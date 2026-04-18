"""Pydantic v2 schemas for invite endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateAdminInviteRequest(BaseModel):
    """Body for POST /api/v1/invites/admin."""

    role_target: str  # admin | seller | customer | driver
    expires_in_hours: int = Field(default=168, ge=1, le=8760)  # default 7d, max 1 year
    email_hint: Optional[str] = Field(default=None, max_length=255)


class CreateSellerReferralRequest(BaseModel):
    """Body for POST /api/v1/invites/seller_referral.

    No required fields — issuer is determined from the auth token.
    Idempotent: returns existing active referral if one exists.
    """


class RegenerateSellerReferralRequest(BaseModel):
    """Body for POST /api/v1/invites/seller_referral/regenerate.

    No body fields — caller is the seller from auth token.
    """


class ValidateInviteResponse(BaseModel):
    """Response for GET /api/v1/invites/validate?token=..."""

    type: str
    role_target: Optional[str]
    issuer_display_name: str
    issuer_role: str
    valid: bool
    already_used: bool
    expired: bool
    revoked: bool


class InviteResponse(BaseModel):
    """Full invite object returned on create/list."""

    id: uuid.UUID
    type: str
    token: Optional[str] = None  # Only returned on create
    role_target: Optional[str]
    max_uses: Optional[int]
    used_count: int
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime
    invite_url: Optional[str] = None

    model_config = {"from_attributes": True}


class InviteListResponse(BaseModel):
    """Paginated list of invites."""

    data: list[InviteResponse]
    pagination: dict[str, object]
