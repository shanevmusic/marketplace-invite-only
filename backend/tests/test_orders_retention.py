"""Retention-gated hard-delete tests.

Uses direct SQL to age the terminal_at timestamps (completed_at /
cancelled_at) to simulate time passage (ADR-0012 D7).
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


async def _drive_order_to_completed(
    client: AsyncClient, oid: str, s_token: str, c_token: str
) -> None:
    for step in ("accept", "preparing", "self-deliver", "out-for-delivery", "delivered"):
        r = await client.post(f"/api/v1/orders/{oid}/{step}", headers=_h(s_token))
        assert r.status_code == 200, (step, r.text)
    r = await client.post(f"/api/v1/orders/{oid}/complete", headers=_h(c_token))
    assert r.status_code == 200


async def _age_terminal_at(
    db: AsyncSession, order_id: UUID, days: int
) -> None:
    past = datetime.now(timezone.utc) - timedelta(days=days)
    await db.execute(
        sa.update(Order)
        .where(Order.id == order_id)
        .values(completed_at=past, cancelled_at=past)
    )
    await db.flush()


async def _setup(db, tag: str):
    seller = await seed_seller_with_profile(db, f"seller_{tag}@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=2100, stock_quantity=10)
    customer = await seed_customer(
        db, f"customer_{tag}@example.com", referring_seller_id=seller.id
    )
    admin = await seed_admin(db, f"admin_{tag}@example.com")
    return seller, store, product, customer, admin


async def _place(client, c_token, product_id):
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 2}],
            "delivery_address": {"line1": "a", "city": "b", "country": "US"},
        },
        headers=_h(c_token),
    )
    assert r.status_code == 201
    return r.json()


async def test_cannot_delete_order_before_retention(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "ret1")
    s_token = await _login(client, "seller_ret1@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_ret1@example.com", "CustomerPass123!")
    order = await _place(client, c_token, str(product.id))
    oid = order["id"]
    await _drive_order_to_completed(client, oid, s_token, c_token)

    # Just completed — retention is 30 days, not met.
    r = await client.delete(f"/api/v1/orders/{oid}", headers=_h(c_token))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_RETENTION_NOT_MET"


async def test_cannot_delete_non_terminal_order(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "ret2")
    s_token = await _login(client, "seller_ret2@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_ret2@example.com", "CustomerPass123!")
    order = await _place(client, c_token, str(product.id))
    # Still pending
    r = await client.delete(f"/api/v1/orders/{order['id']}", headers=_h(c_token))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_RETENTION_NOT_MET"


async def test_admin_cannot_override_retention(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "ret3")
    s_token = await _login(client, "seller_ret3@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_ret3@example.com", "CustomerPass123!")
    a_token = await _login(client, "admin_ret3@example.com", "AdminPass123!")
    order = await _place(client, c_token, str(product.id))
    oid = order["id"]
    await _drive_order_to_completed(client, oid, s_token, c_token)

    # Admin cannot bypass retention (ADR-0012 D6)
    r = await client.delete(f"/api/v1/orders/{oid}", headers=_h(a_token))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_RETENTION_NOT_MET"


async def test_delete_after_retention_preserves_analytics(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "ret4")
    s_token = await _login(client, "seller_ret4@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_ret4@example.com", "CustomerPass123!")
    order = await _place(client, c_token, str(product.id))
    oid = order["id"]
    await _drive_order_to_completed(client, oid, s_token, c_token)

    # Age past retention
    await _age_terminal_at(db, UUID(oid), days=40)

    # Now delete succeeds
    r = await client.delete(f"/api/v1/orders/{oid}", headers=_h(c_token))
    assert r.status_code == 204, r.text

    # Snapshot still intact
    rows = (
        await db.execute(
            sa.select(OrderAnalyticsSnapshot).where(
                OrderAnalyticsSnapshot.order_id == UUID(oid)
            )
        )
    ).scalars().all()
    assert len(list(rows)) == 1

    # Order row gone
    gone = (
        await db.execute(sa.select(Order).where(Order.id == UUID(oid)))
    ).scalar_one_or_none()
    assert gone is None


async def test_seller_can_delete_after_retention(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "ret5")
    s_token = await _login(client, "seller_ret5@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_ret5@example.com", "CustomerPass123!")
    order = await _place(client, c_token, str(product.id))
    oid = order["id"]
    await _drive_order_to_completed(client, oid, s_token, c_token)
    await _age_terminal_at(db, UUID(oid), days=40)
    r = await client.delete(f"/api/v1/orders/{oid}", headers=_h(s_token))
    assert r.status_code == 204


async def test_cancelled_order_deleted_after_retention(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, _, product, _, _ = await _setup(db, "ret6")
    s_token = await _login(client, "seller_ret6@example.com", "SellerPass123!")
    c_token = await _login(client, "customer_ret6@example.com", "CustomerPass123!")
    order = await _place(client, c_token, str(product.id))
    oid = order["id"]
    # Cancel as customer
    r = await client.post(f"/api/v1/orders/{oid}/cancel", headers=_h(c_token))
    assert r.status_code == 200
    await _age_terminal_at(db, UUID(oid), days=40)
    r = await client.delete(f"/api/v1/orders/{oid}", headers=_h(c_token))
    assert r.status_code == 204
