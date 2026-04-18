"""Order cancellation rules.

- Customer: cancel pending only.
- Seller: cancel pending / accepted / preparing.
- Admin: any pre-delivery state (incl. out_for_delivery).
- Post-out_for_delivery non-admin actors → 409.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    seed_admin,
    seed_customer,
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


async def _setup(db, tag: str):
    seller = await seed_seller_with_profile(db, f"seller_{tag}@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=1000, stock_quantity=10)
    customer = await seed_customer(
        db, f"customer_{tag}@example.com", referring_seller_id=seller.id
    )
    admin = await seed_admin(db, f"admin_{tag}@example.com")
    return seller, store, product, customer, admin


async def _place(client, c_token, product_id):
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "delivery_address": {"line1": "a", "city": "b", "country": "US"},
        },
        headers=_h(c_token),
    )
    assert r.status_code == 201
    return r.json()


async def test_customer_cancels_pending_order(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "cc1")
    c_token = await _login(client, "customer_cc1@example.com", "CustomerPass123!")
    order = await _place(client, c_token, str(product.id))
    r = await client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        json={"reason": "changed my mind"},
        headers=_h(c_token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


async def test_customer_cannot_cancel_after_accept(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "cc2")
    s_token = await _login(client, "seller_cc2@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_cc2@example.com", "CustomerPass123!")
    order = await _place(client, c_token, str(product.id))
    await client.post(f"/api/v1/orders/{order['id']}/accept", headers=_h(s_token))
    r = await client.post(
        f"/api/v1/orders/{order['id']}/cancel", headers=_h(c_token)
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_INVALID_TRANSITION"


async def test_seller_cancels_accepted(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "cc3")
    s_token = await _login(client, "seller_cc3@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_cc3@example.com", "CustomerPass123!")
    order = await _place(client, c_token, str(product.id))
    await client.post(f"/api/v1/orders/{order['id']}/accept", headers=_h(s_token))
    r = await client.post(
        f"/api/v1/orders/{order['id']}/cancel", headers=_h(s_token)
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


async def test_seller_cannot_cancel_after_out_for_delivery(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "cc4")
    s_token = await _login(client, "seller_cc4@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_cc4@example.com", "CustomerPass123!")
    order = await _place(client, c_token, str(product.id))
    for step in ("accept", "preparing", "self-deliver", "out-for-delivery"):
        r = await client.post(f"/api/v1/orders/{order['id']}/{step}", headers=_h(s_token))
        assert r.status_code == 200, (step, r.text)
    r = await client.post(
        f"/api/v1/orders/{order['id']}/cancel", headers=_h(s_token)
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_INVALID_TRANSITION"


async def test_admin_can_cancel_out_for_delivery(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "cc5")
    s_token = await _login(client, "seller_cc5@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_cc5@example.com", "CustomerPass123!")
    a_token = await _login(client, "admin_cc5@example.com", "AdminPass123!")
    order = await _place(client, c_token, str(product.id))
    for step in ("accept", "preparing", "self-deliver", "out-for-delivery"):
        r = await client.post(f"/api/v1/orders/{order['id']}/{step}", headers=_h(s_token))
        assert r.status_code == 200, (step, r.text)
    r = await client.post(
        f"/api/v1/orders/{order['id']}/cancel", headers=_h(a_token)
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


async def test_cannot_cancel_after_delivered(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "cc6")
    s_token = await _login(client, "seller_cc6@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_cc6@example.com", "CustomerPass123!")
    a_token = await _login(client, "admin_cc6@example.com", "AdminPass123!")
    order = await _place(client, c_token, str(product.id))
    for step in ("accept", "preparing", "self-deliver", "out-for-delivery", "delivered"):
        r = await client.post(f"/api/v1/orders/{order['id']}/{step}", headers=_h(s_token))
        assert r.status_code == 200, (step, r.text)
    # Even admin cannot cancel a delivered order
    r = await client.post(
        f"/api/v1/orders/{order['id']}/cancel", headers=_h(a_token)
    )
    assert r.status_code == 409
