"""Purge job tests.

- Hard-deletes orders whose terminal_at is older than retention.
- Preserves analytics snapshots.
- Does not touch non-terminal orders.
- Idempotent.
- Auto-completes delivered orders older than grace period.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.order_analytics_snapshot import OrderAnalyticsSnapshot
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
    product = await seed_product(db, seller, store, price_minor=500, stock_quantity=100)
    customer = await seed_customer(
        db, f"customer_{tag}@example.com", referring_seller_id=seller.id
    )
    admin = await seed_admin(db, f"admin_{tag}@example.com")
    return seller, store, product, customer, admin


async def _place(client, c_token, pid):
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": pid, "quantity": 1}],
            "delivery_address": {"line1": "a", "city": "b", "country": "US"},
        },
        headers=_h(c_token),
    )
    assert r.status_code == 201
    return r.json()


async def _complete(client, oid, s_token, c_token):
    for step in ("accept", "preparing", "self-deliver", "out-for-delivery", "delivered"):
        r = await client.post(f"/api/v1/orders/{oid}/{step}", headers=_h(s_token))
        assert r.status_code == 200
    r = await client.post(f"/api/v1/orders/{oid}/complete", headers=_h(c_token))
    assert r.status_code == 200


async def _age_terminal_at(db: AsyncSession, oid: UUID, days: int) -> None:
    past = datetime.now(timezone.utc) - timedelta(days=days)
    await db.execute(
        sa.update(Order).where(Order.id == oid).values(
            completed_at=past, cancelled_at=past
        )
    )
    await db.flush()


async def test_purge_removes_eligible_orders(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "p1")
    s_token = await _login(client, "seller_p1@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_p1@example.com", "CustomerPass123!")
    a_token = await _login(client, "admin_p1@example.com", "AdminPass123!")

    order = await _place(client, c_token, str(product.id))
    await _complete(client, order["id"], s_token, c_token)
    await _age_terminal_at(db, UUID(order["id"]), days=45)

    r = await client.post("/api/v1/admin/jobs/purge-orders", headers=_h(a_token))
    assert r.status_code == 200
    body = r.json()
    assert body["purged_count"] == 1

    # Order gone, snapshot intact
    gone = (
        await db.execute(sa.select(Order).where(Order.id == UUID(order["id"])))
    ).scalar_one_or_none()
    assert gone is None
    snap = (
        await db.execute(
            sa.select(OrderAnalyticsSnapshot).where(
                OrderAnalyticsSnapshot.order_id == UUID(order["id"])
            )
        )
    ).scalar_one_or_none()
    assert snap is not None


async def test_purge_ignores_non_terminal_orders(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "p2")
    c_token = await _login(client, "customer_p2@example.com", "CustomerPass123!")
    a_token = await _login(client, "admin_p2@example.com", "AdminPass123!")

    order = await _place(client, c_token, str(product.id))
    r = await client.post("/api/v1/admin/jobs/purge-orders", headers=_h(a_token))
    assert r.status_code == 200
    assert r.json()["purged_count"] == 0

    # Still alive
    row = (
        await db.execute(sa.select(Order).where(Order.id == UUID(order["id"])))
    ).scalar_one_or_none()
    assert row is not None


async def test_purge_idempotent(client: AsyncClient, db: AsyncSession) -> None:
    _, _, product, _, _ = await _setup(db, "p3")
    s_token = await _login(client, "seller_p3@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_p3@example.com", "CustomerPass123!")
    a_token = await _login(client, "admin_p3@example.com", "AdminPass123!")

    order = await _place(client, c_token, str(product.id))
    await _complete(client, order["id"], s_token, c_token)
    await _age_terminal_at(db, UUID(order["id"]), days=45)

    r1 = await client.post("/api/v1/admin/jobs/purge-orders", headers=_h(a_token))
    r2 = await client.post("/api/v1/admin/jobs/purge-orders", headers=_h(a_token))
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["purged_count"] == 1
    assert r2.json()["purged_count"] == 0


async def test_purge_auto_completes_old_delivered(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "p4")
    s_token = await _login(client, "seller_p4@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_p4@example.com", "CustomerPass123!")
    a_token = await _login(client, "admin_p4@example.com", "AdminPass123!")

    order = await _place(client, c_token, str(product.id))
    oid = UUID(order["id"])
    for step in ("accept", "preparing", "self-deliver", "out-for-delivery", "delivered"):
        r = await client.post(f"/api/v1/orders/{order['id']}/{step}", headers=_h(s_token))
        assert r.status_code == 200

    # Age delivered_at past the 72h default grace
    past = datetime.now(timezone.utc) - timedelta(hours=100)
    await db.execute(
        sa.update(Order).where(Order.id == oid).values(delivered_at=past)
    )
    await db.flush()

    r = await client.post("/api/v1/admin/jobs/purge-orders", headers=_h(a_token))
    assert r.status_code == 200
    body = r.json()
    assert body["auto_completed_count"] == 1

    # Order is now completed and snapshot exists
    row = (
        await db.execute(sa.select(Order).where(Order.id == oid))
    ).scalar_one()
    assert row.status == "completed"
    assert row.completed_at is not None

    snap = (
        await db.execute(
            sa.select(OrderAnalyticsSnapshot).where(
                OrderAnalyticsSnapshot.order_id == oid
            )
        )
    ).scalar_one_or_none()
    assert snap is not None


async def test_non_admin_cannot_trigger_purge(
    client: AsyncClient, db: AsyncSession
) -> None:
    await _setup(db, "p5")
    s_token = await _login(client, "seller_p5@example.com", "SellerPass123!")
    r = await client.post("/api/v1/admin/jobs/purge-orders", headers=_h(s_token))
    assert r.status_code == 403
