"""Products router.

Endpoints:
    POST   /products          — seller creates a product (owns store required)
    GET    /products          — role-scoped list (seller own, customer referral-scoped, admin any)
    GET    /products/{id}     — visibility-enforced get
    PATCH  /products/{id}     — seller own, admin any
    DELETE /products/{id}     — seller own, admin any (soft-delete)
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_roles
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.products import (
    CreateProductRequest,
    ProductListItem,
    ProductListResponse,
    ProductResponse,
    UpdateProductRequest,
)
from app.services import product_service


router = APIRouter(prefix="/products", tags=["products"])

_seller_only = require_roles("seller")
_seller_or_admin = require_roles("seller", "admin")


def _images_to_dicts(images: list) -> list[dict]:
    return [
        {"s3_key": img.s3_key, "display_order": img.display_order}
        for img in images
    ]


@router.post("", response_model=ProductResponse, status_code=201)
@limiter.limit("60/minute")
async def create_product(
    request: Request,
    body: CreateProductRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(_seller_only),
) -> ProductResponse:
    """Seller creates a product in their store."""
    product = await product_service.create_product(
        db,
        caller=caller,
        name=body.name,
        price_minor=body.price_minor,
        description=body.description,
        stock_quantity=body.stock_quantity,
        images=_images_to_dicts(body.images),
        store_id=body.store_id,
    )
    return ProductResponse(**product_service.product_to_response_dict(product))


@router.get("", response_model=ProductListResponse)
async def list_products(
    store_id: Optional[uuid.UUID] = Query(default=None),
    seller_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> ProductListResponse:
    """List visible products for the caller."""
    products = await product_service.list_products_for_caller(
        db,
        caller,
        store_id=store_id,
        seller_id=seller_id,
        limit=limit,
    )
    items = [
        ProductListItem(**product_service.product_to_list_item_dict(p))
        for p in products
    ]
    return ProductListResponse(
        data=items,
        pagination={"next_cursor": None, "has_more": False},
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> ProductResponse:
    """Visibility-enforced product read."""
    product = await product_service.get_product_for_caller(db, caller, product_id)
    return ProductResponse(**product_service.product_to_response_dict(product))


@router.patch("/{product_id}", response_model=ProductResponse)
async def patch_product(
    product_id: uuid.UUID,
    body: UpdateProductRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(_seller_or_admin),
) -> ProductResponse:
    """Seller patches own product; admin may patch any."""
    images_payload: Optional[list[dict]] = None
    if body.images is not None:
        images_payload = _images_to_dicts(body.images)
    product = await product_service.update_product(
        db,
        caller=caller,
        product_id=product_id,
        name=body.name,
        description=body.description,
        price_minor=body.price_minor,
        stock_quantity=body.stock_quantity,
        is_active=body.is_active,
        images=images_payload,
    )
    return ProductResponse(**product_service.product_to_response_dict(product))


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(_seller_or_admin),
) -> Response:
    """Soft-delete a product (lifetime sales remain intact)."""
    await product_service.soft_delete_product(
        db, caller=caller, product_id=product_id
    )
    return Response(status_code=204)
