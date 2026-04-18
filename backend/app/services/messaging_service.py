"""Messaging service — conversations, ciphertext messages, retention.

SECURITY INVARIANT (ADR-0009, ADR-0013): this module never calls any
crypto primitive against message content.  It stores and retrieves
opaque bytes, enforced by ``tests/test_messaging_ciphertext_only.py``.

Conversation eligibility (ADR-0013):
- Admins may converse with anyone.
- A customer may open a conversation with the seller that referred them.
- A seller may open a conversation with any customer whose
  ``referring_seller_id`` equals the seller's user id.
- All other pairs → 404 CONVERSATION_NOT_FOUND (no existence leak).
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConversationIneligible,
    ConversationNotFound,
    MessageRetentionInvalid,
    NotFoundError,
)
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.platform_settings import PlatformSettings
from app.models.user import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _canonical_pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Return (lower, higher) by UUID bytes — ADR-0008 canonical ordering."""
    return (a, b) if a.bytes < b.bytes else (b, a)


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


async def _can_converse(
    db: AsyncSession, *, caller: User, peer_id: uuid.UUID
) -> bool:
    """Check whether ``caller`` may open a conversation with ``peer_id``."""
    if caller.id == peer_id:
        return False

    # Admin can message anyone (support).
    if caller.role == "admin":
        return True

    # Load peer.
    peer_row = await db.execute(
        sa.select(User).where(
            User.id == peer_id,
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
    )
    peer = peer_row.scalar_one_or_none()
    if peer is None:
        return False

    if peer.role == "admin":
        # Any active user may initiate a conversation with an admin (support).
        return True

    # Customer ↔ seller referral link required (either direction).
    if caller.role == "customer" and peer.role == "seller":
        return caller.referring_seller_id == peer.id
    if caller.role == "seller" and peer.role == "customer":
        return peer.referring_seller_id == caller.id

    return False


async def _load_conversation_for_caller(
    db: AsyncSession,
    *,
    caller: User,
    conversation_id: uuid.UUID,
    lock: bool = False,
) -> Conversation:
    """Fetch a conversation and confirm caller is a participant.

    Non-participants and non-existent IDs both raise 404.
    """
    stmt = sa.select(Conversation).where(Conversation.id == conversation_id)
    if lock:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if conv is None:
        raise ConversationNotFound()

    # Admins may observe any conversation (e.g. admin-assist flows).
    if caller.role == "admin":
        return conv
    if caller.id not in (conv.user_a_id, conv.user_b_id):
        raise ConversationNotFound()
    return conv


def _peer_of(conv: Conversation, caller_id: uuid.UUID) -> uuid.UUID:
    return conv.user_b_id if conv.user_a_id == caller_id else conv.user_a_id


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


async def create_conversation(
    db: AsyncSession, *, caller: User, peer_user_id: uuid.UUID
) -> Conversation:
    """Open a new conversation (idempotent on canonical pair).

    Eligibility check enforced.  Returns existing conversation if already present.
    """
    if not await _can_converse(db, caller=caller, peer_id=peer_user_id):
        raise ConversationIneligible()

    a, b = _canonical_pair(caller.id, peer_user_id)
    existing = await db.execute(
        sa.select(Conversation).where(
            Conversation.user_a_id == a,
            Conversation.user_b_id == b,
        )
    )
    conv = existing.scalar_one_or_none()
    if conv is not None:
        return conv

    conv = Conversation(
        id=uuid.uuid4(),
        user_a_id=a,
        user_b_id=b,
        created_at=_now(),
        last_message_at=None,
    )
    db.add(conv)
    await db.flush()
    return conv


async def list_conversations_for_caller(
    db: AsyncSession, *, caller: User, limit: int = 50
) -> list[Conversation]:
    result = await db.execute(
        sa.select(Conversation)
        .where(
            sa.or_(
                Conversation.user_a_id == caller.id,
                Conversation.user_b_id == caller.id,
            )
        )
        .order_by(
            sa.func.coalesce(
                Conversation.last_message_at, Conversation.created_at
            ).desc()
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_conversation(
    db: AsyncSession, *, caller: User, conversation_id: uuid.UUID
) -> Conversation:
    return await _load_conversation_for_caller(
        db, caller=caller, conversation_id=conversation_id
    )


async def unread_count(
    db: AsyncSession, *, conversation_id: uuid.UUID, caller_id: uuid.UUID
) -> int:
    """Count messages in the conversation addressed to caller that are unread."""
    result = await db.execute(
        sa.select(sa.func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sender_id != caller_id,
            Message.read_at.is_(None),
            Message.deleted_at.is_(None),
        )
    )
    return int(result.scalar_one())


def conversation_to_response_dict(
    conv: Conversation, *, caller_id: uuid.UUID, unread: int
) -> dict:
    return {
        "id": conv.id,
        "peer_user_id": _peer_of(conv, caller_id),
        "created_at": conv.created_at,
        "last_message_at": conv.last_message_at,
        "unread_count": unread,
    }


# ---------------------------------------------------------------------------
# Messages — opaque ciphertext in/out.  No crypto ever touches message bytes.
# ---------------------------------------------------------------------------


async def store_message(
    db: AsyncSession,
    *,
    caller: User,
    conversation_id: uuid.UUID,
    ciphertext: bytes,
    nonce: bytes,
    ephemeral_public_key: bytes,
    recipient_key_id: uuid.UUID | None,
) -> Message:
    """Persist an opaque ciphertext row and bump last_message_at."""
    conv = await _load_conversation_for_caller(
        db,
        caller=caller,
        conversation_id=conversation_id,
        lock=True,
    )

    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        sender_id=caller.id,
        ciphertext=ciphertext,
        nonce=nonce,
        ephemeral_public_key=ephemeral_public_key,
        recipient_key_id=recipient_key_id,
        sent_at=_now(),
    )
    db.add(msg)
    conv.last_message_at = msg.sent_at
    await db.flush()
    return msg


async def list_messages(
    db: AsyncSession,
    *,
    caller: User,
    conversation_id: uuid.UUID,
    before: Optional[datetime] = None,
    limit: int = 50,
) -> list[Message]:
    await _load_conversation_for_caller(
        db, caller=caller, conversation_id=conversation_id
    )
    stmt = (
        sa.select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
        )
        .order_by(Message.sent_at.desc())
        .limit(limit)
    )
    if before is not None:
        stmt = stmt.where(Message.sent_at < before)
    result = await db.execute(stmt)
    # Return newest-first.
    return list(result.scalars().all())


async def mark_message_read(
    db: AsyncSession,
    *,
    caller: User,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
) -> Message:
    await _load_conversation_for_caller(
        db, caller=caller, conversation_id=conversation_id
    )
    result = await db.execute(
        sa.select(Message)
        .where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
        )
        .with_for_update()
    )
    msg = result.scalar_one_or_none()
    if msg is None:
        raise NotFoundError("Message not found.")
    # Only the recipient may mark a message as read.
    if msg.sender_id == caller.id:
        raise NotFoundError("Message not found.")
    if msg.read_at is None:
        msg.read_at = _now()
        await db.flush()
    return msg


