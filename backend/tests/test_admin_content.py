"""Admin products (content moderation) tests (Phase 11)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    seed_admin,
    seed_product,
    seed_seller_with_profile,
    seed_store_for_seller,
)


pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_list_products_admin(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, email="ap1@x.com")
    seller = await seed_seller_with_profile(db, email="sp1@x.com")
    store = await seed_store_for_seller(db, seller)
    await seed_product(db, seller, store, name="Widget")
    await db.commit()
    t = await _login(client, "ap1@x.com", "AdminPass123!")

    resp = await client.get(
        "/api/v1/admin/products",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert any(p["name"] == "Widget" for p in body["data"])


async def test_disable_and_restore_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, email="ap2@x.com")
    seller = await seed_seller_with_profile(db, email="sp2@x.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, name="ModMe")
    await db.commit()
    t = await _login(client, "ap2@x.com", "AdminPass123!")

    resp = await client.post(
        f"/api/v1/admin/products/{product.id}/disable",
        json={"reason": "Counterfeit"},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "disabled"
    assert body["disabled_reason"] == "Counterfeit"

    resp = await client.post(
        f"/api/v1/admin/products/{product.id}/restore",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


async def test_non_admin_cannot_moderate(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, email="sp3@x.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, name="Nope")
    await db.commit()
    t = await _login(client, "sp3@x.com", "SellerPass123!")
    resp = await client.post(
        f"/api/v1/admin/products/{product.id}/disable",
        json={"reason": "x"},
        headers={"Authorization": f"Bearer {t}"},
    )
    assert resp.status_code == 403
