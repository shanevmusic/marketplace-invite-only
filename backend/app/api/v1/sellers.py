"""Sellers router.

Endpoints:
    GET    /sellers/me                 — seller reads own profile
    GET    /sellers/me/dashboard       — seller dashboard aggregates
    GET    /sellers/{id}               — admin any, customer referral-scoped
    GET    /sellers/{id}/dashboard     — admin only (view any seller's dashboard)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_roles
from app.models.user import User
from app.schemas.sellers import (
    SellerDashboardResponse,
    SellerPublicResponse,
    SellerResponse,
)
from app.services import seller_service


router = APIRouter(prefix="/sellers", tags=["sellers"])

_seller_only = require_roles("seller")
_admin_only = require_roles("admin")


@router.get("/me", response_model=SellerResponse)
async def get_my_seller(
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(_seller_only),
) -> SellerResponse:
    """Return the caller's seller profile."""
    seller = await seller_service.get_caller_seller(db, caller)
    return SellerResponse.model_validate(seller)


@router.get("/me/dashboard", response_model=SellerDashboardResponse)
async def get_my_dashboard(
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(_seller_only),
) -> SellerDashboardResponse:
    """Dashboard aggregates for the caller seller."""
    payload = await seller_service.get_dashboard(db, caller)
    return SellerDashboardResponse(**payload)


@router.get("/{seller_id}", response_model=SellerPublicResponse)
async def get_seller_by_id(
    seller_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> SellerPublicResponse:
    """Visibility-scoped seller profile read.

    - admin: any seller.
    - seller: only self (404 otherwise).
    - customer: only direct referring seller (404 otherwise).
    - driver / other: 404.
    """
    seller = await seller_service.get_seller_for_caller(db, caller, seller_id)
    return SellerPublicResponse(
        id=seller.id,
        display_name=seller.display_name,
        bio=seller.bio,
        city=seller.city,
    )


@router.get("/{seller_id}/dashboard", response_model=SellerDashboardResponse)
async def get_seller_dashboard_admin(
    seller_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(_admin_only),
) -> SellerDashboardResponse:
    """Admin view of any seller's dashboard."""
    payload = await seller_service.get_dashboard(
        db, caller, target_seller_id=seller_id
    )
    return SellerDashboardResponse(**payload)
