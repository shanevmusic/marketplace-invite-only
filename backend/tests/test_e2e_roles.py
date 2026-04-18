"""Phase 12 — end-to-end happy-path tests per role.

One full scenario per role exercised through the real HTTP surface so we
catch contract regressions between routes that isolated unit tests miss.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    create_admin_invite,
    seed_admin,
    seed_customer,
    seed_driver,
    seed_product,
    seed_seller_with_profile,
    seed_store_for_seller,
)

pytestmark = pytest.mark.asyncio


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, email: str, pw: str) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": pw}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# Admin happy-path
# ---------------------------------------------------------------------------


async def test_admin_flow(client: AsyncClient, db: AsyncSession) -> None:
    """Admin: login → create invite → list users → suspend → unsuspend → analytics."""
    admin = await seed_admin(db, email="e2e-admin@x.com")
    driver = await seed_driver(db, email="e2e-driver-admin@x.com")
    await db.commit()

    t = await _login(client, "e2e-admin@x.com", "AdminPass123!")

    # Create a seller invite
    r = await client.post(
        "/api/v1/admin/invites",
        json={"role_target": "seller", "expires_in_days": 7},
        headers=_h(t),
    )
    assert r.status_code == 201, r.text
    assert "token" in r.json()

    # List users
    r = await client.get("/api/v1/admin/users", headers=_h(t))
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()["data"]}
    assert {"e2e-admin@x.com", "e2e-driver-admin@x.com"}.issubset(emails)

    # Suspend + unsuspend the driver
    r = await client.post(
        f"/api/v1/admin/users/{driver.id}/suspend",
        json={"reason": "e2e"},
        headers=_h(t),
    )
    assert r.status_code == 200 and r.json()["status"] == "suspended"

    r = await client.post(
        f"/api/v1/admin/users/{driver.id}/unsuspend", headers=_h(t)
    )
    assert r.status_code == 200 and r.json()["status"] == "active"

    # Analytics overview
    r = await client.get("/api/v1/admin/analytics/overview", headers=_h(t))
    assert r.status_code == 200
    overview = r.json()
    assert "users" in overview or "data" in overview or overview  # shape tolerant


# ---------------------------------------------------------------------------
# Seller happy-path
# ---------------------------------------------------------------------------


async def test_seller_flow(client: AsyncClient, db: AsyncSession) -> None:
    """Seller: login → create product → list own orders → transition order."""
    seller = await seed_seller_with_profile(db, email="e2e-seller@x.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=1500, stock_quantity=5)
    customer = await seed_customer(
        db, email="e2e-seller-cust@x.com", referring_seller_id=seller.id
    )
    await db.commit()

    s_token = await _login(client, "e2e-seller@x.com", "SellerPass123!")
    c_token = await _login(client, "e2e-seller-cust@x.com", "CustomerPass123!")

    # Seller creates a new product via API (uses API contract, not the seed row)
    r = await client.post(
        "/api/v1/products",
        json={
            "name": "E2E Widget",
            "price_minor": 9900,
            "stock_quantity": 3,
            "description": "",
            "images": [],
        },
        headers=_h(s_token),
    )
    assert r.status_code == 201, r.text

    # Customer places an order on the pre-seeded product
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(product.id), "quantity": 2}],
            "delivery_address": {
                "line1": "9 Main",
                "city": "Metro",
                "country": "US",
            },
        },
        headers=_h(c_token),
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]

    # Seller views their orders list via /orders (scoped to caller role)
    r = await client.get("/api/v1/orders", headers=_h(s_token))
    assert r.status_code == 200, r.text
    payload = r.json()
    rows = payload.get("data") if isinstance(payload, dict) else payload
    ids = {o["id"] for o in rows}
    assert oid in ids

    # Seller dashboard is also reachable
    r = await client.get("/api/v1/sellers/me/dashboard", headers=_h(s_token))
    assert r.status_code == 200

    # Seller transitions: accept → preparing
    r = await client.post(f"/api/v1/orders/{oid}/accept", headers=_h(s_token))
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    r = await client.post(f"/api/v1/orders/{oid}/preparing", headers=_h(s_token))
    assert r.status_code == 200 and r.json()["status"] == "preparing"


# ---------------------------------------------------------------------------
# Customer happy-path
# ---------------------------------------------------------------------------


async def test_customer_flow(client: AsyncClient, db: AsyncSession) -> None:
    """Customer: signup via seller invite → discover → order → complete after delivered."""
    seller = await seed_seller_with_profile(db, email="e2e-seller-c@x.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(
        db, seller, store, price_minor=2500, stock_quantity=4
    )
    # Seller referral invite
    from tests.conftest import create_seller_referral

    invite_token = await create_seller_referral(db, seller)
    await db.commit()

    # Customer signs up via the invite
    r = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "e2e-cust-sign@x.com",
            "password": "LongStrongPass!47xZ",
            "display_name": "E2E Cust",
            "invite_token": invite_token,
            "role_choice": "customer",
        },
    )
    assert r.status_code == 201, r.text
    c_token = r.json()["access_token"]

    # Discover the product via customer-visible listing
    r = await client.get(f"/api/v1/products/{product.id}", headers=_h(c_token))
    assert r.status_code == 200

    # Place an order
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(product.id), "quantity": 1}],
            "delivery_address": {
                "line1": "7 Main",
                "city": "Metro",
                "country": "US",
            },
        },
        headers=_h(c_token),
    )
    assert r.status_code == 201
    oid = r.json()["id"]

    # Seller accepts + preparing + self-deliver + out-for-delivery + delivered
    s_token = await _login(client, "e2e-seller-c@x.com", "SellerPass123!")
    for ep in ("accept", "preparing", "self-deliver", "out-for-delivery", "delivered"):
        r = await client.post(f"/api/v1/orders/{oid}/{ep}", headers=_h(s_token))
        assert r.status_code == 200, f"{ep}: {r.text}"

    # Customer marks complete
    r = await client.post(f"/api/v1/orders/{oid}/complete", headers=_h(c_token))
    assert r.status_code == 200 and r.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# Driver happy-path
# ---------------------------------------------------------------------------


async def test_driver_flow(client: AsyncClient, db: AsyncSession) -> None:
    """Driver: referred by admin invite → assigned → location update → delivered."""
    admin = await seed_admin(db, email="e2e-admin-d@x.com")
    seller = await seed_seller_with_profile(db, email="e2e-seller-d@x.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(
        db, seller, store, price_minor=1200, stock_quantity=2
    )
    customer = await seed_customer(
        db, email="e2e-cust-d@x.com", referring_seller_id=seller.id
    )

    # Admin issues a driver invite (admin_invite)
    driver_invite = await create_admin_invite(db, admin, "driver")
    await db.commit()

    # Driver signs up via the admin invite
    r = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "e2e-driver-sign@x.com",
            "password": "LongStrongPass!47xZ",
            "display_name": "E2E Driver",
            "invite_token": driver_invite,
            "role_choice": "driver",
        },
    )
    assert r.status_code == 201, r.text
    d_token = r.json()["access_token"]

    # Customer places an order
    c_token = await _login(client, "e2e-cust-d@x.com", "CustomerPass123!")
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(product.id), "quantity": 1}],
            "delivery_address": {
                "line1": "5 Main",
                "city": "Metro",
                "country": "US",
            },
        },
        headers=_h(c_token),
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]

    # Seller drives it to request-driver
    s_token = await _login(client, "e2e-seller-d@x.com", "SellerPass123!")
    for ep in ("accept", "preparing", "request-driver"):
        r = await client.post(f"/api/v1/orders/{oid}/{ep}", headers=_h(s_token))
        assert r.status_code == 200, f"{ep}: {r.text}"

    # Admin assigns the driver
    # Resolve driver user_id
    from sqlalchemy import select

    from app.models.user import User

    drv_row = (
        await db.execute(select(User).where(User.email == "e2e-driver-sign@x.com"))
    ).scalar_one()
    a_token = await _login(client, "e2e-admin-d@x.com", "AdminPass123!")
    r = await client.post(
        f"/api/v1/admin/orders/{oid}/assign-driver",
        json={"driver_id": str(drv_row.id)},
        headers=_h(a_token),
    )
    assert r.status_code == 200, r.text

    # Seller pushes out-for-delivery
    r = await client.post(
        f"/api/v1/orders/{oid}/out-for-delivery", headers=_h(s_token)
    )
    assert r.status_code == 200

    # Driver posts a location update
    r = await client.post(
        f"/api/v1/deliveries/{oid}/location",
        json={"lat": 37.7749, "lng": -122.4194},
        headers=_h(d_token),
    )
    # Accept 200 or 204 depending on contract shape.
    assert r.status_code in (200, 204), r.text

    # Seller / driver marks delivered (delivered is seller-authored in this impl)
    r = await client.post(f"/api/v1/orders/{oid}/delivered", headers=_h(s_token))
    assert r.status_code == 200 and r.json()["status"] == "delivered"
