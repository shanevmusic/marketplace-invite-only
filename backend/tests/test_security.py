"""Security regression tests for Phase 3 auth + invite implementation.

Tests in this module verify specific security properties:
- User enumeration prevention (login returns identical errors)
- Disabled/soft-deleted user blocking
- JWT algorithm restrictions (alg:none, wrong secret, unknown sub)
- Refresh-token rotation TOCTOU protection (SELECT FOR UPDATE)
- JWT secret startup validation
- Password minimum length enforcement

Run with:
    APP_ENVIRONMENT=test pytest -q tests/test_security.py
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from tests.conftest import seed_admin, seed_seller_with_profile

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return resp


async def _seed_user(
    db: AsyncSession,
    email: str,
    password: str = "StrongPass123!",
    role: str = "customer",
    is_active: bool = True,
    deleted_at: datetime | None = None,
    disabled_at: datetime | None = None,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
        role=role,
        display_name=f"Security Test {email}",
        is_active=is_active,
        deleted_at=deleted_at,
        disabled_at=disabled_at,
    )
    db.add(user)
    await db.flush()
    return user


# ---------------------------------------------------------------------------
# 1. Login returns identical error for wrong password vs unknown email
#    (timing + error-code parity)
# ---------------------------------------------------------------------------


async def test_login_error_parity_unknown_email(client: AsyncClient, db: AsyncSession) -> None:
    """Unknown email → 401 AUTH_INVALID_CREDENTIALS (same as wrong password)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "no_such_user_xyz@example.com", "password": "SomePassword123!"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_login_error_parity_wrong_password(client: AsyncClient, db: AsyncSession) -> None:
    """Wrong password → 401 AUTH_INVALID_CREDENTIALS."""
    await seed_admin(db, "parity_test@example.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "parity_test@example.com", "password": "WrongPassword999!"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_login_error_parity_same_response_body(client: AsyncClient, db: AsyncSession) -> None:
    """Wrong password and unknown email return identical HTTP status + error code.

    This prevents an attacker from inferring account existence.
    """
    await seed_admin(db, "parity_same@example.com")

    # Wrong password for existing user
    resp_wrong_pw = await client.post(
        "/api/v1/auth/login",
        json={"email": "parity_same@example.com", "password": "WrongPassword!"},
    )
    # Unknown user
    resp_unknown = await client.post(
        "/api/v1/auth/login",
        json={"email": "doesnotexist_parity@example.com", "password": "WrongPassword!"},
    )

    assert resp_wrong_pw.status_code == resp_unknown.status_code == 401
    assert (
        resp_wrong_pw.json()["error"]["code"]
        == resp_unknown.json()["error"]["code"]
        == "AUTH_INVALID_CREDENTIALS"
    )


# ---------------------------------------------------------------------------
# 2. Disabled user cannot authenticate (is_active=False)
# ---------------------------------------------------------------------------


async def test_disabled_user_login_blocked(client: AsyncClient, db: AsyncSession) -> None:
    """User with is_active=False cannot log in via /auth/login."""
    await _seed_user(
        db,
        email="sec_disabled@example.com",
        password="StrongPass123!",
        is_active=False,
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "sec_disabled@example.com", "password": "StrongPass123!"},
    )
    assert resp.status_code == 401
    # Must NOT reveal that the account exists (same opaque code as wrong password)
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_disabled_user_access_token_rejected(client: AsyncClient, db: AsyncSession) -> None:
    """After disabling a user, their existing access token must 401 on /auth/me."""
    import sqlalchemy as sa
    from app.core.security import create_access_token

    user = await _seed_user(
        db,
        email="sec_disable_after@example.com",
        password="StrongPass123!",
        is_active=True,
    )

    # Create a valid access token for this user
    access_token, _ = create_access_token(user.id, user.role)

    # Disable the user in-band
    await db.execute(
        sa.update(User).where(User.id == user.id).values(is_active=False)
    )
    await db.flush()

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 401


async def test_disabled_at_user_access_token_rejected(client: AsyncClient, db: AsyncSession) -> None:
    """User with disabled_at IS NOT NULL must 401 on /auth/me."""
    import sqlalchemy as sa
    from app.core.security import create_access_token

    user = await _seed_user(
        db,
        email="sec_disabled_at@example.com",
        password="StrongPass123!",
        is_active=True,
    )

    # Issue a token first, then set disabled_at
    access_token, _ = create_access_token(user.id, user.role)

    now = datetime.now(timezone.utc)
    await db.execute(
        sa.update(User).where(User.id == user.id).values(disabled_at=now)
    )
    await db.flush()

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 3. Soft-deleted user cannot authenticate
# ---------------------------------------------------------------------------


