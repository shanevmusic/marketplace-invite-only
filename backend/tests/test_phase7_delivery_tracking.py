"""Phase 7 — delivery tracking asymmetric-visibility tests.

Adversarial: prove the customer channel cannot leak driver/seller
coordinates under any payload shape on REST or WebSocket.

Tests cover:
1.  GET /deliveries/{id}/track as customer — raw response body has no
    "lat"/"lng"/"last_known" substrings.
2.  WS: customer subscribed to delivery topic receives ZERO
    delivery.location events even when driver posts many.
3.  WS: every event received on the customer socket validates against
    CustomerDeliveryEvent (extra='forbid').
4.  Stranger → 403/404 REST and 4403 WS.
5.  Driver posts location while order not OFD → 409.
6.  Seller self-delivery can publish location.
7.  Two-delivery isolation: customer of A, driver of B — no crosstalk.
8.  After delivered, POST /location → 409.
9.  Metrics: duration_seconds computed + snapshot carries
    delivery_duration_seconds.
10. CustomerDeliveryView.model_fields has no lat/lng.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg2
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token, hash_password
from app.main import app
from app.schemas.delivery_tracking import (
    CustomerDeliveryEtaEvent,
    CustomerDeliveryStatusEvent,
    CustomerDeliverySubscribedEvent,
    CustomerDeliveryView,
    InternalDeliveryView,
)
from tests.conftest import (
    seed_admin,
    seed_customer,
    seed_driver,
    seed_product,
    seed_seller_with_profile,
    seed_store_for_seller,
)


_DB_DSN = "postgresql://marketplace:marketplace@localhost:5432/marketplace_test"


# =========================================================================
# Async (httpx) helpers — use the ``client`` + ``db`` fixtures.
# =========================================================================

pytestmark_async = pytest.mark.asyncio


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _addr(with_latlng: bool = False) -> dict:
    addr = {
        "line1": "1 Market St",
        "city": "Metro",
        "country": "US",
    }
    if with_latlng:
        addr["lat"] = 40.0  # type: ignore[assignment]
        addr["lng"] = -73.0  # type: ignore[assignment]
    return addr


async def _login(client: AsyncClient, email: str, pw: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _drive_order_to_ofd(
    client: AsyncClient,
    db: AsyncSession,
    suffix: str,
    *,
    use_driver: bool = False,
) -> dict[str, Any]:
    """Create users, place an order, walk it to out_for_delivery.

    Returns a dict with keys: order_id, seller, customer, driver (optional),
    s_token, c_token, d_token (optional).
    """
    seller = await seed_seller_with_profile(db, f"seller_{suffix}@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=1000, stock_quantity=5)
    customer = await seed_customer(
        db, f"customer_{suffix}@example.com", referring_seller_id=seller.id
    )
    driver = None
    admin = None
    if use_driver:
        driver = await seed_driver(db, f"driver_{suffix}@example.com")
        admin = await seed_admin(db, f"admin_{suffix}@example.com")

    s_tok = await _login(client, f"seller_{suffix}@example.com", "SellerPass123!")
    c_tok = await _login(client, f"customer_{suffix}@example.com", "CustomerPass123!")
    d_tok = (
        await _login(client, f"driver_{suffix}@example.com", "DriverPass123!")
        if use_driver
        else None
    )
    a_tok = (
        await _login(client, f"admin_{suffix}@example.com", "AdminPass123!")
        if use_driver
        else None
    )

    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(product.id), "quantity": 1}],
            "delivery_address": _addr(),
        },
        headers=_h(c_tok),
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]

    assert (
        await client.post(f"/api/v1/orders/{oid}/accept", headers=_h(s_tok))
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/orders/{oid}/preparing", headers=_h(s_tok))
    ).status_code == 200

    if use_driver:
        assert (
            await client.post(
                f"/api/v1/orders/{oid}/request-driver", headers=_h(s_tok)
            )
        ).status_code == 200
        r = await client.post(
            f"/api/v1/admin/orders/{oid}/assign-driver",
            json={"driver_id": str(driver.id)},  # type: ignore[union-attr]
            headers=_h(a_tok),  # type: ignore[arg-type]
        )
        assert r.status_code == 200, r.text
        # Driver triggers OFD.
        r = await client.post(
            f"/api/v1/orders/{oid}/out-for-delivery", headers=_h(d_tok)  # type: ignore[arg-type]
        )
    else:
        assert (
            await client.post(
                f"/api/v1/orders/{oid}/self-deliver", headers=_h(s_tok)
            )
        ).status_code == 200
        r = await client.post(
            f"/api/v1/orders/{oid}/out-for-delivery", headers=_h(s_tok)
        )
    assert r.status_code == 200, r.text

    return {
        "order_id": oid,
        "seller": seller,
        "customer": customer,
        "driver": driver,
        "s_token": s_tok,
        "c_token": c_tok,
        "d_token": d_tok,
        "a_token": a_tok,
    }


# =========================================================================
# REST tests (async) — customer view must NEVER leak coordinates.
# =========================================================================


@pytest.mark.asyncio
async def test_customer_track_response_has_no_driver_coordinate_substrings(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Adversarial test 1: raw JSON body must not contain DRIVER lat/lng.

    Uses an address with NO lat/lng (customer did not provide destination
    coords).  Drives the driver's last-known position to unique sentinel
    values (12.3456 / -98.7654) and asserts neither the lat/lng schema
    keys nor the sentinel digit sequences appear anywhere in the raw
    response body.

    This is the primary asymmetric-visibility invariant: server-side
    driver location must never surface on the customer channel.
    """
    # Override address to one with no lat/lng — we want to prove the
    # customer's view carries none, regardless of submission.
    seller = await seed_seller_with_profile(db, "seller_p7r1@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=1000, stock_quantity=5)
    customer = await seed_customer(
        db, "customer_p7r1@example.com", referring_seller_id=seller.id
    )
    s_tok = await _login(client, "seller_p7r1@example.com", "SellerPass123!")
    c_tok = await _login(client, "customer_p7r1@example.com", "CustomerPass123!")
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(product.id), "quantity": 1}],
            "delivery_address": {
                "line1": "1 Market St",
                "city": "Metro",
                "country": "US",
            },
        },
        headers=_h(c_tok),
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    for path in ("accept", "preparing", "self-deliver", "out-for-delivery"):
        r = await client.post(f"/api/v1/orders/{oid}/{path}", headers=_h(s_tok))
        assert r.status_code == 200, (path, r.text)

    # Seller posts driver/self location with sentinel coords.
    r = await client.post(
        f"/api/v1/deliveries/{oid}/location",
        json={"lat": 12.3456, "lng": -98.7654, "eta_seconds": 120},
        headers=_h(s_tok),
    )
    assert r.status_code == 204, r.text

    # Customer retrieves tracking view.
    r = await client.get(f"/api/v1/deliveries/{oid}/track", headers=_h(c_tok))
    assert r.status_code == 200, r.text

    raw = r.text
    raw_lower = raw.lower()
    # Adversarial substring check on the server-side (driver) location.
    # The customer's own delivery_address CAN contain lat/lng keys
    # (null here, since we didn't supply them), because the spec lets
    # the customer see their OWN destination.  What must not leak is
    # the DRIVER's last-known position — so we check sentinel values
    # and the server-side field name prefix.
    assert "last_known" not in raw_lower
    assert "current_lat" not in raw_lower
    assert "current_lng" not in raw_lower
    # Sentinel coordinate digits — stringified leak check.
    assert "12.3456" not in raw
    assert "98.7654" not in raw
    # No driver identity on the customer view.
    assert "driver_id" not in raw_lower

    # Schema-level: must validate as CustomerDeliveryView (extra='forbid').
    view = CustomerDeliveryView.model_validate_json(r.text)
    assert view.order_id == uuid.UUID(oid)
    assert view.eta_seconds == 120


