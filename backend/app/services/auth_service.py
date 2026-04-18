"""Auth service — signup, login, refresh, logout, and session management.

All DB writes go through async SQLAlchemy sessions.  Password hashing uses
Argon2id; refresh tokens are opaque random strings with SHA-256 stored.

Design (ADR-0006):
- Refresh token rotation: each /auth/refresh revokes the old row and issues new.
- Reuse detection: if a revoked token is presented, ALL user tokens are revoked.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccountSuspended,
    AuthenticationError,
    EmailTaken,
    InvalidCredentials,
    InvalidTokenError,
    TokenExpired,
    TokenRevoked,
    TokenReused,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    LoginResponse,
    RefreshResponse,
    SignupRequest,
    UserInSignup,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _create_refresh_token_row(
    db: AsyncSession,
    user: User,
    device_label: Optional[str] = None,
) -> tuple[str, RefreshToken]:
    """Create a refresh token row in the DB and return (plaintext, row)."""
    from app.core.config import settings

    plaintext, token_hash = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=token_hash,
        device_label=device_label,
        issued_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )
    db.add(row)
    return plaintext, row


def _build_login_response(
    user: User,
    access_token: str,
    refresh_plaintext: str,
    exp: datetime,
) -> LoginResponse:
    now = datetime.now(timezone.utc)
    expires_in = max(0, int((exp - now).total_seconds()))
    return LoginResponse(
        user=UserInSignup(
            id=user.id,
            email=user.email,
            role=user.role,
            display_name=user.display_name,
        ),
        access_token=access_token,
        refresh_token=refresh_plaintext,
        expires_in=expires_in,
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def signup(
    db: AsyncSession,
    req: SignupRequest,
) -> LoginResponse:
    """Register a new user, consuming the invite token atomically.

    Validates the invite via invite_service.consume_invite, creates the user
    row, writes a referral row if applicable, sets referring_seller_id, and
    issues a token pair.
    """
    from app.core.exceptions import PasswordTooCommon
    from app.core.password_policy import is_common_password
    from app.services.invite_service import consume_invite

    # Reject passwords in the embedded common-password list before touching
    # the invite row, so we don't consume a single-use invite on a bad pw.
    if is_common_password(req.password):
        raise PasswordTooCommon()

    # Validate and consume invite (raises on any invalid state)
    role_choice = req.role_choice
    invite_link = await consume_invite(db, req.invite_token, role_choice)

    # Determine the user's role
    if invite_link.type == "admin_invite":
        role = invite_link.role_target
    else:
        # seller_referral: role_choice is validated in consume_invite
        role = role_choice

    # Check email uniqueness
    existing = await db.execute(
        sa.select(User).where(User.email == req.email, User.deleted_at.is_(None))
    )
    if existing.scalar_one_or_none() is not None:
        raise EmailTaken()

    # Create user
    user_id = uuid.uuid4()
    pw_hash = hash_password(req.password)

    referring_seller_id: Optional[uuid.UUID] = None
    if invite_link.type == "seller_referral":
        # issuer must be a seller; set referring_seller_id
        referring_seller_id = invite_link.issuer_id

    user = User(
        id=user_id,
        email=req.email,
        password_hash=pw_hash,
        role=role,
        display_name=req.display_name,
        phone=req.phone,
        is_active=True,
        referring_seller_id=referring_seller_id,
    )
    db.add(user)
    await db.flush()  # get user.id into DB for FK references

    # Write referral row (for both admin_invite and seller_referral)
    from app.models.referral import Referral

    referral_row = Referral(
        id=uuid.uuid4(),
        referrer_id=invite_link.issuer_id,
        referred_user_id=user.id,
        invite_link_id=invite_link.id,
    )
    db.add(referral_row)

    # Issue tokens
    access_token, exp = create_access_token(user.id, role)  # type: ignore[arg-type]
    refresh_plaintext, _ = await _create_refresh_token_row(db, user)

    await db.commit()
    await db.refresh(user)

    return _build_login_response(user, access_token, refresh_plaintext, exp)


async def login(
    db: AsyncSession,
    email: str,
    password: str,
    device_label: Optional[str] = None,
) -> LoginResponse:
    """Verify credentials and issue a token pair."""
    result = await db.execute(
        sa.select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    # Use a single opaque check for missing user, wrong password, OR disabled
    # account to prevent user-enumeration via differing error messages.
    # The disabled-account check comes AFTER password verification so that an
    # attacker cannot determine which users exist by observing a different
    # error path (e.g. "account disabled" vs "wrong password").
    password_ok = user is not None and verify_password(password, user.password_hash)
    if not password_ok:
        raise InvalidCredentials()

    if not user.is_active:  # type: ignore[union-attr]  # user is not None at this point
        # Return the same opaque error — do NOT reveal the account exists.
        raise InvalidCredentials()

    # Phase 12: reject suspended accounts BEFORE issuing any tokens.  Unlike
    # the opaque "invalid credentials" path above, suspensions are an
    # explicit admin decision the user already knows about, so surfacing
    # 403 AUTH_ACCOUNT_SUSPENDED is the expected UX.
    if user.status == "suspended":  # type: ignore[union-attr]
        raise AccountSuspended()

    # Silently rehash if argon2 parameters have been strengthened since the
    # stored hash was created.
    if needs_rehash(user.password_hash):  # type: ignore[union-attr]
        user.password_hash = hash_password(password)  # type: ignore[union-attr]

    access_token, exp = create_access_token(user.id, user.role)
    refresh_plaintext, _ = await _create_refresh_token_row(db, user, device_label)
    await db.commit()

    return _build_login_response(user, access_token, refresh_plaintext, exp)


async def refresh(
    db: AsyncSession,
    plaintext_refresh: str,
) -> RefreshResponse:
    """Rotate refresh token: validate, revoke old, issue new pair.

    Reuse detection: if the presented token row is already revoked, revoke ALL
    tokens for that user (possible theft scenario).
    """
    token_hash = hash_refresh_token(plaintext_refresh)
    # SELECT FOR UPDATE prevents TOCTOU: two concurrent requests with the same
    # valid refresh token could both pass the revoked_at IS NULL check before
    # either writes.  The row lock serialises rotation within the DB.
    result = await db.execute(
        sa.select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )
    row = result.scalar_one_or_none()

    if row is None:
        raise InvalidTokenError("Refresh token not found.")

    # Reuse detection — revoked token presented
    if row.revoked_at is not None:
        # Revoke ALL tokens for this user
        await db.execute(
            sa.update(RefreshToken)
            .where(
                RefreshToken.user_id == row.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.commit()
        raise TokenReused()

    # Check expiry
    now = datetime.now(timezone.utc)
    expires_at = row.expires_at
    if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise TokenExpired()

    # Load user
    user_result = await db.execute(
        sa.select(User).where(User.id == row.user_id, User.deleted_at.is_(None))
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active or user.disabled_at is not None:
        raise AuthenticationError("Authentication required.")

    # Revoke old row
    row.revoked_at = now
    row.last_used_at = now

    # Issue new token pair
    access_token, exp = create_access_token(user.id, user.role)
    new_plaintext, new_hash = generate_refresh_token()
    new_row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=new_hash,
        device_label=row.device_label,
        issued_at=now,
        expires_at=now + timedelta(days=7),
    )
    db.add(new_row)
    await db.commit()

    expires_in = max(0, int((exp - now).total_seconds()))
    return RefreshResponse(
        access_token=access_token,
        refresh_token=new_plaintext,
        expires_in=expires_in,
    )


async def logout(
    db: AsyncSession,
    plaintext_refresh: str,
) -> None:
    """Revoke the specific refresh token."""
    token_hash = hash_refresh_token(plaintext_refresh)
    result = await db.execute(
        sa.select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await db.commit()


async def logout_all(
    db: AsyncSession,
    user: User,
) -> None:
    """Revoke ALL refresh tokens for *user*."""
    await db.execute(
        sa.update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def get_me(
    db: AsyncSession,
    user: User,
) -> User:
    """Return a fresh copy of *user* from the DB."""
    result = await db.execute(
        sa.select(User).where(User.id == user.id)
    )
    return result.scalar_one()
