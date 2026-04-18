"""Devices router — register FCM/APNs tokens for push notifications."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services import push_service

router = APIRouter(prefix="/devices", tags=["devices"])


class RegisterDeviceRequest(BaseModel):
    platform: Literal["ios", "android", "web"]
    token: str = Field(min_length=1, max_length=4096)


class RegisterDeviceResponse(BaseModel):
    id: str
    platform: str


@router.post("/register", response_model=RegisterDeviceResponse, status_code=201)
async def register_device(
    body: RegisterDeviceRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RegisterDeviceResponse:
    device = await push_service.register_device(
        db, user.id, body.platform, body.token
    )
    return RegisterDeviceResponse(id=str(device.id), platform=device.platform)
