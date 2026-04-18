"""Tests for /sellers/me/dashboard aggregates.

Covers:
- lifetime_sales_amount and lifetime_orders_count read from
  order_analytics_snapshots — survive product soft-delete AND order
  hard-delete (since snapshots have no FKs).
- active_orders_count moves correctly across state transitions
  (pending → accepted → preparing → out_for_delivery → delivered; delivered
  drops it from the active set).
- Customer / driver cannot access the seller dashboard.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.order_analytics_snapshot import OrderAnalyticsSnapshot
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


def _snapshot(
    *,
    seller_id: uuid.UUID,
    store_id: uuid.UUID,
    customer_id: uuid.UUID,
    total_minor: int,
    subtotal_minor: int | None = None,
    city: str = "TestCity",
    item_count: int = 1,
) -> OrderAnalyticsSnapshot:
    return OrderAnalyticsSnapshot(
        id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        seller_id=seller_id,
        store_id=store_id,
        customer_id=customer_id,
        city=city,
        item_count=item_count,
        subtotal_minor=subtotal_minor if subtotal_minor is not None else total_minor,
        total_minor=total_minor,
        delivered_at=datetime.now(timezone.utc),
    )


def _order(
    *,
    seller_id: uuid.UUID,
    store_id: uuid.UUID,
    customer_id: uuid.UUID,
    status: str,
    total_minor: int = 1000,
) -> Order:
    return Order(
        id=uuid.uuid4(),
        customer_id=customer_id,
        seller_id=seller_id,
        store_id=store_id,
        status=status,
        subtotal_minor=total_minor,
        total_minor=total_minor,
        delivery_address={
            "line1": "1 Main",
            "city": "TestCity",
            "country": "US",
        },
    )


# ---------------------------------------------------------------------------
# Lifetime sales persistence across product soft-delete
# ---------------------------------------------------------------------------


async def test_lifetime_sales_survive_product_soft_delete(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "dash_soft_s@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store)
    customer = await seed_customer(
        db, "dash_soft_c@example.com", referring_seller_id=seller.id
    )

    # Seed 2 snapshots totalling 5500 minor units
    db.add(
        _snapshot(
            seller_id=seller.id,
            store_id=store.id,
            customer_id=customer.id,
            total_minor=3000,
        )
    )
    db.add(
        _snapshot(
            seller_id=seller.id,
            store_id=store.id,
            customer_id=customer.id,
            total_minor=2500,
        )
    )
    await db.flush()

    s_token = await _login(client, "dash_soft_s@example.com", "SellerPass123!")

    # Soft-delete the product (via the API)
    del_resp = await client.delete(
        f"/api/v1/products/{product.id}",
        headers={"Authorization": f"Bearer {s_token}"},
    )
    assert del_resp.status_code == 204

    resp = await client.get(
        "/api/v1/sellers/me/dashboard",
        headers={"Authorization": f"Bearer {s_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["lifetime_sales_amount"] == 5500
    assert body["lifetime_orders_count"] == 2


# ---------------------------------------------------------------------------
# Lifetime sales persistence across order hard-delete
# ---------------------------------------------------------------------------


async def test_lifetime_sales_survive_order_hard_delete(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Snapshots have no FK to orders, so deleting the order row leaves them intact."""
    seller = await seed_seller_with_profile(db, "dash_hard_s@example.com")
    store = await seed_store_for_seller(db, seller)
    customer = await seed_customer(
        db, "dash_hard_c@example.com", referring_seller_id=seller.id
    )

    # Create an order and its snapshot, then admin-hard-delete the order row
    # directly (simulating retention-job purge past the retention minimum).
    order = _order(
        seller_id=seller.id,
        store_id=store.id,
        customer_id=customer.id,
        status="delivered",
        total_minor=1234,
    )
    db.add(order)
    await db.flush()

    snap = _snapshot(
        seller_id=seller.id,
        store_id=store.id,
        customer_id=customer.id,
        total_minor=1234,
    )
    snap.order_id = order.id
    db.add(snap)
    await db.flush()

    # Hard-delete the order row — simulating retention purge.
    await db.execute(delete(Order).where(Order.id == order.id))
    await db.flush()

    s_token = await _login(client, "dash_hard_s@example.com", "SellerPass123!")
    resp = await client.get(
        "/api/v1/sellers/me/dashboard",
        headers={"Authorization": f"Bearer {s_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["lifetime_sales_amount"] == 1234
    assert body["lifetime_orders_count"] == 1


# ---------------------------------------------------------------------------
# Active orders count across state transitions
# ---------------------------------------------------------------------------


async def test_active_orders_count_transitions(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "dash_active_s@example.com")
    store = await seed_store_for_seller(db, seller)
    customer = await seed_customer(
        db, "dash_active_c@example.com", referring_seller_id=seller.id
    )

    # Seed active-state orders + terminal ones
    pending = _order(
        seller_id=seller.id,
        store_id=store.id,
        customer_id=customer.id,
        status="pending",
    )
    accepted = _order(
        seller_id=seller.id,
        store_id=store.id,
        customer_id=customer.id,
        status="accepted",
    )
    preparing = _order(
        seller_id=seller.id,
        store_id=store.id,
        customer_id=customer.id,
        status="preparing",
    )
    ofd = _order(
        seller_id=seller.id,
        store_id=store.id,
        customer_id=customer.id,
        status="out_for_delivery",
    )
    delivered = _order(
        seller_id=seller.id,
        store_id=store.id,
        customer_id=customer.id,
        status="delivered",
    )
    cancelled = _order(
        seller_id=seller.id,
        store_id=store.id,
        customer_id=customer.id,
        status="cancelled",
    )
    for o in (pending, accepted, preparing, ofd, delivered, cancelled):
        db.add(o)
    await db.flush()

    s_token = await _login(client, "dash_active_s@example.com", "SellerPass123!")
    resp = await client.get(
        "/api/v1/sellers/me/dashboard",
        headers={"Authorization": f"Bearer {s_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["active_orders_count"] == 4

    # Transition pending → cancelled: active drops by 1.
    pending.status = "cancelled"
    pending.cancelled_at = datetime.now(timezone.utc)
    await db.flush()

    resp2 = await client.get(
        "/api/v1/sellers/me/dashboard",
        headers={"Authorization": f"Bearer {s_token}"},
    )
    assert resp2.json()["active_orders_count"] == 3

    # Transition out_for_delivery → delivered: drops by 1.
    ofd.status = "delivered"
    ofd.delivered_at = datetime.now(timezone.utc)
    await db.flush()

    resp3 = await client.get(
        "/api/v1/sellers/me/dashboard",
        headers={"Authorization": f"Bearer {s_token}"},
    )
    assert resp3.json()["active_orders_count"] == 2


# ---------------------------------------------------------------------------
# RBAC on dashboard
# ---------------------------------------------------------------------------


async def test_customer_cannot_access_dashboard(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_customer(db, "dash_cust@example.com")
    token = await _login(client, "dash_cust@example.com", "CustomerPass123!")
    resp = await client.get(
        "/api/v1/sellers/me/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_driver_cannot_access_dashboard(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_driver(db, "dash_drv@example.com")
    token = await _login(client, "dash_drv@example.com", "DriverPass123!")
    resp = await client.get(
        "/api/v1/sellers/me/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_admin_can_view_any_sellers_dashboard(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "dash_admin_s@example.com")
    store = await seed_store_for_seller(db, seller)
    customer = await seed_customer(
        db, "dash_admin_c@example.com", referring_seller_id=seller.id
    )
    db.add(
        _snapshot(
            seller_id=seller.id,
            store_id=store.id,
            customer_id=customer.id,
            total_minor=999,
        )
    )
    await db.flush()

    await seed_admin(db, "dash_admin@example.com")
    token = await _login(client, "dash_admin@example.com", "AdminPass123!")
    resp = await client.get(
        f"/api/v1/sellers/{seller.id}/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["lifetime_sales_amount"] == 999


async def test_seller_cannot_view_other_sellers_dashboard(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller_a = await seed_seller_with_profile(db, "dash_iso_a@example.com")
    await seed_seller_with_profile(db, "dash_iso_b@example.com")
    b_token = await _login(client, "dash_iso_b@example.com", "SellerPass123!")
    resp = await client.get(
        f"/api/v1/sellers/{seller_a.id}/dashboard",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    # Admin-only endpoint → 403
    assert resp.status_code == 403
