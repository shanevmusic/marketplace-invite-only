"""Pydantic schemas for delivery tracking (Phase 7).

CRITICAL invariant: ``CustomerDeliveryView`` and ``CustomerDeliveryEvent``
must NEVER carry lat/lng or driver identity fields.  ``extra='forbid'``
ensures accidental additions at call-sites are rejected.

Internal vs customer payloads are separate Pydantic TYPES — not two views
over a single model — so there is structurally no way to leak server-side
coordinates to the customer channel.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class LocationUpdateRequest(BaseModel):
    """Driver/seller posts their current position + optional ETA / distance."""

    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    eta_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    distance_meters: Optional[int] = Field(default=None, ge=0, le=10_000_000)


class AdminDeliveryPatchRequest(BaseModel):
    """Admin override.  All fields optional."""

    driver_id: Optional[uuid.UUID] = None
    distance_meters: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    duration_seconds: Optional[int] = Field(default=None, ge=0, le=604_800)


# ---------------------------------------------------------------------------
# Internal response (driver/seller/admin)
# ---------------------------------------------------------------------------


class InternalDeliveryView(BaseModel):
    """Full internal view — includes coordinates, driver info, metrics."""

    model_config = ConfigDict(extra="forbid")

    order_id: uuid.UUID
    delivery_id: uuid.UUID
    status: str
    driver_id: Optional[uuid.UUID] = None
    seller_id: uuid.UUID
    started_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    last_known_lat: Optional[float] = None
    last_known_lng: Optional[float] = None
    last_location_at: Optional[datetime] = None
    current_eta_seconds: Optional[int] = None
    current_eta_updated_at: Optional[datetime] = None
    distance_meters: Optional[int] = None
    duration_seconds: Optional[int] = None
    customer_delivery_address: dict[str, Any]


# ---------------------------------------------------------------------------
# Customer response
# ---------------------------------------------------------------------------


class CustomerDeliveryView(BaseModel):
    """Customer-safe view.  NO lat/lng, NO driver identity.

    extra='forbid' ensures that if a developer ever forwards an
    unvetted dict into this model, Pydantic raises instead of silently
    accepting coordinate fields.
    """

    model_config = ConfigDict(extra="forbid")

    order_id: uuid.UUID
    status: str
    eta_seconds: Optional[int] = None
    eta_updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    delivery_address: dict[str, Any]


# ---------------------------------------------------------------------------
# WebSocket events — customer side
# ---------------------------------------------------------------------------


class CustomerDeliveryEtaEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["delivery.eta"]
    order_id: uuid.UUID
    eta_seconds: Optional[int] = None
    eta_updated_at: Optional[datetime] = None


class CustomerDeliveryStatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["delivery.status"]
    order_id: uuid.UUID
    status: str
    started_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class CustomerDeliverySubscribedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["delivery.subscribed"]
    order_id: uuid.UUID
