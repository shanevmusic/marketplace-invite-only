"""Admin users/invites endpoint tests (Phase 11)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    seed_admin,
    seed_customer,
    seed_driver,
    seed_seller_with_profile,
)


pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_list_users_admin_gated(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, email="admin@x.com")
    await seed_seller_with_profile(db, email="seller@x.com")
    await db.commit()

    # Seller is forbidden
    seller_token = await _login(client, "seller@x.com", "SellerPass123!")
    resp = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert resp.status_code == 403

    admin_token = await _login(client, "admin@x.com", "AdminPass123!")
    resp = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body and "pagination" in body
    emails = {u["email"] for u in body["data"]}
    assert "admin@x.com" in emails
    assert "seller@x.com" in emails


async def test_list_users_filters(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, email="a1@x.com")
    await seed_seller_with_profile(db, email="s1@x.com")
    await seed_customer(db, email="c1@x.com")
    await seed_driver(db, email="d1@x.com")
    await db.commit()
    t = await _login(client, "a1@x.com", "AdminPass123!")

    resp = await client.get(
        "/api/v1/admin/users?role=driver",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    roles = {u["role"] for u in resp.json()["data"]}
    assert roles == {"driver"}

    resp = await client.get(
        "/api/v1/admin/users?q=s1",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()["data"]}
    assert "s1@x.com" in emails


async def test_suspend_and_unsuspend_flow(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, email="a2@x.com")
    driver = await seed_driver(db, email="drv@x.com")
    await db.commit()
    t = await _login(client, "a2@x.com", "AdminPass123!")

    # Suspend
    resp = await client.post(
        f"/api/v1/admin/users/{driver.id}/suspend",
        json={"reason": "TOS violation"},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "suspended"
    assert body["suspended_reason"] == "TOS violation"

    # Phase 12: suspended users are rejected at the /auth/login boundary
    # BEFORE any tokens are issued.  403 AUTH_ACCOUNT_SUSPENDED is the
    # canonical response.
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "drv@x.com", "password": "DriverPass123!"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTH_ACCOUNT_SUSPENDED"

    # Unsuspend
    resp = await client.post(
        f"/api/v1/admin/users/{driver.id}/unsuspend",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


async def test_suspend_forbidden_for_non_admin(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, email="s2@x.com")
    driver = await seed_driver(db, email="d2@x.com")
    await db.commit()
    t = await _login(client, "s2@x.com", "SellerPass123!")
    resp = await client.post(
        f"/api/v1/admin/users/{driver.id}/suspend",
        json={"reason": "nope"},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 403


async def test_admin_issue_invite(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, email="a3@x.com")
    await db.commit()
    t = await _login(client, "a3@x.com", "AdminPass123!")
    resp = await client.post(
        "/api/v1/admin/invites",
        json={"role_target": "seller", "expires_in_days": 14},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role_target"] == "seller"
    assert body["token"]
    assert body["expires_at"]


async def test_user_detail_with_referral_tree(
    client: AsyncClient, db: AsyncSession
) -> None:
    import uuid
    from datetime import datetime, timezone

    from app.models.invite_link import InviteLink
    from app.models.referral import Referral

    admin = await seed_admin(db, email="a4@x.com")
    seller = await seed_seller_with_profile(db, email="s4@x.com")
    customer = await seed_customer(db, email="c4@x.com")

    invite = InviteLink(
        id=uuid.uuid4(),
        issuer_id=seller.id,
        type="seller_referral",
        token="tok_" + uuid.uuid4().hex,
        role_target=None,
        max_uses=None,
        used_count=1,
        expires_at=None,
    )
    db.add(invite)
    await db.flush()

    ref = Referral(
        id=uuid.uuid4(),
        referrer_id=seller.id,
        referred_user_id=customer.id,
        invite_link_id=invite.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(ref)
    await db.commit()
    t = await _login(client, "a4@x.com", "AdminPass123!")

    resp = await client.get(
        f"/api/v1/admin/users/{seller.id}",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    referred = {u["email"] for u in body["referred_users"]}
    assert "c4@x.com" in referred
