"""Admin-facing endpoints for order fulfillment + retention + purge."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.orders import (
    AssignDriverRequest,
    OrderResponse,
    PurgeJobResponse,
    RetentionSettingsResponse,
    UpdateRetentionSettingsRequest,
)
from app.services import order_service


router = APIRouter(prefix="/admin", tags=["admin"])


def _render_order(order) -> OrderResponse:
    return OrderResponse(**order_service.order_to_response_dict(order))


@router.post("/orders/{order_id}/assign-driver", response_model=OrderResponse)
@limiter.limit("60/minute")
async def assign_driver(
    request: Request,
    order_id: uuid.UUID,
    body: AssignDriverRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> OrderResponse:
    order = await order_service.assign_driver(
        db, caller=caller, order_id=order_id, driver_id=body.driver_id
    )
    return _render_order(order)


@router.get("/settings/retention", response_model=RetentionSettingsResponse)
async def get_retention_settings(
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> RetentionSettingsResponse:
    ps = await order_service.get_retention_settings(db)
    return RetentionSettingsResponse(
        retention_min_days=ps.retention_min_days,
        order_auto_complete_grace_hours=ps.order_auto_complete_grace_hours,
    )


@router.patch("/settings/retention", response_model=RetentionSettingsResponse)
@limiter.limit("30/minute")
async def patch_retention_settings(
    request: Request,
    body: UpdateRetentionSettingsRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> RetentionSettingsResponse:
    ps = await order_service.update_retention_settings(
        db,
        caller=caller,
        retention_min_days=body.retention_min_days,
        order_auto_complete_grace_hours=body.order_auto_complete_grace_hours,
    )
    return RetentionSettingsResponse(
        retention_min_days=ps.retention_min_days,
        order_auto_complete_grace_hours=ps.order_auto_complete_grace_hours,
    )


@router.post("/jobs/purge-orders", response_model=PurgeJobResponse)
@limiter.limit("6/minute")
async def run_purge_job(
    request: Request,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> PurgeJobResponse:
    result = await order_service.run_purge_job(db)
    return PurgeJobResponse(**result)
