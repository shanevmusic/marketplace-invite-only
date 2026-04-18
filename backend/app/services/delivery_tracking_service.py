"""Delivery tracking service — Phase 7.

Enforces asymmetric visibility: customer NEVER sees driver/seller coordinates.

Two distinct serializers:
- ``build_internal_view`` → full coordinates, driver info, metrics. Used by
  driver / seller / admin.
- ``build_customer_view`` → order_id, status, eta, delivery_address only.
  No lat/lng keys exist on the schema, so there is structurally no way to
  leak coordinates to a customer via this path.

Role resolution is centralised in ``resolve_role``; all endpoints + the WS
gateway must funnel through it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DeliveryAlreadyStarted,
    NotFoundError,
    OrderInvalidTransition,
    OrderNotFound,
)
from app.core.exceptions import AuthorizationError
from app.models.delivery import Delivery
from app.models.driver_assignment import DriverAssignment
from app.models.order import Order
from app.models.user import User
from app.schemas.delivery_tracking import (
    CustomerDeliveryView,
    InternalDeliveryView,
)


TrackingRole = Literal["customer", "seller", "driver", "admin", "none"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


async def load_order(db: AsyncSession, order_id: uuid.UUID) -> Optional[Order]:
    result = await db.execute(
        sa.select(Order).where(Order.id == order_id, Order.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def load_delivery(
    db: AsyncSession, order_id: uuid.UUID, *, lock: bool = False
) -> Optional[Delivery]:
    stmt = sa.select(Delivery).where(Delivery.order_id == order_id)
    if lock:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Role resolver — the central gate
# ---------------------------------------------------------------------------


async def resolve_role(
    db: AsyncSession, *, user: User, order: Order
) -> TrackingRole:
    """Return the caller's role relative to this order.

    - admin → always "admin".
    - seller → "seller" iff order.seller_id == user.id (ADR-0011 invariant).
    - customer → "customer" iff order.customer_id == user.id.
    - driver → "driver" iff the delivery row has driver_id == user.id OR
      there is an active driver_assignment (assigned/accepted) matching.
    - otherwise → "none".
    """
    if user.role == "admin":
        return "admin"
    if user.role == "seller" and order.seller_id == user.id:
        return "seller"
    if user.role == "customer" and order.customer_id == user.id:
        return "customer"
    if user.role == "driver":
        delivery = await load_delivery(db, order.id)
        if delivery is not None and delivery.driver_id == user.id:
            return "driver"
        assign_result = await db.execute(
            sa.select(DriverAssignment).where(
                DriverAssignment.order_id == order.id,
                DriverAssignment.driver_id == user.id,
                DriverAssignment.status.in_(("assigned", "accepted")),
            )
        )
        if assign_result.scalar_one_or_none() is not None:
            return "driver"
    return "none"


def is_internal_role(role: TrackingRole) -> bool:
    return role in ("admin", "seller", "driver")


# ---------------------------------------------------------------------------
# Serializers — two DIFFERENT types, not one filtered dict
# ---------------------------------------------------------------------------


def build_internal_view(
    order: Order, delivery: Delivery
) -> InternalDeliveryView:
    return InternalDeliveryView(
        order_id=order.id,
        delivery_id=delivery.id,
        status=delivery.status,
        driver_id=delivery.driver_id,
        seller_id=delivery.seller_id,
        started_at=delivery.started_at,  # type: ignore[arg-type]
        delivered_at=delivery.delivered_at,  # type: ignore[arg-type]
        last_known_lat=delivery.current_lat,
        last_known_lng=delivery.current_lng,
        last_location_at=delivery.last_location_at,  # type: ignore[arg-type]
        current_eta_seconds=delivery.current_eta_seconds,
        current_eta_updated_at=delivery.current_eta_updated_at,  # type: ignore[arg-type]
        distance_meters=delivery.distance_meters,
        duration_seconds=delivery.duration_seconds,
        customer_delivery_address=dict(order.delivery_address or {}),
    )


def build_customer_view(
    order: Order, delivery: Optional[Delivery]
) -> CustomerDeliveryView:
    """Customer-safe serialization.

    Accepts a possibly-NULL delivery (e.g. order not yet out_for_delivery).
    NEVER reads lat/lng from delivery — the schema doesn't even have those
    fields, so we could not pass them in.
    """
    eta_seconds = delivery.current_eta_seconds if delivery else None
    eta_updated_at = delivery.current_eta_updated_at if delivery else None
    started_at = delivery.started_at if delivery else None
    delivered_at = delivery.delivered_at if delivery else order.delivered_at
    # Status: surface the delivery row's status if present (more granular),
    # else the order status (e.g. "pending" / "accepted" / "preparing").
    status = delivery.status if delivery else order.status
    return CustomerDeliveryView(
        order_id=order.id,
        status=status,
        eta_seconds=eta_seconds,
        eta_updated_at=eta_updated_at,  # type: ignore[arg-type]
        started_at=started_at,  # type: ignore[arg-type]
        delivered_at=delivered_at,  # type: ignore[arg-type]
        delivery_address=dict(order.delivery_address or {}),
    )


# ---------------------------------------------------------------------------
# Public operations
# ---------------------------------------------------------------------------


async def get_track_view(
    db: AsyncSession, *, user: User, order_id: uuid.UUID
) -> InternalDeliveryView | CustomerDeliveryView:
    """Return the role-appropriate view, or raise OrderNotFound / Authz."""
    order = await load_order(db, order_id)
    if order is None:
        raise OrderNotFound()
    role = await resolve_role(db, user=user, order=order)
    if role == "none":
        raise OrderNotFound()
    delivery = await load_delivery(db, order.id)
    if role == "customer":
        return build_customer_view(order, delivery)
    if delivery is None:
        # Internal callers expect a delivery row; if there isn't one yet,
        # return 404 so the caller knows tracking hasn't started.
        raise NotFoundError("No delivery row for this order yet.", code="DELIVERY_NOT_STARTED")
    return build_internal_view(order, delivery)


async def post_location(
    db: AsyncSession,
    *,
    user: User,
    order_id: uuid.UUID,
    lat: float,
    lng: float,
    eta_seconds: Optional[int],
    distance_meters: Optional[int],
) -> tuple[Order, Delivery]:
    """Driver/seller posts a location update.

    - 404 if order not found or caller has no relationship to it.
    - 403 if caller is a customer (they cannot post location).
    - 409 if order is not out_for_delivery (tracking window closed).
    """
    order = await load_order(db, order_id)
    if order is None:
        raise OrderNotFound()
    role = await resolve_role(db, user=user, order=order)
    if role == "none":
        raise OrderNotFound()
    if role not in ("driver", "seller", "admin"):
        raise AuthorizationError(
            "Only the assigned driver, the seller, or an admin may post delivery locations.",
            code="PERMISSION_DENIED",
        )
    if order.status != "out_for_delivery":
        raise OrderInvalidTransition(
            f"Cannot post location while order status is {order.status!r}."
        )

    delivery = await load_delivery(db, order.id, lock=True)
    if delivery is None:
        raise OrderInvalidTransition("Delivery row missing for out_for_delivery order.")
    if delivery.status == "delivered":
        # Belt-and-suspenders: OFD check above should already cover this.
        raise OrderInvalidTransition("Delivery already completed.")

    now = _now()
    delivery.current_lat = lat
    delivery.current_lng = lng
    delivery.last_location_at = now  # type: ignore[assignment]
    if eta_seconds is not None:
        delivery.current_eta_seconds = eta_seconds
        delivery.current_eta_updated_at = now  # type: ignore[assignment]
    if distance_meters is not None:
        # Store max seen to avoid noisy over-write of an earlier higher value.
        prev = delivery.distance_meters or 0
        delivery.distance_meters = max(prev, distance_meters)
    await db.flush()
    return order, delivery


async def admin_patch_delivery(
    db: AsyncSession,
    *,
    caller: User,
    order_id: uuid.UUID,
    driver_id: Optional[uuid.UUID] = None,
    distance_meters: Optional[int] = None,
    duration_seconds: Optional[int] = None,
) -> tuple[Order, Delivery]:
    if caller.role != "admin":
        raise OrderNotFound()
    order = await load_order(db, order_id)
    if order is None:
        raise OrderNotFound()
    delivery = await load_delivery(db, order.id, lock=True)
    if delivery is None:
        raise OrderNotFound()
    if driver_id is not None:
        drv_result = await db.execute(
            sa.select(User).where(
                User.id == driver_id,
                User.role == "driver",
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        drv = drv_result.scalar_one_or_none()
        if drv is None:
            raise OrderInvalidTransition("Driver not found or inactive.")
        delivery.driver_id = driver_id
    if distance_meters is not None:
        delivery.distance_meters = distance_meters
    if duration_seconds is not None:
        delivery.duration_seconds = duration_seconds
    await db.flush()
    return order, delivery


# ---------------------------------------------------------------------------
# Event payload helpers — used by both REST broadcasters and WS.
# ---------------------------------------------------------------------------


def internal_location_event(delivery: Delivery) -> dict[str, Any]:
    """Event emitted to internal subscribers (driver/seller/admin)."""
    return {
        "type": "delivery.location",
        "order_id": str(delivery.order_id),
        "lat": delivery.current_lat,
        "lng": delivery.current_lng,
        "at": delivery.last_location_at.isoformat() if delivery.last_location_at else None,  # type: ignore[union-attr]
        "driver_id": str(delivery.driver_id) if delivery.driver_id else None,
    }


def eta_event(delivery: Delivery) -> dict[str, Any]:
    """Customer-safe ETA event.  Contains NO coordinates."""
    return {
        "type": "delivery.eta",
        "order_id": str(delivery.order_id),
        "eta_seconds": delivery.current_eta_seconds,
        "eta_updated_at": delivery.current_eta_updated_at.isoformat()  # type: ignore[union-attr]
        if delivery.current_eta_updated_at
        else None,
    }


def status_event(
    order_id: uuid.UUID,
    status: str,
    *,
    started_at: Optional[datetime] = None,
    delivered_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Customer-safe status event."""
    payload: dict[str, Any] = {
        "type": "delivery.status",
        "order_id": str(order_id),
        "status": status,
    }
    if started_at is not None:
        payload["started_at"] = started_at.isoformat()
    if delivered_at is not None:
        payload["delivered_at"] = delivered_at.isoformat()
    return payload
