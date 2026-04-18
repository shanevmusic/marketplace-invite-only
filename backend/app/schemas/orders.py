"""Pydantic schemas for the orders, deliveries, and admin-orders routers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Address (embedded JSONB)
# ---------------------------------------------------------------------------


class Address(BaseModel):
    """Shipping/delivery address embedded in the order.

    All fields are strings except lat/lng.  Matches the JSONB shape
    documented on ``orders.delivery_address``.
    """

    line1: str = Field(min_length=1, max_length=255)
    line2: Optional[str] = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    region: Optional[str] = Field(default=None, max_length=100)
    postal: Optional[str] = Field(default=None, max_length=32)
    country: str = Field(min_length=2, max_length=2)
    lat: Optional[float] = None
    lng: Optional[float] = None
    notes: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------


class OrderLineItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0, le=10000)


class CreateOrderRequest(BaseModel):
    items: list[OrderLineItemIn] = Field(min_length=1, max_length=100)
    delivery_address: Address


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class OrderLineItemOut(BaseModel):
    id: uuid.UUID
    product_id: Optional[uuid.UUID] = None
    product_name_snapshot: str
    unit_price_minor_snapshot: int
    quantity: int


class DeliveryOut(BaseModel):
    id: uuid.UUID
    driver_id: Optional[uuid.UUID] = None
    seller_id: uuid.UUID
    status: str
    started_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class DriverAssignmentOut(BaseModel):
    id: uuid.UUID
    driver_id: Optional[uuid.UUID] = None
    status: str
    requested_at: datetime
    assigned_at: Optional[datetime] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    seller_id: uuid.UUID
    store_id: uuid.UUID
    status: str
    subtotal_minor: int
    total_minor: int
    delivery_address: dict[str, Any]
    placed_at: datetime
    accepted_at: Optional[datetime] = None
    preparing_at: Optional[datetime] = None
    out_for_delivery_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    items: list[OrderLineItemOut] = []
    delivery: Optional[DeliveryOut] = None
    driver_assignment: Optional[DriverAssignmentOut] = None


class OrderListResponse(BaseModel):
    data: list[OrderResponse]


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class CancelOrderRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Driver assignment (admin)
# ---------------------------------------------------------------------------


class AssignDriverRequest(BaseModel):
    driver_id: uuid.UUID


# ---------------------------------------------------------------------------
# Retention settings
# ---------------------------------------------------------------------------


class RetentionSettingsResponse(BaseModel):
    retention_min_days: int
    order_auto_complete_grace_hours: int


class UpdateRetentionSettingsRequest(BaseModel):
    retention_min_days: Optional[int] = Field(default=None, ge=1, le=3650)
    order_auto_complete_grace_hours: Optional[int] = Field(default=None, ge=1, le=720)


# ---------------------------------------------------------------------------
# Purge job
# ---------------------------------------------------------------------------


class PurgeJobResponse(BaseModel):
    purged_count: int
    auto_completed_count: int
