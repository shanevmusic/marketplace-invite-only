"""Stores router.

Endpoints:
    POST   /stores            — seller creates their one store (201 or 409)
    GET    /stores/me         — seller reads own store (404 if none)
    PATCH  /stores/me         — seller patches own store
    GET    /stores/{id}       — admin / seller (own) / customer (referral-scoped)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_roles
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.stores import (
    CreateStoreRequest,
    StoreResponse,
    UpdateStoreRequest,
)
from app.services import store_service


router = APIRouter(prefix="/stores", tags=["stores"])

_seller_only = require_roles("seller")


@router.post("", response_model=StoreResponse, status_code=201)
@limiter.limit("10/minute")
async def create_store(
    request: Request,
    body: CreateStoreRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(_seller_only),
) -> StoreResponse:
    """Seller creates their one-and-only store."""
    store = await store_service.create_store(
        db,
        caller=caller,
        name=body.name,
        city=body.city,
        description=body.description,
        slug=body.slug,
    )
    # Reload the seller so the response city matches what we persisted.
    seller = await store_service._get_caller_seller(db, caller)
    return StoreResponse(**store_service.store_to_response_dict(store, seller))


@router.get("/me", response_model=StoreResponse)
async def get_my_store(
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(_seller_only),
) -> StoreResponse:
    """Return the caller's store (404 if they have not created one)."""
    store = await store_service.get_own_store(db, caller)
    seller = await store_service._get_caller_seller(db, caller)
    return StoreResponse(**store_service.store_to_response_dict(store, seller))


@router.patch("/me", response_model=StoreResponse)
async def patch_my_store(
    body: UpdateStoreRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(_seller_only),
) -> StoreResponse:
    """Partial update of the caller's own store."""
    store = await store_service.update_own_store(
        db,
        caller=caller,
        name=body.name,
        city=body.city,
        description=body.description,
        is_active=body.is_active,
    )
    seller = await store_service._get_caller_seller(db, caller)
    return StoreResponse(**store_service.store_to_response_dict(store, seller))


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store_by_id(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> StoreResponse:
    """Visibility-scoped read of a store by ID.

    - admin: any store.
    - seller: only own store (404 otherwise).
    - customer: only the store of their direct referring seller (404 otherwise).
    - driver: 404 (drivers do not browse).
    """
    store, seller = await store_service.get_store_for_caller(db, caller, store_id)
    return StoreResponse(**store_service.store_to_response_dict(store, seller))
