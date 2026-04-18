"""Uploads router — presigned S3 PUT URLs plus post-upload confirmation."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.rate_limiter import limiter
from app.models.user import User
from app.services import upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


class PresignRequest(BaseModel):
    purpose: Literal["product_image", "avatar"]
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=64)


class ConfirmRequest(BaseModel):
    s3_key: str = Field(min_length=1, max_length=1024)


@router.post("/presign")
@limiter.limit("20/minute")
async def presign_upload(
    request: Request,
    body: PresignRequest,
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Return a presigned PUT URL for a direct-to-S3 upload."""
    return upload_service.presign_upload(
        user_id=user.id,
        purpose=body.purpose,
        filename=body.filename,
        content_type=body.content_type,
    )


@router.post("/confirm")
@limiter.limit("20/minute")
async def confirm_upload(
    request: Request,
    body: ConfirmRequest,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Confirm a completed upload and receive the final CDN URL."""
    return upload_service.confirm_upload(s3_key=body.s3_key)
