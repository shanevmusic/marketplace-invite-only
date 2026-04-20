"""Delivery-flow router — Uber-style accept/track/complete endpoints.

Covers:
- Driver  : accept, POST location, GET route, POST complete (with code).
- Customer: GET eta, GET code.
- Admin   : GET tracking points, GET messages (archived).
- Chat    : POST message, GET messages.

Customer never sees driver lat/lng — only ETA seconds.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user, get_db
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.delivery_flow import (
    AcceptOrderResponse,
    AdminMessagesListResponse,
    AdminTrackingListResponse,
    CompleteDeliveryRequest,
    CompleteDeliveryResponse,
    CustomerCodeResponse,
    CustomerETAResponse,
    DriverLocationRequest,
    DriverRouteResponse,
    OrderMessageResponse,
    TrackingPointResponse,
)
from app.services import delivery_flow_service as flow


router = APIRouter(tags=["delivery-flow"])


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


@router.post(
    "/driver/orders/{order_id}/accept",
    response_model=AcceptOrderResponse,
)
@limiter.limit("60/minute")
async def driver_accept(
    request: Request,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> AcceptOrderResponse:
    order, _code = await flow.accept_order(db, driver=caller, order_id=order_id)
    return AcceptOrderResponse(
        order_id=order.id,
        driver_accepted_at=order.driver_accepted_at,  # type: ignore[arg-type]
    )


@router.post(
    "/driver/orders/{order_id}/location",
    status_code=204,
)
@limiter.limit("600/minute")
async def driver_location(
    request: Request,
    order_id: uuid.UUID,
    body: DriverLocationRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> None:
    await flow.record_location(
        db, driver=caller, order_id=order_id, lat=body.lat, lng=body.lng
    )


@router.get(
    "/driver/orders/{order_id}/route",
    response_model=DriverRouteResponse,
)
async def driver_route(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> DriverRouteResponse:
    if caller.role not in ("driver", "admin"):
        raise AuthorizationError("Driver only.", code="PERMISSION_DENIED")
    data = await flow.get_route(db, caller=caller, order_id=order_id)
    return DriverRouteResponse(**data)


@router.post(
    "/driver/orders/{order_id}/complete",
    response_model=CompleteDeliveryResponse,
)
@limiter.limit("30/minute")
async def driver_complete(
    request: Request,
    order_id: uuid.UUID,
    body: CompleteDeliveryRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> CompleteDeliveryResponse:
    order = await flow.complete_delivery(
        db, driver=caller, order_id=order_id, submitted=body.code
    )
    return CompleteDeliveryResponse(
        order_id=order.id, delivered_at=order.delivered_at  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------


@router.get(
    "/customer/orders/{order_id}/eta",
    response_model=CustomerETAResponse,
)
async def customer_eta(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> CustomerETAResponse:
    # Caller must own the order or be admin.
    from app.models.order import Order

    order = await db.get(Order, order_id)
    if order is None or order.deleted_at is not None:
        raise NotFoundError("Order not found.", code="ORDER_NOT_FOUND")
    if caller.role != "admin" and order.customer_id != caller.id:
        raise NotFoundError("Order not found.", code="ORDER_NOT_FOUND")

    eta_seconds, last_update = await flow.compute_eta_seconds(db, order_id=order_id)
    return CustomerETAResponse(
        order_id=order_id, eta_seconds=eta_seconds, last_update_at=last_update
    )


@router.get(
    "/customer/orders/{order_id}/code",
    response_model=CustomerCodeResponse,
)
async def customer_code(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> CustomerCodeResponse:
    code = await flow.get_delivery_code_for_customer(
        db, customer=caller, order_id=order_id
    )
    return CustomerCodeResponse(
        order_id=code.order_id,
        code=code.code_plain,
        locked=code.locked,
        attempts_used=code.attempts_used,
    )


# ---------------------------------------------------------------------------
# Order chat — REST (WebSocket would be better; REST for simplicity v1)
# ---------------------------------------------------------------------------


from pydantic import BaseModel, ConfigDict, Field


class PostMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ciphertext: str = Field(min_length=1, max_length=4096)
    nonce: str = Field(min_length=1, max_length=64)


@router.get(
    "/orders/{order_id}/chat",
    response_model=list[OrderMessageResponse],
)
async def list_chat(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> list[OrderMessageResponse]:
    from app.models.order import Order
    from app.models.delivery import Delivery
    import sqlalchemy as sa

    order = await db.get(Order, order_id)
    if order is None or order.deleted_at is not None:
        raise NotFoundError("Order not found.", code="ORDER_NOT_FOUND")

    include_archived = caller.role == "admin"
    if caller.role != "admin":
        delivery_q = await db.execute(
            sa.select(Delivery).where(Delivery.order_id == order.id)
        )
        delivery = delivery_q.scalar_one_or_none()
        is_customer = caller.id == order.customer_id
        is_driver = delivery is not None and delivery.driver_id == caller.id
        if not (is_customer or is_driver):
            raise NotFoundError("Order not found.", code="ORDER_NOT_FOUND")
        if order.delivered_at is not None:
            # Chat gone for non-admins after delivery.
            return []

    msgs = await flow.list_order_messages(
        db, order_id=order_id, include_archived=include_archived
    )
    return [
        OrderMessageResponse(
            id=m.id,
            order_id=m.order_id,
            sender_id=m.sender_id,
            sender_role=m.sender_role,
            ciphertext=m.ciphertext,
            nonce=m.nonce,
            created_at=m.created_at,
        )
        for m in msgs
    ]


@router.post(
    "/orders/{order_id}/chat",
    response_model=OrderMessageResponse,
    status_code=201,
)
@limiter.limit("120/minute")
async def post_chat(
    request: Request,
    order_id: uuid.UUID,
    body: PostMessageRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderMessageResponse:
    msg = await flow.post_order_message(
        db,
        sender=caller,
        order_id=order_id,
        ciphertext=body.ciphertext,
        nonce=body.nonce,
    )
    return OrderMessageResponse(
        id=msg.id,
        order_id=msg.order_id,
        sender_id=msg.sender_id,
        sender_role=msg.sender_role,
        ciphertext=msg.ciphertext,
        nonce=msg.nonce,
        created_at=msg.created_at,
    )


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/admin", tags=["admin-delivery-flow"])


@admin_router.get(
    "/orders/{order_id}/tracking",
    response_model=AdminTrackingListResponse,
)
async def admin_tracking(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminTrackingListResponse:
    points = await flow.list_tracking_points(db, order_id=order_id)
    return AdminTrackingListResponse(
        points=[
            TrackingPointResponse(
                id=p.id,
                order_id=p.order_id,
                driver_id=p.driver_id,
                lat=p.lat,
                lng=p.lng,
                recorded_at=p.recorded_at,
            )
            for p in points
        ]
    )


@admin_router.get(
    "/orders/{order_id}/messages",
    response_model=AdminMessagesListResponse,
)
async def admin_messages(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminMessagesListResponse:
    msgs = await flow.list_order_messages(
        db, order_id=order_id, include_archived=True
    )
    return AdminMessagesListResponse(
        messages=[
            OrderMessageResponse(
                id=m.id,
                order_id=m.order_id,
                sender_id=m.sender_id,
                sender_role=m.sender_role,
                ciphertext=m.ciphertext,
                nonce=m.nonce,
                created_at=m.created_at,
            )
            for m in msgs
        ]
    )
