"""Pydantic v2 schemas for auth endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    """Body for POST /api/v1/auth/signup."""

    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    invite_token: str = Field(min_length=1)
    # For seller_referral: must be 'customer' or 'seller'.
    # For admin_invite: must match role_target or be omitted.
    role_choice: Optional[str] = Field(default=None)


class LoginRequest(BaseModel):
    """Body for POST /api/v1/auth/login."""

    email: EmailStr
    password: str
    device_label: Optional[str] = Field(default=None, max_length=255)


class TokenPair(BaseModel):
    """Token response returned on signup, login, and refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    """Body for POST /api/v1/auth/refresh."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Body for POST /api/v1/auth/logout."""

    refresh_token: str


class MeResponse(BaseModel):
    """Response for GET /api/v1/auth/me."""

    id: uuid.UUID
    email: str
    role: str
    display_name: str
    phone: Optional[str]
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    referring_seller_id: Optional[uuid.UUID]

    model_config = {"from_attributes": True}


class UserInSignup(BaseModel):
    """Slim user object embedded in signup/login responses."""

    id: uuid.UUID
    email: str
    role: str
    display_name: str

    model_config = {"from_attributes": True}


class SignupResponse(BaseModel):
    """Response body for 201 signup."""

    user: UserInSignup
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class LoginResponse(BaseModel):
    """Response body for 200 login."""

    user: UserInSignup
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class RefreshResponse(BaseModel):
    """Response body for 200 refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class UpdateMeRequest(BaseModel):
    """Body for PATCH /api/v1/auth/me."""

    display_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=32)
    avatar_url: Optional[str] = Field(default=None, max_length=2048)


class ChangePasswordRequest(BaseModel):
    """Body for POST /api/v1/auth/me/password."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class NotificationPrefsResponse(BaseModel):
    """Response for GET/PATCH /api/v1/auth/me/notifications."""

    push_enabled: bool
    email_enabled: bool
    order_updates: bool
    messages: bool
    marketing: bool

    model_config = {"from_attributes": True}


class UpdateNotificationPrefsRequest(BaseModel):
    """Body for PATCH /api/v1/auth/me/notifications."""

    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    order_updates: Optional[bool] = None
    messages: Optional[bool] = None
    marketing: Optional[bool] = None
