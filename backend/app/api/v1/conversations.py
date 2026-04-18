"""Conversations + messages endpoints (Phase 6, ADR-0008, ADR-0009, ADR-0013)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.conversations import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageListResponse,
    MessageResponse,
    SendMessageRequest,
)
from app.services import messaging_service
from app.ws import gateway as ws_gateway


router = APIRouter(prefix="/conversations", tags=["conversations", "messages"])


def _render_msg(msg) -> MessageResponse:
    return MessageResponse(**messaging_service.message_to_response_dict(msg))


@router.post("", response_model=ConversationResponse, status_code=201)
@limiter.limit("30/minute")
async def create_conversation(
    request: Request,
    body: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> ConversationResponse:
    conv = await messaging_service.create_conversation(
        db, caller=caller, peer_user_id=body.peer_user_id
    )
    unread = await messaging_service.unread_count(
        db, conversation_id=conv.id, caller_id=caller.id
    )
    return ConversationResponse(
        **messaging_service.conversation_to_response_dict(
            conv, caller_id=caller.id, unread=unread
        )
    )


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> ConversationListResponse:
    convs = await messaging_service.list_conversations_for_caller(
        db, caller=caller, limit=limit
    )
    out = []
    for c in convs:
        unread = await messaging_service.unread_count(
            db, conversation_id=c.id, caller_id=caller.id
        )
        out.append(
            ConversationResponse(
                **messaging_service.conversation_to_response_dict(
                    c, caller_id=caller.id, unread=unread
                )
            )
        )
    return ConversationListResponse(data=out)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> ConversationResponse:
    conv = await messaging_service.get_conversation(
        db, caller=caller, conversation_id=conversation_id
    )
    unread = await messaging_service.unread_count(
        db, conversation_id=conv.id, caller_id=caller.id
    )
    return ConversationResponse(
        **messaging_service.conversation_to_response_dict(
            conv, caller_id=caller.id, unread=unread
        )
    )


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: uuid.UUID,
    before: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> MessageListResponse:
    rows = await messaging_service.list_messages(
        db,
        caller=caller,
        conversation_id=conversation_id,
        before=before,
        limit=limit,
    )
    next_cursor = rows[-1].sent_at.isoformat() if len(rows) == limit else None
    return MessageListResponse(
        data=[_render_msg(m) for m in rows], next_cursor=next_cursor
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=201,
)
@limiter.limit("60/minute")
async def send_message(
    request: Request,
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> MessageResponse:
    msg = await messaging_service.store_message(
        db,
        caller=caller,
        conversation_id=conversation_id,
        ciphertext=body.ciphertext_bytes(),
        nonce=body.nonce_bytes(),
        ephemeral_public_key=body.ephemeral_public_key_bytes(),
        recipient_key_id=body.recipient_key_id,
    )
    payload = messaging_service.message_to_response_dict(msg)
    # Broadcast after DB flush so WS subscribers see the persisted row.
    await ws_gateway.broadcast_message_new(conversation_id, payload)
    return MessageResponse(**payload)


@router.post(
    "/{conversation_id}/messages/{message_id}/read",
    response_model=MessageResponse,
)
@limiter.limit("120/minute")
async def mark_read(
    request: Request,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> MessageResponse:
    msg = await messaging_service.mark_message_read(
        db,
        caller=caller,
        conversation_id=conversation_id,
        message_id=message_id,
    )
    payload = messaging_service.message_to_response_dict(msg)
    await ws_gateway.broadcast_message_read(conversation_id, payload)
    return MessageResponse(**payload)
