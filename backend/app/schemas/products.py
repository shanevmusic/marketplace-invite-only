"""Pydantic v2 schemas for /products endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductImageIn(BaseModel):
    """Image metadata accepted on product create/update.

    No file upload in Phase 4 — only the S3/GCS object key + display order.
    """

    s3_key: str = Field(min_length=1, max_length=1024)
    display_order: int = Field(default=0, ge=0)


class ProductImageOut(BaseModel):
    """Image metadata in product responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    s3_key: str
    display_order: int


class CreateProductRequest(BaseModel):
    """Body for POST /api/v1/products."""

    store_id: Optional[uuid.UUID] = Field(
        default=None,
        description=(
            "Optional — defaults to the caller's store.  Required if caller "
            "has more than one store (not currently supported)."
        ),
    )
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=10000)
    price_minor: int = Field(gt=0, description="Price in platform minor units (e.g. cents).")
    stock_quantity: Optional[int] = Field(
        default=None,
        ge=0,
        description="NULL = unlimited stock.",
    )
    images: list[ProductImageIn] = Field(default_factory=list)


class UpdateProductRequest(BaseModel):
    """Body for PATCH /api/v1/products/{id} — partial update."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=10000)
    price_minor: Optional[int] = Field(default=None, gt=0)
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None
    # If provided, replaces the existing image set wholesale.
    images: Optional[list[ProductImageIn]] = None


class ProductResponse(BaseModel):
    """Full product response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seller_id: uuid.UUID
    store_id: uuid.UUID
    name: str
    description: str
    price_minor: int
    stock_quantity: Optional[int]
    is_active: bool
    created_at: datetime
    images: list[ProductImageOut] = Field(default_factory=list)


class ProductListItem(BaseModel):
    """Compact product representation for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seller_id: uuid.UUID
    store_id: uuid.UUID
    name: str
    price_minor: int
    stock_quantity: Optional[int]
    is_active: bool
    image_s3_key: Optional[str] = None


class ProductListResponse(BaseModel):
    """Paginated list of products."""

    data: list[ProductListItem]
    pagination: dict[str, object]
