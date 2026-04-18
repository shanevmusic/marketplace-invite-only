"""Phase 12 — security hardening regression tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import seed_admin, seed_driver, seed_seller_with_profile


# ---------------------------------------------------------------------------
# (a) Login suspension gap
# ---------------------------------------------------------------------------


async def test_login_rejects_suspended_user_with_403(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Suspended accounts get 403 AUTH_ACCOUNT_SUSPENDED BEFORE token issuance."""
    admin = await seed_admin(db, email="sa1@x.com")
    driver = await seed_driver(db, email="sd1@x.com")
    await db.commit()

    # Log in to get an admin token.
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "sa1@x.com", "password": "AdminPass123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    # Suspend the driver.
    resp = await client.post(
        f"/api/v1/admin/users/{driver.id}/suspend",
        json={"reason": "TOS"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Driver login is now rejected with 403.
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "sd1@x.com", "password": "DriverPass123!"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "AUTH_ACCOUNT_SUSPENDED"
    # No tokens leaked in the response
    assert "access_token" not in body
    assert "refresh_token" not in body


async def test_login_wrong_password_for_suspended_stays_opaque(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Wrong password on a suspended account still returns opaque 401.

    Suspension must not create a user-enumeration oracle.
    """
    admin = await seed_admin(db, email="sa2@x.com")
    driver = await seed_driver(db, email="sd2@x.com")
    await db.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "sa2@x.com", "password": "AdminPass123!"},
    )
    token = login.json()["access_token"]
    await client.post(
        f"/api/v1/admin/users/{driver.id}/suspend",
        json={"reason": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "sd2@x.com", "password": "WRONG_PASSWORD_1234"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


# ---------------------------------------------------------------------------
# (c) Security headers middleware
# ---------------------------------------------------------------------------


async def test_security_headers_applied_to_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    headers = {k.lower(): v for k, v in resp.headers.items()}
    assert "strict-transport-security" in headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in headers["permissions-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


async def test_security_headers_applied_to_error_responses(
    client: AsyncClient,
) -> None:
    """Headers must be present even when the response is a 4xx envelope."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "notfound@example.com", "password": "bad"},
    )
    assert resp.status_code == 401
    assert "strict-transport-security" in resp.headers


# ---------------------------------------------------------------------------
# (c) Password entropy check (common-password rejection)
# ---------------------------------------------------------------------------


async def test_signup_rejects_common_password(
    client: AsyncClient, db: AsyncSession
) -> None:
    from tests.conftest import create_admin_invite

    admin = await seed_admin(db, email="apw@x.com")
    token = await create_admin_invite(db, admin, "customer")
    await db.commit()

    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "new@x.com",
            "password": "password12345",  # in the common list, ≥12 chars
            "display_name": "New",
            "invite_token": token,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "PASSWORD_TOO_COMMON"


# ---------------------------------------------------------------------------
# (c) Password-rehash policy
# ---------------------------------------------------------------------------


async def test_password_rehash_on_login_when_params_weaker(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the stored hash is weaker than current params, login silently rehashes."""
    import argon2

    from app.core import security as sec

    admin = await seed_admin(db, email="rh@x.com")
    await db.commit()

    # Swap in a stronger hasher so the seeded one is "old".
    strong = argon2.PasswordHasher(
        time_cost=4, memory_cost=65536, parallelism=2
    )
    monkeypatch.setattr(sec, "_ph", strong)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "rh@x.com", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200

    from sqlalchemy import select

    from app.models.user import User

    await db.commit()
    # Use a fresh session via expire_all + re-query
    db.expire_all()
    row = (
        await db.execute(select(User).where(User.email == "rh@x.com"))
    ).scalar_one()
    # The new hash must not equal the old one (params upgraded).
    assert row.password_hash.startswith("$argon2id$")