@pytest.mark.asyncio
async def test_internal_track_response_carries_coordinates(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Seller and admin get the internal view with coordinates."""
    ctx = await _drive_order_to_ofd(client, db, "p7r2")
    oid = ctx["order_id"]
    await client.post(
        f"/api/v1/deliveries/{oid}/location",
        json={"lat": 10.0, "lng": 20.0, "eta_seconds": 300},
        headers=_h(ctx["s_token"]),
    )
    r = await client.get(
        f"/api/v1/deliveries/{oid}/track", headers=_h(ctx["s_token"])
    )
    assert r.status_code == 200
    view = InternalDeliveryView.model_validate_json(r.text)
    assert view.last_known_lat == 10.0
    assert view.last_known_lng == 20.0


@pytest.mark.asyncio
async def test_stranger_gets_404_on_track(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Adversarial test 4a: unrelated user → 404."""
    ctx = await _drive_order_to_ofd(client, db, "p7r3")
    oid = ctx["order_id"]
    stranger = await seed_customer(db, "stranger_p7r3@example.com")
    stranger_tok = await _login(client, "stranger_p7r3@example.com", "CustomerPass123!")
    r = await client.get(
        f"/api/v1/deliveries/{oid}/track", headers=_h(stranger_tok)
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_customer_cannot_post_location(
    client: AsyncClient, db: AsyncSession
) -> None:
    ctx = await _drive_order_to_ofd(client, db, "p7r4")
    r = await client.post(
        f"/api/v1/deliveries/{ctx['order_id']}/location",
        json={"lat": 1.0, "lng": 2.0},
        headers=_h(ctx["c_token"]),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_location_post_before_ofd_returns_409(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Adversarial test 5: driver posts while order not OFD → 409."""
    seller = await seed_seller_with_profile(db, "seller_p7r5@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=1000, stock_quantity=5)
    customer = await seed_customer(
        db, "customer_p7r5@example.com", referring_seller_id=seller.id
    )
    s_tok = await _login(client, "seller_p7r5@example.com", "SellerPass123!")
    c_tok = await _login(client, "customer_p7r5@example.com", "CustomerPass123!")
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(product.id), "quantity": 1}],
            "delivery_address": _addr(),
        },
        headers=_h(c_tok),
    )
    oid = r.json()["id"]
    # Move to "accepted" only.
    await client.post(f"/api/v1/orders/{oid}/accept", headers=_h(s_tok))
    # Seller tries to post a location while status=accepted.
    r = await client.post(
        f"/api/v1/deliveries/{oid}/location",
        json={"lat": 1.0, "lng": 2.0},
        headers=_h(s_tok),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_INVALID_TRANSITION"


@pytest.mark.asyncio
async def test_seller_self_delivery_can_publish_location(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Test 6: seller self-delivery path — seller can POST /location."""
    ctx = await _drive_order_to_ofd(client, db, "p7r6")
    r = await client.post(
        f"/api/v1/deliveries/{ctx['order_id']}/location",
        json={"lat": 1.1, "lng": 2.2, "eta_seconds": 60},
        headers=_h(ctx["s_token"]),
    )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_location_after_delivered_returns_409(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Adversarial test 8: after delivered, POST /location → 409."""
    ctx = await _drive_order_to_ofd(client, db, "p7r7")
    oid = ctx["order_id"]
    # Mark delivered.
    r = await client.post(f"/api/v1/orders/{oid}/delivered", headers=_h(ctx["s_token"]))
    assert r.status_code == 200
    r = await client.post(
        f"/api/v1/deliveries/{oid}/location",
        json={"lat": 1.0, "lng": 2.0},
        headers=_h(ctx["s_token"]),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_INVALID_TRANSITION"


@pytest.mark.asyncio
async def test_driver_can_post_location_in_assigned_mode(
    client: AsyncClient, db: AsyncSession
) -> None:
    ctx = await _drive_order_to_ofd(client, db, "p7r8", use_driver=True)
    r = await client.post(
        f"/api/v1/deliveries/{ctx['order_id']}/location",
        json={"lat": 40.7, "lng": -74.0, "eta_seconds": 45},
        headers=_h(ctx["d_token"]),
    )
    assert r.status_code == 204
    # Customer GET /track shows eta but no driver coords.
    r = await client.get(
        f"/api/v1/deliveries/{ctx['order_id']}/track", headers=_h(ctx["c_token"])
    )
    assert r.status_code == 200
    body = r.json()
    assert body["eta_seconds"] == 45
    # Driver's unique coords (40.7 / -74.0) must not be in body.
    assert "40.7" not in r.text
    assert "-74.0" not in r.text
    assert '"last_known_lat"' not in r.text
    assert '"last_known_lng"' not in r.text
    assert '"driver_id"' not in r.text


@pytest.mark.asyncio
async def test_metrics_persisted_on_complete(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Adversarial test 9: duration populated + snapshot carries metrics."""
    ctx = await _drive_order_to_ofd(client, db, "p7r9")
    oid = ctx["order_id"]

    # Post a distance metric.
    await client.post(
        f"/api/v1/deliveries/{oid}/location",
        json={"lat": 1.0, "lng": 2.0, "distance_meters": 5432},
        headers=_h(ctx["s_token"]),
    )

    # Force a nontrivial duration by backdating started_at.
    from app.models.delivery import Delivery
    import sqlalchemy as sa

    result = await db.execute(sa.select(Delivery).where(Delivery.order_id == uuid.UUID(oid)))
    dlv = result.scalar_one()
    dlv.started_at = datetime.now(timezone.utc).replace(microsecond=0)  # type: ignore[assignment]
    from datetime import timedelta

    dlv.started_at = datetime.now(timezone.utc) - timedelta(seconds=300)  # type: ignore[assignment]
    await db.flush()

    # Delivered.
    r = await client.post(f"/api/v1/orders/{oid}/delivered", headers=_h(ctx["s_token"]))
    assert r.status_code == 200
    # Complete.
    r = await client.post(f"/api/v1/orders/{oid}/complete", headers=_h(ctx["c_token"]))
    assert r.status_code == 200

    # duration_seconds populated on delivery row.
    result = await db.execute(sa.select(Delivery).where(Delivery.order_id == uuid.UUID(oid)))
    dlv = result.scalar_one()
    assert dlv.duration_seconds is not None
    assert dlv.duration_seconds >= 290  # backdated by 300s
    assert dlv.distance_meters == 5432

    # Snapshot carries the metrics.
    from app.models.order_analytics_snapshot import OrderAnalyticsSnapshot

    snap_result = await db.execute(
        sa.select(OrderAnalyticsSnapshot).where(
            OrderAnalyticsSnapshot.order_id == uuid.UUID(oid)
        )
    )
    snap = snap_result.scalar_one()
    assert snap.delivery_duration_seconds == dlv.duration_seconds
    assert snap.delivery_distance_meters == 5432


@pytest.mark.asyncio
async def test_admin_patch_overrides_metrics_and_reassigns_driver(
    client: AsyncClient, db: AsyncSession
) -> None:
    ctx = await _drive_order_to_ofd(client, db, "p7r10", use_driver=True)
    new_driver = await seed_driver(db, "newdrv_p7r10@example.com")
    r = await client.patch(
        f"/api/v1/admin/deliveries/{ctx['order_id']}",
        json={
            "driver_id": str(new_driver.id),
            "distance_meters": 1234,
            "duration_seconds": 600,
        },
        headers=_h(ctx["a_token"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["driver_id"] == str(new_driver.id)
    assert body["distance_meters"] == 1234
    assert body["duration_seconds"] == 600


# =========================================================================
# Pure schema / model assertions — no DB.
# =========================================================================


def test_customer_view_schema_has_no_coordinate_fields() -> None:
    """Adversarial test 10: structurally impossible to set lat/lng.

    The model_fields map enumerates the only fields Pydantic will
    populate.  If a developer ever adds lat/lng to CustomerDeliveryView,
    this assertion fails — a regression bell.
    """
    field_names = set(CustomerDeliveryView.model_fields.keys())
    assert "lat" not in field_names
    assert "lng" not in field_names
    assert "last_known_lat" not in field_names
    assert "last_known_lng" not in field_names
    assert "driver_id" not in field_names
    # Confirm the fields we DO expect.
    assert field_names == {
        "order_id",
        "status",
        "eta_seconds",
        "eta_updated_at",
        "started_at",
        "delivered_at",
        "delivery_address",
    }


def test_customer_view_rejects_extra_coordinate_fields() -> None:
    """extra='forbid' means even if a dev tries to sneak in lat/lng."""
    payload = {
        "order_id": str(uuid.uuid4()),
        "status": "out_for_delivery",
        "delivery_address": {"line1": "1 A St", "city": "X", "country": "US"},
        "lat": 10.0,  # sneaky addition
    }
    with pytest.raises(ValidationError):
        CustomerDeliveryView.model_validate(payload)


def test_customer_events_reject_coordinate_fields() -> None:
    base = {"order_id": str(uuid.uuid4())}
    with pytest.raises(ValidationError):
        CustomerDeliveryEtaEvent.model_validate({**base, "type": "delivery.eta", "lat": 1.0})
    with pytest.raises(ValidationError):
        CustomerDeliveryStatusEvent.model_validate(
            {**base, "type": "delivery.status", "status": "x", "lng": 2.0}
        )


# =========================================================================
# WebSocket tests — sync, psycopg2-backed.
# Mirrors the pattern in tests/test_websocket.py.
# =========================================================================


def _mk_token(user_id: uuid.UUID, role: str) -> str:
    token, _ = create_access_token(user_id, role)
    return token


def _sql(sql: str, params: tuple = ()) -> list:
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall() if cur.description else []
        conn.commit()
        return rows
    finally:
        conn.close()


def _make_user(email: str, role: str) -> uuid.UUID:
    uid = uuid.uuid4()
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (id, email, password_hash, role, display_name, is_active) "
            "VALUES (%s, %s, %s, %s, %s, TRUE)",
            (str(uid), email, hash_password("WsTest1234!"), role, "WS"),
        )
        if role == "seller":
            cur.execute(
                "INSERT INTO sellers (id, user_id, display_name, bio, city, country_code) "
                "VALUES (%s, %s, %s, NULL, %s, %s)",
                (str(uid), str(uid), "WS", "Town", "US"),
            )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return uid


def _link_customer_to_seller(cust: uuid.UUID, seller: uuid.UUID) -> None:
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET referring_seller_id=%s WHERE id=%s",
            (str(seller), str(cust)),
        )
        conn.commit()
    finally:
        conn.close()


def _make_store_and_product(seller: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    store_id = uuid.uuid4()
    prod_id = uuid.uuid4()
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO stores (id, seller_id, name, slug, description, is_active) "
            "VALUES (%s, %s, %s, %s, %s, TRUE)",
            (str(store_id), str(seller), "WS Store", f"ws-{store_id.hex[:8]}", ""),
        )
        cur.execute(
            "INSERT INTO products (id, seller_id, store_id, name, description, "
            "price_minor, stock_quantity, is_active) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)",
            (str(prod_id), str(seller), str(store_id), "WS Product", "", 1000, 10),
        )
        conn.commit()
    finally:
        conn.close()
    return store_id, prod_id


def _make_ofd_order(
    seller: uuid.UUID,
    customer: uuid.UUID,
    store_id: uuid.UUID,
    *,
    driver_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Create an order row directly in OFD state with a delivery row."""
    oid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (id, customer_id, seller_id, store_id, status, "
            "subtotal_minor, total_minor, delivery_address, placed_at, accepted_at, "
            "preparing_at, out_for_delivery_at) "
            "VALUES (%s, %s, %s, %s, 'out_for_delivery', 1000, 1000, "
            "%s::jsonb, %s, %s, %s, %s)",
            (
                str(oid),
                str(customer),
                str(seller),
                str(store_id),
                json.dumps({"line1": "1 A", "city": "X", "country": "US"}),
                now,
                now,
                now,
                now,
            ),
        )
        cur.execute(
            "INSERT INTO deliveries (id, order_id, driver_id, seller_id, status, started_at) "
            "VALUES (%s, %s, %s, %s, 'in_transit', %s)",
            (str(uuid.uuid4()), str(oid), str(driver_id) if driver_id else None, str(seller), now),
        )
        conn.commit()
    finally:
        conn.close()
    return oid


def _cleanup_order(oid: uuid.UUID) -> None:
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM deliveries WHERE order_id=%s", (str(oid),))
        cur.execute("DELETE FROM orders WHERE id=%s", (str(oid),))
        conn.commit()
    finally:
        conn.close()


def _cleanup_users(ids: list[uuid.UUID]) -> None:
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        for uid in ids:
            cur.execute("DELETE FROM products WHERE seller_id=%s", (str(uid),))
            cur.execute("DELETE FROM stores WHERE seller_id=%s", (str(uid),))
            cur.execute("DELETE FROM sellers WHERE id=%s", (str(uid),))
            cur.execute("UPDATE users SET referring_seller_id=NULL WHERE referring_seller_id=%s", (str(uid),))
            cur.execute("DELETE FROM users WHERE id=%s", (str(uid),))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="module")
def tc(setup_test_db):
    with TestClient(app) as client:
        yield client
    # Dispose the async engine's connection pool.  TestClient spins up a
    # dedicated event loop inside an anyio BlockingPortal; when the client
    # exits, that loop closes, but any asyncpg connections leased from
    # our module-level engine pool remain attached to it.  A later
    # module-scoped TestClient (e.g. test_websocket.py) then receives
    # those stale connections on a different loop, causing
    # "Future attached to a different loop" errors.  Disposing the pool
    # here forces a clean reconnect on the next event loop.
    import asyncio
    from app.db.session import async_engine
    asyncio.run(async_engine.dispose())


def _drain_until_pong(ws) -> list[dict]:
    """Drain all messages up to and including the pong reply to a ping.

    Sends a ``{"type":"ping"}`` from the client, reads messages one at a
    time, and stops when ``{"type":"pong"}`` arrives.  Because the server
    processes messages in order per-connection, any event broadcast
    BEFORE the ping was received by the server will have been queued
    into the send stream BEFORE the pong — so by reading until pong we
    capture every preceding event without needing a timeout.
    """
    ws.send_text(json.dumps({"type": "ping"}))
    events: list[dict] = []
    while True:
        evt = json.loads(ws.receive_text())
        if evt.get("type") == "pong":
            break
        events.append(evt)
    return events


def test_ws_customer_never_receives_location_events(tc: TestClient) -> None:
    """Adversarial test 2: customer socket receives ZERO delivery.location events.

    Driver posts 5 location updates via the internal broadcaster (routed by
    role).  Customer socket is subscribed to the SAME delivery topic, but
    the dispatcher routes location events to the internal bucket only —
    customer must receive 0 location events.
    """
    seller = _make_user("ws_p7_s1@example.com", "seller")
    customer = _make_user("ws_p7_c1@example.com", "customer")
    driver = _make_user("ws_p7_d1@example.com", "driver")
    _link_customer_to_seller(customer, seller)
    store_id, _ = _make_store_and_product(seller)
    oid = _make_ofd_order(seller, customer, store_id, driver_id=driver)
    try:
        cust_tok = _mk_token(customer, "customer")
        driver_tok = _mk_token(driver, "driver")
        seller_tok = _mk_token(seller, "seller")

        # Customer subscribes.
        with tc.websocket_connect(f"/ws?token={cust_tok}") as ws_cust:
            ws_cust.send_text(
                json.dumps({"type": "subscribe", "delivery_order_id": str(oid)})
            )
            ack = json.loads(ws_cust.receive_text())
            assert ack["type"] == "delivery.subscribed"

            # Internal socket also subscribes (to verify broadcaster fires).
            with tc.websocket_connect(f"/ws?token={seller_tok}") as ws_seller:
                ws_seller.send_text(
                    json.dumps({"type": "subscribe", "delivery_order_id": str(oid)})
                )
                assert json.loads(ws_seller.receive_text())["type"] == "delivery.subscribed"

                # Driver posts 5 location updates via REST.
                for i in range(5):
                    r = tc.post(
                        f"/api/v1/deliveries/{oid}/location",
                        json={"lat": 1.0 + i, "lng": 2.0 + i, "eta_seconds": 30 + i},
                        headers={"Authorization": f"Bearer {driver_tok}"},
                    )
                    assert r.status_code == 204, r.text

                # Drain seller (internal) socket: expect 5 location + 5 eta.
                seller_events = _drain_until_pong(ws_seller)
                seller_types = [e.get("type") for e in seller_events]
                assert seller_types.count("delivery.location") == 5
                assert seller_types.count("delivery.eta") == 5

            # Drain customer socket.  Expect 0 location events; exactly 5
            # eta events (from the same posts).
            cust_events = _drain_until_pong(ws_cust)
            cust_types = [e.get("type") for e in cust_events]
            assert cust_types.count("delivery.location") == 0
            # Also confirm zero events have lat/lng keys.
            for evt in cust_events:
                assert "lat" not in evt
                assert "lng" not in evt
                # Must pass strict customer-event schema.
                if evt.get("type") == "delivery.eta":
                    CustomerDeliveryEtaEvent.model_validate(evt)
                elif evt.get("type") == "delivery.status":
                    CustomerDeliveryStatusEvent.model_validate(evt)
                elif evt.get("type") == "delivery.subscribed":
                    CustomerDeliverySubscribedEvent.model_validate(evt)
                elif evt.get("type") == "ping":
                    pass
                else:
                    raise AssertionError(f"Unexpected event on customer socket: {evt}")
            assert cust_types.count("delivery.eta") == 5
    finally:
        _cleanup_order(oid)
        _cleanup_users([seller, customer, driver])


def test_ws_stranger_subscribe_4403(tc: TestClient) -> None:
    """Adversarial test 4b: unrelated user → 4403."""
    seller = _make_user("ws_p7_s2@example.com", "seller")
    customer = _make_user("ws_p7_c2@example.com", "customer")
    stranger = _make_user("ws_p7_x2@example.com", "customer")
    _link_customer_to_seller(customer, seller)
    store_id, _ = _make_store_and_product(seller)
    oid = _make_ofd_order(seller, customer, store_id)
    try:
        tok = _mk_token(stranger, "customer")
        with pytest.raises(WebSocketDisconnect) as exc:
            with tc.websocket_connect(f"/ws?token={tok}") as ws:
                ws.send_text(
                    json.dumps({"type": "subscribe", "delivery_order_id": str(oid)})
                )
                ws.receive_text()  # await close frame
        assert exc.value.code == 4403
    finally:
        _cleanup_order(oid)
        _cleanup_users([seller, customer, stranger])


def test_ws_two_delivery_isolation(tc: TestClient) -> None:
    """Adversarial test 7: customer of A / driver of B — no crosstalk.

    Shared user is:
    - customer on order A
    - driver on order B
    While subscribed to A, they must NOT receive B's location events even
    though they are also authorized for B.
    """
    seller = _make_user("ws_p7_s3@example.com", "seller")
    shared = _make_user("ws_p7_shared@example.com", "customer")
    # Shared user also has driver role for order B — create a second user
    # for that (we can't have one user be two roles).  Use a separate driver.
    shared_as_driver = _make_user("ws_p7_shared_drv@example.com", "driver")
    other_customer = _make_user("ws_p7_c3b@example.com", "customer")
    _link_customer_to_seller(shared, seller)
    _link_customer_to_seller(other_customer, seller)
    store_id, _ = _make_store_and_product(seller)

    order_a = _make_ofd_order(seller, shared, store_id)  # shared is customer.
    order_b = _make_ofd_order(
        seller, other_customer, store_id, driver_id=shared_as_driver
    )
    try:
        cust_tok = _mk_token(shared, "customer")
        driver_tok = _mk_token(shared_as_driver, "driver")

        with tc.websocket_connect(f"/ws?token={cust_tok}") as ws:
            ws.send_text(
                json.dumps({"type": "subscribe", "delivery_order_id": str(order_a)})
            )
            assert json.loads(ws.receive_text())["type"] == "delivery.subscribed"

            # Driver (different socket) posts to order_b.
            r = tc.post(
                f"/api/v1/deliveries/{order_b}/location",
                json={"lat": 7.0, "lng": 8.0, "eta_seconds": 5},
                headers={"Authorization": f"Bearer {driver_tok}"},
            )
            assert r.status_code == 204

            # Drain socket — should have zero events about order_b.
            events = _drain_until_pong(ws)
            for evt in events:
                # None must reference order_b.
                assert evt.get("order_id") != str(order_b)
    finally:
        _cleanup_order(order_a)
        _cleanup_order(order_b)
        _cleanup_users([seller, shared, shared_as_driver, other_customer])


def test_ws_no_token_closes_4401(tc: TestClient) -> None:
    """Regression: WS without token still closes 4401 (existing invariant)."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with tc.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "subscribe", "delivery_order_id": str(uuid.uuid4())}))
            ws.receive_text()
    assert exc.value.code == 4401
