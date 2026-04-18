"""Tests for referral-scoped visibility (ADR-0007, depth=1).

Covers:
- Customer A referred by seller S sees S's products (GET /products and
  GET /products/{id} both succeed).
- Customer B not referred by S gets 404 on S's product GET and empty list on
  GET /products browse.
- Customer with referring_seller_id=None sees nothing.
- Seller cannot browse another seller's catalog via customer-style listing.
- Driver gets empty list / 404.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    seed_admin,
    seed_customer,
    seed_driver,
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
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Positive case: customer referred by seller sees that seller's products
# ---------------------------------------------------------------------------


async def test_referred_customer_sees_referrers_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "vis_seller@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, name="Visible")

    await seed_customer(db, "vis_cust_ref@example.com", referring_seller_id=seller.id)
    c_token = await _login(client, "vis_cust_ref@example.com", "CustomerPass123!")

    # Browse
    list_resp = await client.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]
    names = [i["name"] for i in items]
    assert "Visible" in names

    # Detail
    detail = await client.get(
        f"/api/v1/products/{product.id}",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["name"] == "Visible"


# ---------------------------------------------------------------------------
# Negative case: customer NOT referred by the seller is blind to them
# ---------------------------------------------------------------------------


async def test_unreferred_customer_cannot_see_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller_a = await seed_seller_with_profile(db, "vis_sellerA@example.com")
    store_a = await seed_store_for_seller(db, seller_a)
    product_a = await seed_product(db, seller_a, store_a, name="Hidden-A")

    seller_b = await seed_seller_with_profile(db, "vis_sellerB@example.com")
    store_b = await seed_store_for_seller(db, seller_b)
    await seed_product(db, seller_b, store_b, name="Other-B")

    # Customer referred by seller B only
    await seed_customer(
        db, "vis_cust_B@example.com", referring_seller_id=seller_b.id
    )
    c_token = await _login(client, "vis_cust_B@example.com", "CustomerPass123!")

    # Direct GET on A's product → 404
    detail = await client.get(
        f"/api/v1/products/{product_a.id}",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert detail.status_code == 404

    # Browse list: must include only B's products, never A's
    list_resp = await client.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert list_resp.status_code == 200
    names = [i["name"] for i in list_resp.json()["data"]]
    assert "Other-B" in names
    assert "Hidden-A" not in names


async def test_unreferred_customer_empty_browse(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Customer with referring_seller_id=None sees an empty product catalog."""
    seller = await seed_seller_with_profile(db, "vis_sel_empty@example.com")
    store = await seed_store_for_seller(db, seller)
    await seed_product(db, seller, store)

    await seed_customer(
        db, "vis_cust_empty@example.com", referring_seller_id=None
    )
    c_token = await _login(
        client, "vis_cust_empty@example.com", "CustomerPass123!"
    )

    resp = await client.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# Cross-seller isolation
# ---------------------------------------------------------------------------


async def test_seller_cannot_see_other_sellers_product_via_detail(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller_a = await seed_seller_with_profile(db, "cross_a@example.com")
    store_a = await seed_store_for_seller(db, seller_a)
    product_a = await seed_product(db, seller_a, store_a, name="A-Product")

    await seed_seller_with_profile(db, "cross_b@example.com")
    b_token = await _login(client, "cross_b@example.com", "SellerPass123!")

    resp = await client.get(
        f"/api/v1/products/{product_a.id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


async def test_seller_browse_shows_only_own_products(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller_a = await seed_seller_with_profile(db, "own_a@example.com")
    store_a = await seed_store_for_seller(db, seller_a)
    await seed_product(db, seller_a, store_a, name="OWN-A")

    seller_b = await seed_seller_with_profile(db, "own_b@example.com")
    store_b = await seed_store_for_seller(db, seller_b)
    await seed_product(db, seller_b, store_b, name="OWN-B")

    b_token = await _login(client, "own_b@example.com", "SellerPass123!")
    resp = await client.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()["data"]]
    assert names == ["OWN-B"]
    assert "OWN-A" not in names


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def test_driver_browse_is_empty(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "driver_vis_s@example.com")
    store = await seed_store_for_seller(db, seller)
    await seed_product(db, seller, store, name="NoDriver")

    await seed_driver(db, "driver_vis@example.com")
    d_token = await _login(client, "driver_vis@example.com", "DriverPass123!")
    resp = await client.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {d_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


async def test_driver_404_on_product_detail(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "driver_prod_s@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store)

    await seed_driver(db, "driver_prod@example.com")
    d_token = await _login(client, "driver_prod@example.com", "DriverPass123!")
    resp = await client.get(
        f"/api/v1/products/{product.id}",
        headers={"Authorization": f"Bearer {d_token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Admin sees everything
# ---------------------------------------------------------------------------


async def test_admin_sees_all_products(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller_a = await seed_seller_with_profile(db, "admin_sees_a@example.com")
    store_a = await seed_store_for_seller(db, seller_a)
    await seed_product(db, seller_a, store_a, name="A")

    seller_b = await seed_seller_with_profile(db, "admin_sees_b@example.com")
    store_b = await seed_store_for_seller(db, seller_b)
    await seed_product(db, seller_b, store_b, name="B")

    await seed_admin(db, "admin_sees@example.com")
    token = await _login(client, "admin_sees@example.com", "AdminPass123!")
    resp = await client.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    names = sorted([i["name"] for i in resp.json()["data"]])
    assert "A" in names and "B" in names
