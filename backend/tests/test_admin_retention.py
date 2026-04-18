"""Admin retention settings tests.

- GET /admin/settings/retention returns current config.
- PATCH updates retention_min_days / order_auto_complete_grace_hours.
- PATCH rejects values < 1 with RETENTION_SETTING_INVALID (422).
- Non-admin callers get 403.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    seed_admin,
    seed_customer,
    seed_seller_with_profile,
)

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, pw: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def test_get_retention_settings(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, "admin_ret_s1@example.com")
    tok = await _login(client, "admin_ret_s1@example.com", "AdminPass123!")

    r = await client.get("/api/v1/admin/settings/retention", headers=_h(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["retention_min_days"] >= 1
    assert body["order_auto_complete_grace_hours"] >= 1


async def test_patch_retention_settings(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, "admin_ret_s2@example.com")
    tok = await _login(client, "admin_ret_s2@example.com", "AdminPass123!")

    r = await client.patch(
        "/api/v1/admin/settings/retention",
        json={"retention_min_days": 45, "order_auto_complete_grace_hours": 96},
        headers=_h(tok),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["retention_min_days"] == 45
    assert body["order_auto_complete_grace_hours"] == 96

    # Verify persisted
    r = await client.get("/api/v1/admin/settings/retention", headers=_h(tok))
    assert r.json()["retention_min_days"] == 45


async def test_patch_rejects_zero_retention(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, "admin_ret_s3@example.com")
    tok = await _login(client, "admin_ret_s3@example.com", "AdminPass123!")

    r = await client.patch(
        "/api/v1/admin/settings/retention",
        json={"retention_min_days": 0},
        headers=_h(tok),
    )
    # Could be caught at schema layer (422 VALIDATION_FAILED) or service (422)
    assert r.status_code == 422


async def test_patch_rejects_zero_grace(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, "admin_ret_s4@example.com")
    tok = await _login(client, "admin_ret_s4@example.com", "AdminPass123!")

    r = await client.patch(
        "/api/v1/admin/settings/retention",
        json={"order_auto_complete_grace_hours": 0},
        headers=_h(tok),
    )
    assert r.status_code == 422


async def test_non_admin_cannot_view_settings(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "seller_ret_s5@example.com")
    s_tok = await _login(client, "seller_ret_s5@example.com", "SellerPass123!")
    r = await client.get("/api/v1/admin/settings/retention", headers=_h(s_tok))
    assert r.status_code == 403


async def test_non_admin_cannot_patch(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "seller_ret_s6@example.com")
    seller = await seed_seller_with_profile(db, "seller_ret_s6b@example.com")
    await seed_customer(db, "cust_ret_s6@example.com", referring_seller_id=seller.id)
    c_tok = await _login(client, "cust_ret_s6@example.com", "CustomerPass123!")

    r = await client.patch(
        "/api/v1/admin/settings/retention",
        json={"retention_min_days": 60},
        headers=_h(c_tok),
    )
    assert r.status_code == 403
