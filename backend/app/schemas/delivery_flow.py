"""Pydantic schemas for the Uber-style delivery flow (migration 0010)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AcceptOrderResponse(BaseModel):
    order_id: uuid.UUID
    driver_accepted_at: datetime
    code_expires_at: Optional[datetime] = None


class DriverLocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)


class DriverRouteResponse(BaseModel):
    """Non-customer view — safe to show driver/admin the drop-off coords."""

    order_id: uuid.UUID
    customer_lat: Optional[float]
    customer_lng: Optional[float]
    polyline: Optional[str] = None


class CompleteDeliveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class CompleteDeliveryResponse(BaseModel):
    order_id: uuid.UUID
    delivered_at: datetime


class CompleteDeliveryFailure(BaseModel):
    attempts_used: int
    attempts_remaining: int
    locked: bool


class CustomerETAResponse(BaseModel):
    """Coordinate-free — customers never see driver lat/lng."""

    order_id: uuid.UUID
    eta_seconds: Optional[int] = None
    last_update_at: Optional[datetime] = None


class CustomerCodeResponse(BaseModel):
    order_id: uuid.UUID
    code: str
    locked: bool
    attempts_used: int


class OrderMessageResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    sender_id: Optional[uuid.UUID]
    sender_role: str
    ciphertext: str
    nonce: str
    created_at: datetime


class TrackingPointResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    driver_id: Optional[uuid.UUID]
    lat: float
    lng: float
    recorded_at: datetime


class AdminTrackingListResponse(BaseModel):
    points: list[TrackingPointResponse]


class AdminMessagesListResponse(BaseModel):
    messages: list[OrderMessageResponse]
