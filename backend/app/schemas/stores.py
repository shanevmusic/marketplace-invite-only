"""Pydantic v2 schemas for /stores endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CreateStoreRequest(BaseModel):
    """Body for POST /api/v1/stores — seller creates their one store."""

    name: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=255)


class UpdateStoreRequest(BaseModel):
    """Body for PATCH /api/v1/stores/me — partial update."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    city: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    is_active: Optional[bool] = None


class StoreResponse(BaseModel):
    """Store object returned by /stores endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seller_id: uuid.UUID
    name: str
    slug: str
    description: str
    city: str
    is_active: bool
    created_at: datetime
