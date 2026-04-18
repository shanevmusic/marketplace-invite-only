"""End-to-end order lifecycle tests.

Covers:
- Happy path self-deliver: place → accept → preparing → self-deliver →
  out_for_delivery → delivered → complete.
- Happy path driver: place → accept → preparing → request-driver →
  admin-assign → out_for_delivery → delivered → complete.
- Out-for-delivery idempotency: second call → 409 DELIVERY_ALREADY_STARTED.
- Invalid transitions: e.g. accepted → out_for_delivery (skipping preparing).
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


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _address() -> dict:
    return {
        "line1": "1 Market St",
        "city": "Metro",
        "country": "US",
    }


async def _place_order(
    client: AsyncClient, cust_token: str, product_id: str, qty: int = 1
) -> dict:
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": product_id, "quantity": qty}],
            "delivery_address": _address(),
        },
        headers=_h(cust_token),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _build_seller_and_customer(db, email_suffix: str):
    seller = await seed_seller_with_profile(db, f"seller_{email_suffix}@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=5000, stock_quantity=10)
    customer = await seed_customer(
        db, f"customer_{email_suffix}@example.com", referring_seller_id=seller.id
    )
    return seller, store, product, customer


# ---------------------------------------------------------------------------
# Happy path — self-deliver
# ---------------------------------------------------------------------------


async def test_full_lifecycle_self_deliver(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, store, product, customer = await _build_seller_and_customer(db, "life1")
    s_token = await _login(client, "seller_life1@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_life1@example.com", "CustomerPass123!")

    order = await _place_order(client, c_token, str(product.id), qty=2)
    oid = order["id"]
    assert order["status"] == "pending"
    assert order["subtotal_minor"] == 10000
    assert order["total_minor"] == 10000
    assert len(order["items"]) == 1

    # Seller accepts
    r = await client.post(f"/api/v1/orders/{oid}/accept", headers=_h(s_token))
    assert r.status_code == 200 and r.json()["status"] == "accepted"

    # Preparing
    r = await client.post(f"/api/v1/orders/{oid}/preparing", headers=_h(s_token))
    assert r.status_code == 200 and r.json()["status"] == "preparing"

    # Self-deliver
    r = await client.post(f"/api/v1/orders/{oid}/self-deliver", headers=_h(s_token))
    assert r.status_code == 200
    body = r.json()
    assert body["delivery"]["driver_id"] is None

    # Out for delivery
    r = await client.post(
        f"/api/v1/orders/{oid}/out-for-delivery", headers=_h(s_token)
    )
    assert r.status_code == 200 and r.json()["status"] == "out_for_delivery"

    # Delivered
    r = await client.post(f"/api/v1/orders/{oid}/delivered", headers=_h(s_token))
    assert r.status_code == 200 and r.json()["status"] == "delivered"

    # Customer completes
    r = await client.post(f"/api/v1/orders/{oid}/complete", headers=_h(c_token))
    assert r.status_code == 200 and r.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# Happy path — driver assigned
# ---------------------------------------------------------------------------


async def test_full_lifecycle_with_driver(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, store, product, customer = await _build_seller_and_customer(db, "life2")
    admin = await seed_admin(db, "admin_life2@example.com")
    driver = await seed_driver(db, "driver_life2@example.com")

    s_token = await _login(client, "seller_life2@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_life2@example.com", "CustomerPass123!")
    a_token = await _login(client, "admin_life2@example.com", "AdminPass123!")
    d_token = await _login(client, "driver_life2@example.com", "DriverPass123!")

    order = await _place_order(client, c_token, str(product.id))
    oid = order["id"]

    # Seller accepts + preparing
    r = await client.post(f"/api/v1/orders/{oid}/accept", headers=_h(s_token))
    assert r.status_code == 200
    r = await client.post(f"/api/v1/orders/{oid}/preparing", headers=_h(s_token))
    assert r.status_code == 200

    # Seller requests a driver
    r = await client.post(f"/api/v1/orders/{oid}/request-driver", headers=_h(s_token))
    assert r.status_code == 200
    assert r.json()["driver_assignment"]["status"] == "requested"

    # Admin assigns driver
    r = await client.post(
        f"/api/v1/admin/orders/{oid}/assign-driver",
        json={"driver_id": str(driver.id)},
        headers=_h(a_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["driver_assignment"]["status"] == "assigned"
    assert body["driver_assignment"]["driver_id"] == str(driver.id)

    # Driver triggers out-for-delivery (ADR-0003)
    r = await client.post(
        f"/api/v1/orders/{oid}/out-for-delivery", headers=_h(d_token)
    )
    assert r.status_code == 200 and r.json()["status"] == "out_for_delivery"

    # Driver marks delivered
    r = await client.post(f"/api/v1/orders/{oid}/delivered", headers=_h(d_token))
    assert r.status_code == 200 and r.json()["status"] == "delivered"

    # Customer completes
    r = await client.post(f"/api/v1/orders/{oid}/complete", headers=_h(c_token))
    assert r.status_code == 200 and r.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# Idempotency on out-for-delivery
# ---------------------------------------------------------------------------


async def test_out_for_delivery_idempotent_409(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, store, product, customer = await _build_seller_and_customer(db, "idem1")
    s_token = await _login(client, "seller_idem1@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_idem1@example.com", "CustomerPass123!")

    order = await _place_order(client, c_token, str(product.id))
    oid = order["id"]
    await client.post(f"/api/v1/orders/{oid}/accept", headers=_h(s_token))
    await client.post(f"/api/v1/orders/{oid}/preparing", headers=_h(s_token))
    await client.post(f"/api/v1/orders/{oid}/self-deliver", headers=_h(s_token))
    r = await client.post(
        f"/api/v1/orders/{oid}/out-for-delivery", headers=_h(s_token)
    )
    assert r.status_code == 200
    r2 = await client.post(
        f"/api/v1/orders/{oid}/out-for-delivery", headers=_h(s_token)
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "DELIVERY_ALREADY_STARTED"


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


async def test_invalid_transition_skipping_preparing(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, store, product, customer = await _build_seller_and_customer(db, "inv1")
    s_token = await _login(client, "seller_inv1@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_inv1@example.com", "CustomerPass123!")

    order = await _place_order(client, c_token, str(product.id))
    oid = order["id"]
    await client.post(f"/api/v1/orders/{oid}/accept", headers=_h(s_token))
    r = await client.post(
        f"/api/v1/orders/{oid}/out-for-delivery", headers=_h(s_token)
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_INVALID_TRANSITION"


async def test_cannot_complete_before_delivered(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, store, product, customer = await _build_seller_and_customer(db, "inv2")
    s_token = await _login(client, "seller_inv2@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_inv2@example.com", "CustomerPass123!")

    order = await _place_order(client, c_token, str(product.id))
    oid = order["id"]
    await client.post(f"/api/v1/orders/{oid}/accept", headers=_h(s_token))
    r = await client.post(f"/api/v1/orders/{oid}/complete", headers=_h(c_token))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_INVALID_TRANSITION"


async def test_cannot_set_fulfillment_twice(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller, store, product, customer = await _build_seller_and_customer(db, "inv3")
    s_token = await _login(client, "seller_inv3@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_inv3@example.com", "CustomerPass123!")

    order = await _place_order(client, c_token, str(product.id))
    oid = order["id"]
    await client.post(f"/api/v1/orders/{oid}/accept", headers=_h(s_token))
    r = await client.post(f"/api/v1/orders/{oid}/self-deliver", headers=_h(s_token))
    assert r.status_code == 200
    r2 = await client.post(
        f"/api/v1/orders/{oid}/request-driver", headers=_h(s_token)
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "FULFILLMENT_ALREADY_CHOSEN"


async def test_analytics_snapshot_created_on_complete(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Verify snapshot row is written at completed-transition."""
    from sqlalchemy import select

    from app.models.order_analytics_snapshot import OrderAnalyticsSnapshot

    seller, store, product, customer = await _build_seller_and_customer(db, "snap1")
    s_token = await _login(client, "seller_snap1@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_snap1@example.com", "CustomerPass123!")

    order = await _place_order(client, c_token, str(product.id), qty=3)
    oid = order["id"]
    for step in ("accept", "preparing", "self-deliver", "out-for-delivery", "delivered"):
        r = await client.post(f"/api/v1/orders/{oid}/{step}", headers=_h(s_token))
        assert r.status_code == 200, (step, r.text)
    r = await client.post(f"/api/v1/orders/{oid}/complete", headers=_h(c_token))
    assert r.status_code == 200

    result = await db.execute(
        select(OrderAnalyticsSnapshot).where(OrderAnalyticsSnapshot.order_id == order["id"])
    )
    rows = list(result.scalars().all())
    assert len(rows) == 1
    snap = rows[0]
    assert snap.total_minor == 15000  # 3 * 5000
    assert snap.item_count == 3
