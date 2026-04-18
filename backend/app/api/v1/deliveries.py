"""Delivery tracking router — Phase 7.

Endpoints:
- POST   /deliveries/{order_id}/location   — driver/seller posts lat/lng/eta.
- GET    /deliveries/{order_id}/track      — role-appropriate view.
- PATCH  /admin/deliveries/{order_id}      — admin override / reassign.

All role gating goes through
``delivery_tracking_service.resolve_role`` so the same invariants hold
across REST and WS.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_user, get_db
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.delivery_tracking import (
    AdminDeliveryPatchRequest,
    CustomerDeliveryView,
    InternalDeliveryView,
    LocationUpdateRequest,
)
from app.services import delivery_tracking_service as dts
from app.ws import gateway as ws_gateway


router = APIRouter(prefix="/deliveries", tags=["deliveries"])
admin_router = APIRouter(prefix="/admin/deliveries", tags=["admin-deliveries"])


# ---------------------------------------------------------------------------
# Driver/seller POST location
# ---------------------------------------------------------------------------


@router.post("/{order_id}/location", status_code=204)
@limiter.limit("600/minute")
async def post_location(
    request: Request,
    order_id: uuid.UUID,
    body: LocationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> None:
    order, delivery = await dts.post_location(
        db,
        user=caller,
        order_id=order_id,
        lat=body.lat,
        lng=body.lng,
        eta_seconds=body.eta_seconds,
        distance_meters=body.distance_meters,
    )
    # Broadcast: internal-only for lat/lng breadcrumb; customer-safe for ETA.
    await ws_gateway.broadcast_delivery_location_internal(
        order.id, dts.internal_location_event(delivery)
    )
    if body.eta_seconds is not None:
        await ws_gateway.broadcast_delivery_event_all(
            order.id, dts.eta_event(delivery)
        )


# ---------------------------------------------------------------------------
# GET /track — role-appropriate
# ---------------------------------------------------------------------------


@router.get(
    "/{order_id}/track",
    response_model=InternalDeliveryView | CustomerDeliveryView,  # type: ignore[valid-type]
)
async def track(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> InternalDeliveryView | CustomerDeliveryView:
    return await dts.get_track_view(db, user=caller, order_id=order_id)


# ---------------------------------------------------------------------------
# Admin PATCH
# ---------------------------------------------------------------------------


@admin_router.patch(
    "/{order_id}",
    response_model=InternalDeliveryView,
)
@limiter.limit("60/minute")
async def admin_patch(
    request: Request,
    order_id: uuid.UUID,
    body: AdminDeliveryPatchRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> InternalDeliveryView:
    order, delivery = await dts.admin_patch_delivery(
        db,
        caller=caller,
        order_id=order_id,
        driver_id=body.driver_id,
        distance_meters=body.distance_meters,
        duration_seconds=body.duration_seconds,
    )
    return dts.build_internal_view(order, delivery)
