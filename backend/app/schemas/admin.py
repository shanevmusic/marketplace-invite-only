"""Pydantic schemas for Phase 11 admin endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class AdminUserSummary(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    status: str
    is_active: bool
    created_at: datetime
    suspended_at: Optional[datetime] = None
    suspended_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class ReferralEdge(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    role: str
    created_at: datetime


class AdminUserDetail(AdminUserSummary):
    referred_by: Optional[ReferralEdge] = None
    referred_users: list[ReferralEdge] = Field(default_factory=list)


class SuspendUserRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class AdminListResponse(BaseModel):
    data: list[Any]
    pagination: dict[str, Any]


class AdminUserListResponse(BaseModel):
    data: list[AdminUserSummary]
    pagination: dict[str, Any]


# ---------------------------------------------------------------------------
# Invites (admin override)
# ---------------------------------------------------------------------------


class AdminIssueInviteRequest(BaseModel):
    role_target: str
    expires_in_days: int = Field(default=7, ge=1, le=365)
    email_hint: Optional[str] = Field(default=None, max_length=255)


class AdminIssueInviteResponse(BaseModel):
    id: uuid.UUID
    token: str
    role_target: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


class AdminProductSummary(BaseModel):
    id: uuid.UUID
    seller_id: uuid.UUID
    store_id: uuid.UUID
    name: str
    price_minor: int
    stock_quantity: Optional[int]
    status: str
    is_active: bool
    disabled_at: Optional[datetime] = None
    disabled_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminProductListResponse(BaseModel):
    data: list[AdminProductSummary]
    pagination: dict[str, Any]


class DisableProductRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


class AdminOrderSummary(BaseModel):
    """Compact admin view of an order — keeps payload small for list screens."""

    id: uuid.UUID
    customer_id: uuid.UUID
    seller_id: uuid.UUID
    store_id: uuid.UUID
    status: str
    total_minor: int
    placed_at: datetime

    model_config = {"from_attributes": True}


class AdminOrderListResponse(BaseModel):
    data: list[AdminOrderSummary]
    pagination: dict[str, Any]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class AdminAnalyticsOverview(BaseModel):
    total_gmv_minor: int
    orders_count: int
    active_users_24h: int
    active_users_7d: int
    active_users_30d: int
    seller_count: int
    customer_count: int
    driver_count: int
    admin_count: int


class TopSellerEntry(BaseModel):
    seller_id: uuid.UUID
    display_name: str
    lifetime_revenue_minor: int
    lifetime_order_count: int


class TopSellersResponse(BaseModel):
    data: list[TopSellerEntry]


# ---------------------------------------------------------------------------
# Ops
# ---------------------------------------------------------------------------


class MigrationVersionResponse(BaseModel):
    version: Optional[str]
