"""Order visibility tests.

- Customer sees only their own orders.
- Seller sees only orders against their own store.
- Driver sees only orders they are assigned to.
- Unrelated users receive 404 (not 403) on GET /orders/{id}.
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


async def _login(client: AsyncClient, email: str, pw: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def _place(client, c_token, pid):
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "delivery_address": {"line1": "a", "city": "b", "country": "US"},
        },
        headers=_h(c_token),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_customer_sees_only_own_orders(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "seller_v1@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=500, stock_quantity=10)
    await seed_customer(db, "cust_v1a@example.com", referring_seller_id=seller.id)
    await seed_customer(db, "cust_v1b@example.com", referring_seller_id=seller.id)

    tok_a = await _login(client, "cust_v1a@example.com", "CustomerPass123!")
    tok_b = await _login(client, "cust_v1b@example.com", "CustomerPass123!")

    order_a = await _place(client, tok_a, str(product.id))

    # Customer B gets 404 on A's order
    r = await client.get(f"/api/v1/orders/{order_a['id']}", headers=_h(tok_b))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ORDER_NOT_FOUND"

    # Customer B's list does not contain A's order
    r = await client.get("/api/v1/orders", headers=_h(tok_b))
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()["data"]]
    assert order_a["id"] not in ids


async def test_seller_sees_only_own_store_orders(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller_a = await seed_seller_with_profile(db, "seller_v2a@example.com")
    store_a = await seed_store_for_seller(db, seller_a, slug="store-v2a")
    product_a = await seed_product(db, seller_a, store_a, price_minor=500, stock_quantity=10)
    await seed_customer(db, "cust_v2a@example.com", referring_seller_id=seller_a.id)

    seller_b = await seed_seller_with_profile(db, "seller_v2b@example.com")
    await seed_store_for_seller(db, seller_b, slug="store-v2b")

    tok_cust = await _login(client, "cust_v2a@example.com", "CustomerPass123!")
    tok_b = await _login(client, "seller_v2b@example.com", "SellerPass123!")

    order_a = await _place(client, tok_cust, str(product_a.id))

    # Seller B cannot see seller A's order
    r = await client.get(f"/api/v1/orders/{order_a['id']}", headers=_h(tok_b))
    assert r.status_code == 404

    # Seller B's list is empty
    r = await client.get("/api/v1/orders", headers=_h(tok_b))
    assert r.status_code == 200
    assert r.json()["data"] == []


async def test_driver_sees_only_assigned(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "seller_v3@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=500, stock_quantity=10)
    await seed_customer(db, "cust_v3@example.com", referring_seller_id=seller.id)
    admin = await seed_admin(db, "admin_v3@example.com")
    driver_assigned = await seed_driver(db, "driver_v3a@example.com")
    await seed_driver(db, "driver_v3b@example.com")

    s_tok = await _login(client, "seller_v3@example.com", "SellerPass123!")
    c_tok = await _login(client, "cust_v3@example.com", "CustomerPass123!")
    a_tok = await _login(client, "admin_v3@example.com", "AdminPass123!")
    d_tok_assigned = await _login(client, "driver_v3a@example.com", "DriverPass123!")
    d_tok_other = await _login(client, "driver_v3b@example.com", "DriverPass123!")

    order = await _place(client, c_tok, str(product.id))
    oid = order["id"]
    await client.post(f"/api/v1/orders/{oid}/accept", headers=_h(s_tok))
    await client.post(f"/api/v1/orders/{oid}/preparing", headers=_h(s_tok))
    await client.post(f"/api/v1/orders/{oid}/request-driver", headers=_h(s_tok))
    r = await client.post(
        f"/api/v1/admin/orders/{oid}/assign-driver",
        json={"driver_id": str(driver_assigned.id)},
        headers=_h(a_tok),
    )
    assert r.status_code == 200, r.text

    # Assigned driver can see it
    r = await client.get(f"/api/v1/orders/{oid}", headers=_h(d_tok_assigned))
    assert r.status_code == 200

    # Other driver gets 404
    r = await client.get(f"/api/v1/orders/{oid}", headers=_h(d_tok_other))
    assert r.status_code == 404

    # Other driver's list is empty
    r = await client.get("/api/v1/orders", headers=_h(d_tok_other))
    assert r.status_code == 200
    assert r.json()["data"] == []


async def test_admin_sees_all_orders(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "seller_v4@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=500, stock_quantity=10)
    await seed_customer(db, "cust_v4@example.com", referring_seller_id=seller.id)
    await seed_admin(db, "admin_v4@example.com")

    c_tok = await _login(client, "cust_v4@example.com", "CustomerPass123!")
    a_tok = await _login(client, "admin_v4@example.com", "AdminPass123!")

    order = await _place(client, c_tok, str(product.id))

    r = await client.get(f"/api/v1/orders/{order['id']}", headers=_h(a_tok))
    assert r.status_code == 200
    r = await client.get("/api/v1/orders", headers=_h(a_tok))
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()["data"]]
    assert order["id"] in ids
