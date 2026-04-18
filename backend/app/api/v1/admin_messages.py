"""Admin endpoints: message retention config + purge job."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.conversations import (
    MessageRetentionResponse,
    PurgeMessagesResponse,
    UpdateMessageRetentionRequest,
)
from app.services import messaging_service


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/settings/message-retention", response_model=MessageRetentionResponse
)
async def get_message_retention(
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> MessageRetentionResponse:
    days = await messaging_service.get_message_retention_days(db)
    return MessageRetentionResponse(message_retention_days=days)


@router.patch(
    "/settings/message-retention", response_model=MessageRetentionResponse
)
@limiter.limit("30/minute")
async def patch_message_retention(
    request: Request,
    body: UpdateMessageRetentionRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> MessageRetentionResponse:
    days = await messaging_service.update_message_retention_days(
        db, caller=caller, days=body.message_retention_days
    )
    return MessageRetentionResponse(message_retention_days=days)


@router.post("/jobs/purge-messages", response_model=PurgeMessagesResponse)
@limiter.limit("6/minute")
async def run_purge_messages(
    request: Request,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> PurgeMessagesResponse:
    count = await messaging_service.purge_old_messages(db)
    return PurgeMessagesResponse(purged_count=count)
