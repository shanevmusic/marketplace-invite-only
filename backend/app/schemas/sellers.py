"""Pydantic v2 schemas for /sellers endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SellerResponse(BaseModel):
    """Seller profile object."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    bio: Optional[str]
    city: str
    country_code: str
    created_at: datetime


class SellerPublicResponse(BaseModel):
    """Reduced seller projection for referral-scoped customer view."""

    id: uuid.UUID
    display_name: str
    bio: Optional[str]
    city: str


class SellerDashboardResponse(BaseModel):
    """GET /sellers/me/dashboard response.

    Lifetime metrics are read from ``order_analytics_snapshots`` (see
    ``docs/phase-4-notes.md``) so they survive product soft-delete and
    order hard-delete.
    """

    seller_id: uuid.UUID
    lifetime_sales_amount: int = Field(
        description="Total lifetime revenue in platform minor units (e.g. cents)."
    )
    lifetime_orders_count: int = Field(
        description="Total lifetime delivered orders."
    )
    active_orders_count: int = Field(
        description=(
            "Orders currently in a non-terminal state "
            "(pending, accepted, preparing, out_for_delivery)."
        )
    )
    currency_code: str
    last_updated: datetime
