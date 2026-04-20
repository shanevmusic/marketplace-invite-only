"""Orders router — customer/seller/driver-facing endpoints."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.orders import (
    CancelOrderRequest,
    CreateOrderRequest,
    OrderListResponse,
    OrderResponse,
)
from app.services import delivery_tracking_service as dts
from app.services import order_service
from app.ws import gateway as ws_gateway


router = APIRouter(prefix="/orders", tags=["orders"])


def _render(order) -> OrderResponse:
    return OrderResponse(**order_service.order_to_response_dict(order))


@router.post("", response_model=OrderResponse, status_code=201)
@limiter.limit("30/minute")
async def create_order(
    request: Request,
    body: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderResponse:
    """Customer places an order."""
    order = await order_service.create_order(
        db,
        customer=caller,
        items=[
            {"product_id": item.product_id, "quantity": item.quantity}
            for item in body.items
        ],
        delivery_address=body.delivery_address.model_dump(),
    )
    return _render(order)


@router.get("", response_model=OrderListResponse)
async def list_orders(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderListResponse:
    """List orders visible to the caller — with retention masking."""
    orders = await order_service.list_orders_for_caller(
        db, caller, status=status, limit=limit
    )

    rendered: list[OrderResponse] = []
    for o in orders:
        if caller.role == "customer" and order_service.is_customer_hidden(o):
            continue  # 30-min post-delivery hide window
        if caller.role == "customer" and order_service.is_customer_masked(o):
            rendered.append(
                OrderResponse(**order_service.mask_customer_order_response(o))
            )
            continue
        if caller.role == "seller" and order_service.is_seller_stripped(o):
            rendered.append(
                OrderResponse(**order_service.mask_seller_order_response(o))
            )
            continue
        rendered.append(_render(o))
    return OrderListResponse(data=rendered)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderResponse:
    order = await order_service.get_order_for_caller(db, caller, order_id)
    return _render(order)


@router.post("/{order_id}/accept", response_model=OrderResponse)
@limiter.limit("60/minute")
async def accept_order(
    request: Request,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderResponse:
    order = await order_service.accept_order(db, caller=caller, order_id=order_id)
    return _render(order)


@router.post("/{order_id}/preparing", response_model=OrderResponse)
@limiter.limit("60/minute")
async def mark_preparing(
    request: Request,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderResponse:
    order = await order_service.mark_preparing(db, caller=caller, order_id=order_id)
    return _render(order)


@router.post("/{order_id}/self-deliver", response_model=OrderResponse)
@limiter.limit("60/minute")
async def self_deliver(
    request: Request,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderResponse:
    order = await order_service.choose_self_delivery(
        db, caller=caller, order_id=order_id
    )
    return _render(order)


@router.post("/{order_id}/request-driver", response_model=OrderResponse)
@limiter.limit("60/minute")
async def request_driver(
    request: Request,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderResponse:
    order = await order_service.request_driver(
        db, caller=caller, order_id=order_id
    )
    return _render(order)


@router.post("/{order_id}/out-for-delivery", response_model=OrderResponse)
@limiter.limit("60/minute")
async def out_for_delivery(
    request: Request,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderResponse:
    order = await order_service.out_for_delivery(
        db, caller=caller, order_id=order_id
    )
    # Broadcast delivery.status (customer-safe) to all delivery subscribers.
    started_at = order.delivery.started_at if order.delivery is not None else None
    await ws_gateway.broadcast_delivery_event_all(
        order.id,
        dts.status_event(order.id, "out_for_delivery", started_at=started_at),
    )
    return _render(order)


@router.post("/{order_id}/delivered", response_model=OrderResponse)
@limiter.limit("60/minute")
async def delivered(
    request: Request,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderResponse:
    order = await order_service.mark_delivered(
        db, caller=caller, order_id=order_id
    )
    delivered_at = order.delivered_at
    await ws_gateway.broadcast_delivery_event_all(
        order.id,
        dts.status_event(order.id, "delivered", delivered_at=delivered_at),
    )
    return _render(order)


@router.post("/{order_id}/complete", response_model=OrderResponse)
@limiter.limit("60/minute")
async def complete_order(
    request: Request,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderResponse:
    order = await order_service.complete_order(
        db, caller=caller, order_id=order_id
    )
    return _render(order)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
@limiter.limit("30/minute")
async def cancel_order(
    request: Request,
    order_id: uuid.UUID,
    body: CancelOrderRequest | None = None,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> OrderResponse:
    reason = body.reason if body is not None else None
    order = await order_service.cancel_order(
        db, caller=caller, order_id=order_id, reason=reason
    )
    return _render(order)


@router.delete("/{order_id}", status_code=204)
@limiter.limit("30/minute")
async def delete_order(
    request: Request,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> Response:
    await order_service.delete_order(db, caller=caller, order_id=order_id)
    return Response(status_code=204)