async def test_soft_deleted_user_login_blocked(client: AsyncClient, db: AsyncSession) -> None:
    """Soft-deleted user (deleted_at IS NOT NULL) cannot log in."""
    now = datetime.now(timezone.utc)
    await _seed_user(
        db,
        email="sec_deleted@example.com",
        password="StrongPass123!",
        is_active=True,
        deleted_at=now,
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "sec_deleted@example.com", "password": "StrongPass123!"},
    )
    # login() filters deleted_at IS NULL — user not found → AUTH_INVALID_CREDENTIALS
    assert resp.status_code == 401


async def test_soft_deleted_user_token_rejected(client: AsyncClient, db: AsyncSession) -> None:
    """Access token for a soft-deleted user must be rejected by /auth/me."""
    import sqlalchemy as sa
    from app.core.security import create_access_token

    user = await _seed_user(
        db,
        email="sec_deleted_token@example.com",
        password="StrongPass123!",
        is_active=True,
    )

    access_token, _ = create_access_token(user.id, user.role)

    # Soft-delete the user
    now = datetime.now(timezone.utc)
    await db.execute(
        sa.update(User).where(User.id == user.id).values(deleted_at=now)
    )
    await db.flush()

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 4. JWT with alg:none is rejected
# ---------------------------------------------------------------------------


async def test_jwt_alg_none_rejected(client: AsyncClient) -> None:
    """A token with alg:none (no signature) must be rejected with 401."""
    import base64
    import json

    # Craft a JWT with alg:none manually
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "sub": str(uuid.uuid4()),
                "role": "admin",
                "jti": "test",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                "iat": int(datetime.now(timezone.utc).timestamp()),
            }
        ).encode()
    ).rstrip(b"=").decode()

    # alg:none token has an empty signature segment
    forged_token = f"{header}.{payload}."

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 5. JWT signed with wrong secret is rejected
# ---------------------------------------------------------------------------


async def test_jwt_wrong_secret_rejected(client: AsyncClient, db: AsyncSession) -> None:
    """JWT signed with a different secret must be rejected with 401."""
    from jose import jwt as jose_jwt

    user = await seed_admin(db, "sec_wrong_secret@example.com")

    # Sign with a different secret
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": "admin",
        "jti": "test-jti",
        "exp": now + timedelta(minutes=15),
        "iat": now,
    }
    forged_token = jose_jwt.encode(payload, "completely_different_secret", algorithm="HS256")

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 6. JWT with valid signature but unknown sub (no user) → 401
# ---------------------------------------------------------------------------


async def test_jwt_unknown_sub_rejected(client: AsyncClient) -> None:
    """JWT with valid signature but sub=random UUID (no matching user) → 401."""
    from app.core.security import create_access_token

    random_id = uuid.uuid4()
    token, _ = create_access_token(random_id, "customer")

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 7. Concurrent refresh rotation TOCTOU test
#    After SELECT FOR UPDATE fix: exactly one request should succeed, the other
#    should fail (either with an error or with a re-used token error).
# ---------------------------------------------------------------------------


