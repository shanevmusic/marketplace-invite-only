"""Invite endpoint tests.

Covers:
- Admin creates admin_invite for driver
- Seller cannot create admin_invite (403)
- Seller creates/gets seller_referral (idempotent)
- Seller regenerates referral
- Seller cannot revoke admin's invite (403)
- Admin can revoke any invite
- Validate endpoint flags
- RBAC matrix checks
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    create_admin_invite,
    create_seller_referral,
    seed_admin,
    seed_seller_with_profile,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Admin creates admin_invite for driver
# ---------------------------------------------------------------------------


async def test_admin_creates_driver_invite(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Admin can create admin_invite with role_target=driver → 201."""
    admin = await seed_admin(db, "admin_driver@example.com")
    token = await _login(client, "admin_driver@example.com", "AdminPass123!")

    resp = await client.post(
        "/api/v1/invites/admin",
        json={"role_target": "driver"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["type"] == "admin_invite"
    assert body["role_target"] == "driver"
    assert body["token"] is not None


async def test_seller_cannot_create_admin_invite(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Seller calling POST /invites/admin → 403."""
    seller = await seed_seller_with_profile(db, "seller_no_admin@example.com")
    token = await _login(client, "seller_no_admin@example.com", "SellerPass123!")

    resp = await client.post(
        "/api/v1/invites/admin",
        json={"role_target": "seller"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Seller creates/gets seller_referral (idempotent)
# ---------------------------------------------------------------------------


async def test_seller_creates_referral_idempotent(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Seller calling POST /invites/seller_referral twice returns the same invite."""
    await seed_seller_with_profile(db, "seller_idem@example.com")
    token = await _login(client, "seller_idem@example.com", "SellerPass123!")

    resp1 = await client.post(
        "/api/v1/invites/seller_referral",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 201
    id1 = resp1.json()["id"]

    resp2 = await client.post(
        "/api/v1/invites/seller_referral",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 201
    id2 = resp2.json()["id"]

    assert id1 == id2, "Second call should return same active invite"


async def test_seller_referral_idempotent_returns_token(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Both calls to POST /invites/seller_referral return the same non-null token.

    Regression test for bug where the 'get existing' path returned token=None.
    """
    await seed_seller_with_profile(db, "seller_tok@example.com")
    auth = await _login(client, "seller_tok@example.com", "SellerPass123!")

    resp1 = await client.post(
        "/api/v1/invites/seller_referral",
        headers={"Authorization": f"Bearer {auth}"},
    )
    assert resp1.status_code == 201
    body1 = resp1.json()
    assert body1["token"] is not None, "First call must return a token"
    token1 = body1["token"]
    id1 = body1["id"]

    # Second call — should return existing invite with the same token
    resp2 = await client.post(
        "/api/v1/invites/seller_referral",
        headers={"Authorization": f"Bearer {auth}"},
    )
    assert resp2.status_code == 201
    body2 = resp2.json()
    assert body2["token"] is not None, "Second (idempotent) call must also return a token"
    assert body2["token"] == token1, "Both calls must return the same token"
    assert body2["id"] == id1, "Both calls must return the same invite id"

    # Returned token must be valid
    validate = await client.get(f"/api/v1/invites/validate?token={token1}")
    assert validate.status_code == 200
    assert validate.json()["valid"] is True


async def test_get_or_create_after_regenerate_returns_new_token(
    client: AsyncClient, db: AsyncSession
) -> None:
    """After regenerate, a subsequent GET/create returns the new token (not null)."""
    await seed_seller_with_profile(db, "seller_regen2@example.com")
    auth = await _login(client, "seller_regen2@example.com", "SellerPass123!")

    # Create initial
    resp1 = await client.post(
        "/api/v1/invites/seller_referral",
        headers={"Authorization": f"Bearer {auth}"},
    )
    old_token = resp1.json()["token"]

    # Regenerate
    regen = await client.post(
        "/api/v1/invites/seller_referral/regenerate",
        headers={"Authorization": f"Bearer {auth}"},
    )
    assert regen.status_code == 201
    new_token = regen.json()["token"]
    assert new_token != old_token

    # get_or_create should return the new active invite with its token
    resp2 = await client.post(
        "/api/v1/invites/seller_referral",
        headers={"Authorization": f"Bearer {auth}"},
    )
    assert resp2.status_code == 201
    body2 = resp2.json()
    assert body2["token"] is not None, "get_or_create after regen must return non-null token"
    assert body2["token"] == new_token, "Must return the newly regenerated token"


# ---------------------------------------------------------------------------
# Seller regenerates referral
# ---------------------------------------------------------------------------


async def test_seller_regenerates_referral(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Seller regenerates referral → old token invalid, new one works."""
    seller = await seed_seller_with_profile(db, "seller_regen@example.com")
    access = await _login(client, "seller_regen@example.com", "SellerPass123!")

    # Create initial referral
    resp1 = await client.post(
        "/api/v1/invites/seller_referral",
        headers={"Authorization": f"Bearer {access}"},
    )
    old_token = resp1.json()["token"]
    old_id = resp1.json()["id"]

    # Regenerate
    resp2 = await client.post(
        "/api/v1/invites/seller_referral/regenerate",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp2.status_code == 201
    new_token = resp2.json()["token"]
    new_id = resp2.json()["id"]

    assert old_id != new_id
    assert old_token != new_token

    # Old token should now be invalid (revoked)
    validate_resp = await client.get(
        f"/api/v1/invites/validate?token={old_token}"
    )
    assert validate_resp.json()["revoked"] is True
    assert validate_resp.json()["valid"] is False

    # New token should be valid
    validate_new = await client.get(
        f"/api/v1/invites/validate?token={new_token}"
    )
    assert validate_new.json()["valid"] is True


# ---------------------------------------------------------------------------
# Revocation RBAC
# ---------------------------------------------------------------------------


async def test_seller_cannot_revoke_admins_invite(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Seller trying to delete an admin's invite → 403."""
    admin = await seed_admin(db, "admin_rev@example.com")
    seller = await seed_seller_with_profile(db, "seller_rev@example.com")

    admin_invite_token = await create_admin_invite(db, admin, "customer")
    seller_token = await _login(client, "seller_rev@example.com", "SellerPass123!")

    # Get the invite ID from validate
    import sqlalchemy as sa
    from app.models.invite_link import InviteLink
    result = await db.execute(
        sa.select(InviteLink).where(InviteLink.token == admin_invite_token)
    )
    invite = result.scalar_one()

    resp = await client.delete(
        f"/api/v1/invites/{invite.id}",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert resp.status_code == 403


async def test_admin_can_revoke_any_invite(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Admin can revoke any invite."""
    admin = await seed_admin(db, "admin_revoke2@example.com")
    seller = await seed_seller_with_profile(db, "seller_revoke2@example.com")

    ref_token = await create_seller_referral(db, seller)
    admin_access = await _login(client, "admin_revoke2@example.com", "AdminPass123!")

    import sqlalchemy as sa
    from app.models.invite_link import InviteLink
    result = await db.execute(
        sa.select(InviteLink).where(InviteLink.token == ref_token)
    )
    invite = result.scalar_one()

    resp = await client.delete(
        f"/api/v1/invites/{invite.id}",
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Validate endpoint
# ---------------------------------------------------------------------------


async def test_validate_valid_token(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Validate a valid token → valid=True."""
    admin = await seed_admin(db, "admin_valid@example.com")
    token = await create_admin_invite(db, admin, "customer")

    resp = await client.get(f"/api/v1/invites/validate?token={token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["expired"] is False
    assert body["revoked"] is False
    assert body["already_used"] is False
    assert body["role_target"] == "customer"


async def test_validate_expired_token(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Validate an expired token → valid=False, expired=True."""
    admin = await seed_admin(db, "admin_exp_val@example.com")
    token = await create_admin_invite(db, admin, "customer", expired=True)

    resp = await client.get(f"/api/v1/invites/validate?token={token}")
    body = resp.json()
    assert body["valid"] is False
    assert body["expired"] is True


async def test_validate_revoked_token(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Validate a revoked token → valid=False, revoked=True."""
    admin = await seed_admin(db, "admin_rev_val@example.com")
    token = await create_admin_invite(db, admin, "customer", revoked=True)

    resp = await client.get(f"/api/v1/invites/validate?token={token}")
    body = resp.json()
    assert body["valid"] is False
    assert body["revoked"] is True


async def test_validate_consumed_token(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Validate a fully-consumed token → valid=False, already_used=True."""
    admin = await seed_admin(db, "admin_used_val@example.com")
    token = await create_admin_invite(db, admin, "customer", used=True)

    resp = await client.get(f"/api/v1/invites/validate?token={token}")
    body = resp.json()
    assert body["valid"] is False
    assert body["already_used"] is True


async def test_validate_unknown_token(client: AsyncClient) -> None:
    """Validate an unknown token → valid=False."""
    resp = await client.get("/api/v1/invites/validate?token=doesnotexist")
    body = resp.json()
    assert body["valid"] is False


# ---------------------------------------------------------------------------
# RBAC matrix checks
# ---------------------------------------------------------------------------


async def test_non_admin_cannot_create_admin_invite_403(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Customer or driver cannot call POST /invites/admin."""
    import uuid
    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="customer_rbac@example.com",
        password_hash=hash_password("CustPass123!"),
        role="customer",
        display_name="Customer RBAC",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    token = await _login(client, "customer_rbac@example.com", "CustPass123!")
    resp = await client.post(
        "/api/v1/invites/admin",
        json={"role_target": "seller"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_unauthenticated_cannot_create_admin_invite(
    client: AsyncClient,
) -> None:
    """Unauthenticated → 401 on POST /invites/admin."""
    resp = await client.post(
        "/api/v1/invites/admin",
        json={"role_target": "seller"},
    )
    assert resp.status_code == 401
