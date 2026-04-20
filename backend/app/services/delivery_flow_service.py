"""Delivery-flow business logic — accept, track, chat-archive, complete."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, ConflictError, NotFoundError, AuthorizationError
from app.models.delivery import Delivery
from app.models.delivery_flow import (
    DeliveryCode,
    DeliveryCodeAttempt,
    OrderMessage,
    OrderTrackingPoint,
)
from app.models.order import Order
from app.models.user import User


class DeliveryCodeLocked(AppException):
    http_status = 423
    code = "DELIVERY_CODE_LOCKED"


class DeliveryCodeInvalid(AppException):
    http_status = 400
    code = "DELIVERY_CODE_INVALID"


def _hash_code(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def _get_order_or_404(db: AsyncSession, order_id: uuid.UUID) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.deleted_at is not None:
        raise NotFoundError("Order not found.", code="ORDER_NOT_FOUND")
    return order


async def accept_order(
    db: AsyncSession, *, driver: User, order_id: uuid.UUID
) -> tuple[Order, DeliveryCode]:
    """Driver accepts an order — sets timestamp, generates delivery code."""
    if driver.role != "driver":
        raise AuthorizationError(
            "Only drivers can accept orders.", code="PERMISSION_DENIED"
        )
    order = await _get_order_or_404(db, order_id)

    if order.driver_accepted_at is not None:
        existing = await db.get(DeliveryCode, order.id)
        if existing is not None:
            return order, existing

    now = datetime.now(timezone.utc)
    order.driver_accepted_at = now

    # Assign driver on the delivery row so WS/REST tracking role resolution
    # recognizes this driver as internal.
    delivery_q = await db.execute(
        sa.select(Delivery).where(Delivery.order_id == order.id)
    )
    delivery = delivery_q.scalar_one_or_none()
    if delivery is None:
        delivery = Delivery(
            order_id=order.id,
            driver_id=driver.id,
            seller_id=order.seller_id,
            status="in_transit",
        )
        db.add(delivery)
    else:
        delivery.driver_id = driver.id

    plain = _generate_code()
    code = DeliveryCode(
        order_id=order.id,
        code_plain=plain,
        code_hash=_hash_code(plain),
    )
    db.add(code)

    await db.flush()
    return order, code


async def record_location(
    db: AsyncSession, *, driver: User, order_id: uuid.UUID, lat: float, lng: float
) -> OrderTrackingPoint:
    if driver.role not in ("driver", "seller", "admin"):
        raise AuthorizationError("Permission denied.", code="PERMISSION_DENIED")
    order = await _get_order_or_404(db, order_id)
    point = OrderTrackingPoint(
        order_id=order.id,
        driver_id=driver.id if driver.role == "driver" else None,
        lat=lat,
        lng=lng,
    )
    db.add(point)
    # Also keep Delivery.current_lat/current_lng up to date for legacy tracking.
    delivery_q = await db.execute(
        sa.select(Delivery).where(Delivery.order_id == order.id)
    )
    delivery = delivery_q.scalar_one_or_none()
    if delivery is not None:
        delivery.current_lat = lat
        delivery.current_lng = lng
    await db.flush()
    return point


async def get_route(
    db: AsyncSession, *, caller: User, order_id: uuid.UUID
) -> dict:
    order = await _get_order_or_404(db, order_id)
    addr = order.delivery_address or {}
    return {
        "order_id": order.id,
        "customer_lat": addr.get("lat"),
        "customer_lng": addr.get("lng"),
        "polyline": None,
    }


async def complete_delivery(
    db: AsyncSession, *, driver: User, order_id: uuid.UUID, submitted: str
) -> Order:
    if driver.role != "driver":
        raise AuthorizationError("Only drivers complete deliveries.", code="PERMISSION_DENIED")

    order = await _get_order_or_404(db, order_id)
    code = await db.get(DeliveryCode, order.id)
    if code is None:
        raise ConflictError(
            "Delivery has not been accepted yet.", code="DELIVERY_NOT_ACCEPTED"
        )

    # Audit row written regardless of outcome.
    attempt = DeliveryCodeAttempt(
        order_id=order.id,
        driver_id=driver.id,
        submitted_code=submitted,
        success=False,
    )

    if code.locked:
        db.add(attempt)
        await db.flush()
        raise DeliveryCodeLocked(
            "Delivery code is locked. Contact support.",
            code="DELIVERY_CODE_LOCKED",
        )

    if _hash_code(submitted) != code.code_hash:
        code.attempts_used += 1
        if code.attempts_used >= 3:
            code.locked = True
            order.delivery_code_locked = True
        db.add(attempt)
        await db.flush()
        if code.locked:
            raise DeliveryCodeLocked(
                "Delivery code locked after 3 failed attempts.",
                code="DELIVERY_CODE_LOCKED",
            )
        remaining = 3 - code.attempts_used
        raise DeliveryCodeInvalid(
            f"Incorrect code. {remaining} attempts remaining.",
            code="DELIVERY_CODE_INVALID",
            details={"attempts_remaining": remaining},
        )

    # Success path.
    attempt.success = True
    now = datetime.now(timezone.utc)
    code.consumed_at = now
    order.delivered_at = now
    order.status = "delivered"
    order.customer_visible_after = now + timedelta(minutes=30)

    # Archive all order messages (hide from driver + customer; admin keeps).
    await db.execute(
        sa.update(OrderMessage)
        .where(OrderMessage.order_id == order.id, OrderMessage.archived_at.is_(None))
        .values(archived_at=now)
    )
    db.add(attempt)
    await db.flush()
    return order


async def compute_eta_seconds(
    db: AsyncSession, *, order_id: uuid.UUID
) -> tuple[Optional[int], Optional[datetime]]:
    """Haversine distance from latest tracking point / 30 km·h average."""
    row_q = await db.execute(
        sa.select(OrderTrackingPoint)
        .where(OrderTrackingPoint.order_id == order_id)
        .order_by(OrderTrackingPoint.recorded_at.desc())
        .limit(1)
    )
    point: Optional[OrderTrackingPoint] = row_q.scalar_one_or_none()
    if point is None:
        return None, None

    order = await db.get(Order, order_id)
    if order is None:
        return None, None
    addr = order.delivery_address or {}
    dest_lat = addr.get("lat")
    dest_lng = addr.get("lng")
    if dest_lat is None or dest_lng is None:
        return None, point.recorded_at

    import math

    lat1, lon1 = math.radians(point.lat), math.radians(point.lng)
    lat2, lon2 = math.radians(float(dest_lat)), math.radians(float(dest_lng))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    distance_m = 6371000.0 * c
    # 30 km/h average = 8.333 m/s.
    seconds = int(distance_m / 8.333)
    return seconds, point.recorded_at


async def get_delivery_code_for_customer(
    db: AsyncSession, *, customer: User, order_id: uuid.UUID
) -> DeliveryCode:
    order = await _get_order_or_404(db, order_id)
    if order.customer_id != customer.id and customer.role != "admin":
        raise NotFoundError("Order not found.", code="ORDER_NOT_FOUND")
    code = await db.get(DeliveryCode, order.id)
    if code is None or order.driver_accepted_at is None or order.delivered_at is not None:
        raise NotFoundError("Delivery code not available.", code="CODE_NOT_AVAILABLE")
    return code


async def list_tracking_points(
    db: AsyncSession, *, order_id: uuid.UUID
) -> list[OrderTrackingPoint]:
    rows = await db.execute(
        sa.select(OrderTrackingPoint)
        .where(OrderTrackingPoint.order_id == order_id)
        .order_by(OrderTrackingPoint.recorded_at.asc())
    )
    return list(rows.scalars().all())


async def list_order_messages(
    db: AsyncSession, *, order_id: uuid.UUID, include_archived: bool
) -> list[OrderMessage]:
    stmt = sa.select(OrderMessage).where(OrderMessage.order_id == order_id)
    if not include_archived:
        stmt = stmt.where(OrderMessage.archived_at.is_(None))
    stmt = stmt.order_by(OrderMessage.created_at.asc())
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def post_order_message(
    db: AsyncSession,
    *,
    sender: User,
    order_id: uuid.UUID,
    ciphertext: str,
    nonce: str,
) -> OrderMessage:
    order = await _get_order_or_404(db, order_id)
    if order.driver_accepted_at is None:
        raise ConflictError("Chat not open yet.", code="CHAT_NOT_OPEN")
    if order.delivered_at is not None:
        raise ConflictError("Chat closed — delivery completed.", code="CHAT_CLOSED")

    delivery_q = await db.execute(
        sa.select(Delivery).where(Delivery.order_id == order.id)
    )
    delivery = delivery_q.scalar_one_or_none()

    if sender.role == "admin":
        role = "admin"
    elif sender.id == order.customer_id:
        role = "customer"
    elif delivery is not None and delivery.driver_id == sender.id:
        role = "driver"
    else:
        raise AuthorizationError("Not a participant.", code="PERMISSION_DENIED")

    # Only 'customer' and 'driver' are allowed by the CHECK constraint.
    if role == "admin":
        raise AuthorizationError(
            "Admins cannot post in order chats.", code="PERMISSION_DENIED"
        )

    msg = OrderMessage(
        order_id=order.id,
        sender_id=sender.id,
        sender_role=role,
        ciphertext=ciphertext,
        nonce=nonce,
    )
    db.add(msg)
    await db.flush()
    return msg