def message_to_response_dict(msg: Message) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_id": msg.sender_id,
        "ciphertext_b64url": _b64url_encode(bytes(msg.ciphertext)),
        "nonce_b64url": _b64url_encode(bytes(msg.nonce)),
        "ephemeral_public_key_b64url": _b64url_encode(bytes(msg.ephemeral_public_key)),
        "recipient_key_id": msg.recipient_key_id,
        "sent_at": msg.sent_at,
        "read_at": msg.read_at,
    }


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


async def _get_settings(db: AsyncSession) -> PlatformSettings:
    result = await db.execute(sa.select(PlatformSettings).where(PlatformSettings.id == 1))
    ps = result.scalar_one_or_none()
    if ps is None:
        ps = PlatformSettings(id=1)
        db.add(ps)
        await db.flush()
    return ps


async def get_message_retention_days(db: AsyncSession) -> int:
    ps = await _get_settings(db)
    return ps.message_retention_days


async def update_message_retention_days(
    db: AsyncSession, *, caller: User, days: int
) -> int:
    if days < 7:
        raise MessageRetentionInvalid()
    ps = await _get_settings(db)
    ps.message_retention_days = days
    ps.updated_by_user_id = caller.id
    ps.updated_at = _now()
    await db.flush()
    return ps.message_retention_days


async def purge_old_messages(db: AsyncSession) -> int:
    """Hard-delete messages older than retention. Returns count purged."""
    ps = await _get_settings(db)
    cutoff = _now() - timedelta(days=ps.message_retention_days)
    result = await db.execute(
        sa.delete(Message).where(Message.sent_at < cutoff)
    )
    return int(result.rowcount or 0)
