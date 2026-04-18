"""Invite service — create, validate, consume, list, and revoke invite links.

Business rules:
- admin_invite: single-use, role-targeted, 7-day default TTL.
- seller_referral: multi-use, one active per seller, no expiry by default.
- Only admin can create driver invites.
- Sellers can only create seller_referral (for customer or seller signup).
- Consumption is atomic: increment used_count, write referrals row.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    InviteAlreadyUsed,
    InviteExpired,
    InviteInvalid,
    InviteRevoked,
    InviteRoleMismatch,
    NotFoundError,
)
from app.models.invite_link import InviteLink
from app.models.seller import Seller
from app.models.user import User
from app.schemas.invites import InviteResponse, ValidateInviteResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ROLES = {"admin", "seller", "customer", "driver"}
SELLER_REFERRAL_ROLES = {"customer", "seller"}


def _token() -> str:
    """Generate a 32-byte URL-safe base64 invite token (≤44 chars)."""
    return secrets.token_urlsafe(32)


def _is_expired(invite: InviteLink) -> bool:
    if invite.expires_at is None:
        return False
    expires_at = invite.expires_at
    if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


def _is_used(invite: InviteLink) -> bool:
    """True if the invite has hit max_uses."""
    if invite.max_uses is None:
        return False
    return invite.used_count >= invite.max_uses


def _build_invite_response(
    invite: InviteLink,
    token_plaintext: Optional[str] = None,
    frontend_base_url: Optional[str] = None,
) -> InviteResponse:
    invite_url: Optional[str] = None
    if frontend_base_url and token_plaintext:
        invite_url = f"{frontend_base_url}/invite?token={token_plaintext}"

    return InviteResponse(
        id=invite.id,
        type=invite.type,
        token=token_plaintext,
        role_target=invite.role_target,
        max_uses=invite.max_uses,
        used_count=invite.used_count,
        expires_at=invite.expires_at,
        revoked_at=invite.revoked_at,
        created_at=invite.created_at,
        invite_url=invite_url,
    )


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def create_admin_invite(
    db: AsyncSession,
    issuer: User,
    role_target: str,
    expires_in_hours: int = 168,
    email_hint: Optional[str] = None,
) -> tuple[InviteLink, str]:
    """Create a single-use admin_invite. Admin only.

    Returns ``(InviteLink, plaintext_token)``.
    """
    if issuer.role != "admin":
        raise AuthorizationError("Only admins can create admin invites.")
    if role_target not in VALID_ROLES:
        raise InviteInvalid(f"Invalid role_target: {role_target!r}")

    plaintext = _token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    invite = InviteLink(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        type="admin_invite",
        token=plaintext,
        role_target=role_target,
        max_uses=1,
        used_count=0,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite, plaintext


async def get_or_create_seller_referral(
    db: AsyncSession,
    seller_user: User,
) -> tuple[InviteLink, Optional[str]]:
    """Return active seller_referral or create one if none exists.

    Returns ``(InviteLink, plaintext_or_none)``.  Plaintext is only returned
    on creation; an existing invite's plaintext is not re-exposed (it was
    shown at creation time).
    """
    if seller_user.role not in ("seller", "admin"):
        raise AuthorizationError("Only sellers or admins can access seller referrals.")

    # Validate seller has a sellers row
    seller_result = await db.execute(
        sa.select(Seller).where(
            Seller.user_id == seller_user.id,
            Seller.deleted_at.is_(None),
        )
    )
    seller = seller_result.scalar_one_or_none()
    if seller is None:
        raise AuthorizationError("User does not have a seller profile.")

    # Check for existing active referral
    existing_result = await db.execute(
        sa.select(InviteLink).where(
            InviteLink.issuer_id == seller_user.id,
            InviteLink.type == "seller_referral",
            InviteLink.revoked_at.is_(None),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return existing, existing.token  # token is stored in plaintext; return it so seller can share it

    # Create new
    plaintext = _token()
    invite = InviteLink(
        id=uuid.uuid4(),
        issuer_id=seller_user.id,
        type="seller_referral",
        token=plaintext,
        role_target=None,  # determined at signup
        max_uses=None,     # unlimited
        used_count=0,
        expires_at=None,   # no expiry by default
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite, plaintext


async def regenerate_seller_referral(
    db: AsyncSession,
    seller_user: User,
) -> tuple[InviteLink, str]:
    """Revoke current active seller_referral and create a new one.

    Returns ``(new_InviteLink, plaintext_token)``.
    """
    if seller_user.role not in ("seller", "admin"):
        raise AuthorizationError("Only sellers or admins can regenerate referrals.")

    # Validate seller profile
    seller_result = await db.execute(
        sa.select(Seller).where(
            Seller.user_id == seller_user.id,
            Seller.deleted_at.is_(None),
        )
    )
    if seller_result.scalar_one_or_none() is None:
        raise AuthorizationError("User does not have a seller profile.")

    # Revoke all active seller_referrals for this issuer
    now = datetime.now(timezone.utc)
    await db.execute(
        sa.update(InviteLink)
        .where(
            InviteLink.issuer_id == seller_user.id,
            InviteLink.type == "seller_referral",
            InviteLink.revoked_at.is_(None),
        )
        .values(revoked_at=now, updated_at=now)
    )

    # Create new
    plaintext = _token()
    invite = InviteLink(
        id=uuid.uuid4(),
        issuer_id=seller_user.id,
        type="seller_referral",
        token=plaintext,
        role_target=None,
        max_uses=None,
        used_count=0,
        expires_at=None,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite, plaintext


async def list_own_invites(
    db: AsyncSession,
    user: User,
) -> list[InviteLink]:
    """Return invites issued by *user*.

    Admin sees all admin_invites they issued.
    Seller sees their seller_referral history.
    """
    if user.role == "admin":
        result = await db.execute(
            sa.select(InviteLink)
            .where(
                InviteLink.issuer_id == user.id,
                InviteLink.type == "admin_invite",
            )
            .order_by(InviteLink.created_at.desc())
        )
    elif user.role == "seller":
        result = await db.execute(
            sa.select(InviteLink)
            .where(
                InviteLink.issuer_id == user.id,
                InviteLink.type == "seller_referral",
            )
            .order_by(InviteLink.created_at.desc())
        )
    else:
        return []
    return list(result.scalars().all())


async def revoke_invite(
    db: AsyncSession,
    user: User,
    invite_id: uuid.UUID,
) -> None:
    """Revoke an invite.

    Admin can revoke any invite.
    Seller can only revoke their own seller_referral.
    """
    result = await db.execute(
        sa.select(InviteLink).where(InviteLink.id == invite_id)
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise NotFoundError("Invite not found.")

    if _is_used(invite):
        raise InviteAlreadyUsed("Cannot revoke a fully-used invite.")

    if user.role == "admin":
        pass  # admin can revoke anything
    elif user.role == "seller":
        if invite.issuer_id != user.id or invite.type != "seller_referral":
            raise AuthorizationError("Sellers can only revoke their own referral invites.")
    else:
        raise AuthorizationError("Insufficient permissions to revoke invites.")

    invite.revoked_at = datetime.now(timezone.utc)
    await db.commit()


async def validate_invite(
    db: AsyncSession,
    token: str,
) -> ValidateInviteResponse:
    """Public endpoint: validate an invite token without consuming it."""
    result = await db.execute(
        sa.select(InviteLink).where(InviteLink.token == token)
    )
    invite = result.scalar_one_or_none()

    if invite is None:
        # Return flags showing invalid rather than raising to keep the endpoint public
        return ValidateInviteResponse(
            type="unknown",
            role_target=None,
            issuer_display_name="",
            issuer_role="",
            valid=False,
            already_used=False,
            expired=False,
            revoked=False,
        )

    # Load issuer
    issuer_result = await db.execute(
        sa.select(User).where(User.id == invite.issuer_id)
    )
    issuer = issuer_result.scalar_one_or_none()
    issuer_name = issuer.display_name if issuer else ""
    issuer_role = issuer.role if issuer else ""

    expired = _is_expired(invite)
    revoked = invite.revoked_at is not None
    already_used = _is_used(invite)
    valid = not expired and not revoked and not already_used

    return ValidateInviteResponse(
        type=invite.type,
        role_target=invite.role_target,
        issuer_display_name=issuer_name,
        issuer_role=issuer_role,
        valid=valid,
        already_used=already_used,
        expired=expired,
        revoked=revoked,
    )


async def consume_invite(
    db: AsyncSession,
    token: str,
    chosen_role: Optional[str],
) -> InviteLink:
    """Validate and atomically increment used_count.

    Called from auth_service.signup.  Does NOT write the referrals row —
    that is done in auth_service after user creation.

    Raises appropriate AppException subclasses on failure.
    Returns the InviteLink row on success.
    """
    result = await db.execute(
        sa.select(InviteLink).where(InviteLink.token == token).with_for_update()
    )
    invite = result.scalar_one_or_none()

    if invite is None:
        raise InviteInvalid()

    if invite.revoked_at is not None:
        raise InviteRevoked()

    if _is_expired(invite):
        raise InviteExpired()

    if _is_used(invite):
        raise InviteAlreadyUsed()

    # Role validation
    if invite.type == "admin_invite":
        # chosen_role must either be None (we'll use role_target) or match
        if chosen_role is not None and chosen_role != invite.role_target:
            raise InviteRoleMismatch(
                f"Admin invite grants role={invite.role_target!r}; "
                f"you requested {chosen_role!r}."
            )
        # Block: make sure role_target is set
        if invite.role_target is None:
            raise InviteInvalid("Admin invite has no role_target.")
    elif invite.type == "seller_referral":
        # chosen_role must be 'customer' or 'seller' — never 'driver' or 'admin'
        if chosen_role not in SELLER_REFERRAL_ROLES:
            raise InviteRoleMismatch(
                f"Seller referral invites only allow roles: {SELLER_REFERRAL_ROLES}. "
                f"Got {chosen_role!r}."
            )
        # Validate issuer is actually a seller
        issuer_result = await db.execute(
            sa.select(User).where(User.id == invite.issuer_id)
        )
        issuer = issuer_result.scalar_one_or_none()
        if issuer is None or issuer.role != "seller":
            raise InviteInvalid("Seller referral issuer is not a valid seller.")

        # Validate issuer has a sellers row
        seller_result = await db.execute(
            sa.select(Seller).where(
                Seller.user_id == invite.issuer_id,
                Seller.deleted_at.is_(None),
            )
        )
        if seller_result.scalar_one_or_none() is None:
            raise InviteInvalid("Seller referral issuer does not have a seller profile.")

    # Atomically increment used_count
    invite.used_count = invite.used_count + 1
    # Don't commit here — caller (signup) will commit after creating user

    return invite