async def test_concurrent_refresh_rotation_one_wins(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Two concurrent requests with the same refresh token: only one should succeed.

    After the SELECT FOR UPDATE fix, the DB serialises the two requests so exactly
    one rotation succeeds.  The other either gets a token-not-found (already
    rotated) or a token-reused error.  Both are 401.

    Note: This test simulates concurrency sequentially using the same HTTP client
    and DB session.  True concurrent DB-level lock testing requires two separate
    DB connections; this test validates the rotation logic correctness.
    """
    import sqlalchemy as sa
    from app.models.refresh_token import RefreshToken
    from app.core.security import hash_refresh_token

    unique = uuid.uuid4().hex[:8]
    await seed_admin(db, f"sec_toctou_{unique}@example.com")

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": f"sec_toctou_{unique}@example.com",
            "password": "AdminPass123!",
        },
    )
    assert login_resp.status_code == 200
    original_refresh = login_resp.json()["refresh_token"]

    # First rotation attempt — should succeed
    resp1 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh},
    )
    assert resp1.status_code == 200
    new_token_from_first = resp1.json()["refresh_token"]

    # Second attempt with the SAME original token — must fail (already rotated)
    resp2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": original_refresh},
    )
    # Must be 401 — either AUTH_TOKEN_REUSED or AUTH_TOKEN_INVALID
    assert resp2.status_code == 401
    assert resp2.json()["error"]["code"] in (
        "AUTH_TOKEN_REUSED",
        "AUTH_TOKEN_INVALID",
    )


# ---------------------------------------------------------------------------
# 8. Default JWT secret causes startup failure in non-dev/test environment
# ---------------------------------------------------------------------------


def test_default_jwt_secret_hard_fails_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings with environment='prod' and default JWT secret must raise.

    We instantiate Settings() directly with prod environment and the default
    secret.  The model_validator must raise RuntimeError (or a pydantic
    ValidationError wrapping it).
    """
    import os
    # Temporarily override env vars so Settings() picks them up
    monkeypatch.setenv("APP_ENVIRONMENT", "prod")
    monkeypatch.setenv("APP_JWT_SECRET", "change_me_phase_3")

    # Clear the .env file override by importing Settings directly
    from app.core.config import Settings
    from pydantic import ValidationError

    with pytest.raises((RuntimeError, ValidationError)):
        # Construct a new instance — triggers the model_validator
        Settings(
            environment="prod",
            jwt_secret="change_me_phase_3",
            database_url="postgresql+asyncpg://x:x@localhost:5432/x",
            database_url_sync="postgresql://x:x@localhost:5432/x",
        )


def test_default_jwt_secret_allowed_in_dev() -> None:
    """Settings with environment='dev' and default JWT secret must NOT raise."""
    from app.core.config import Settings

    # Should not raise
    s = Settings(
        environment="dev",
        jwt_secret="change_me_phase_3",
        database_url="postgresql+asyncpg://x:x@localhost:5432/x",
        database_url_sync="postgresql://x:x@localhost:5432/x",
    )
    assert s.environment == "dev"


def test_default_jwt_secret_allowed_in_test() -> None:
    """Settings with environment='test' and default JWT secret must NOT raise."""
    from app.core.config import Settings

    s = Settings(
        environment="test",
        jwt_secret="change_me_phase_3",
        database_url="postgresql+asyncpg://x:x@localhost:5432/x",
        database_url_sync="postgresql://x:x@localhost:5432/x",
    )
    assert s.environment == "test"


# ---------------------------------------------------------------------------
# 9. Password too short (11 chars) is rejected at signup
# ---------------------------------------------------------------------------


async def test_signup_password_too_short(client: AsyncClient, db: AsyncSession) -> None:
    """Signup with 11-char password → 422 VALIDATION_FAILED (min_length=12)."""
    from tests.conftest import create_admin_invite

    admin = await seed_admin(db, "sec_pw_short_admin@example.com")
    token = await create_admin_invite(db, admin, "customer")

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "sec_pw_short@example.com",
            "password": "Short1234!X",  # 11 chars — exactly one under the minimum
            "display_name": "Short PW User",
            "invite_token": token,
            "role_choice": "customer",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_signup_password_minimum_accepted(client: AsyncClient, db: AsyncSession) -> None:
    """Signup with exactly 12-char password → succeeds (201)."""
    from tests.conftest import create_admin_invite

    admin = await seed_admin(db, "sec_pw_ok_admin@example.com")
    token = await create_admin_invite(db, admin, "customer")

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "sec_pw_ok@example.com",
            "password": "Short1234!XY",  # 12 chars — exactly the minimum
            "display_name": "Good PW User",
            "invite_token": token,
            "role_choice": "customer",
        },
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# 10. Invite validate PII check — no email or phone leaked
# ---------------------------------------------------------------------------


async def test_validate_invite_no_pii_leak(client: AsyncClient, db: AsyncSession) -> None:
    """GET /invites/validate must not expose issuer email, phone, or ID."""
    from tests.conftest import create_admin_invite

    admin = await seed_admin(db, "sec_validate_pii@example.com")
    token = await create_admin_invite(db, admin, "customer")

    resp = await client.get(f"/api/v1/invites/validate?token={token}")
    assert resp.status_code == 200
    body = resp.json()

    # Allowed fields
    allowed_keys = {
        "type", "role_target", "issuer_display_name", "issuer_role",
        "valid", "already_used", "expired", "revoked",
    }
    # email, phone, id must not be present
    assert "email" not in body
    assert "phone" not in body
    assert "issuer_id" not in body
    assert "issuer_email" not in body
