"""Pydantic schemas for conversations + ciphertext messages (Phase 6).

SECURITY INVARIANT: No plaintext fields are ever accepted at the schema
layer.  ``extra='forbid'`` means a request carrying ``body``, ``text``,
``plaintext``, or ``content`` returns 422 before the service is ever
reached.  This is enforced in ``SendMessageRequest`` and verified by
``tests/test_messaging_ciphertext_only.py``.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    peer_user_id: uuid.UUID


class ConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    peer_user_id: uuid.UUID
    created_at: datetime
    last_message_at: datetime | None = None
    unread_count: int = 0


class ConversationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ConversationResponse]


# ---------------------------------------------------------------------------
# Messages — ciphertext-only (ADR-0009, ADR-0013)
# ---------------------------------------------------------------------------


def _decode_b64url(v: str, *, min_len: int, max_len: int, field: str) -> bytes:
    if not isinstance(v, str):
        raise ValueError(f"{field} must be a string")
    try:
        padded = v + "=" * (-len(v) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{field} is not valid base64url: {exc}") from exc
    if not (min_len <= len(raw) <= max_len):
        raise ValueError(
            f"{field} must decode to {min_len}..{max_len} bytes, got {len(raw)}"
        )
    return raw


class SendMessageRequest(BaseModel):
    """Body for ``POST /conversations/{id}/messages``.

    Only opaque ciphertext fields are accepted.  Any stray key like
    ``body``, ``text``, ``plaintext``, or ``content`` will cause a 422 via
    ``extra='forbid'``.
    """

    model_config = ConfigDict(extra="forbid")

    ciphertext_b64url: str = Field(..., min_length=1, max_length=131072)
    nonce_b64url: str = Field(..., min_length=1, max_length=32)
    ephemeral_public_key_b64url: str = Field(..., min_length=1, max_length=128)
    recipient_key_id: uuid.UUID | None = None

    @field_validator("ciphertext_b64url")
    @classmethod
    def _v_ciphertext(cls, v: str) -> str:
        _decode_b64url(v, min_len=1, max_len=65536, field="ciphertext_b64url")
        return v

    @field_validator("nonce_b64url")
    @classmethod
    def _v_nonce(cls, v: str) -> str:
        _decode_b64url(v, min_len=12, max_len=12, field="nonce_b64url")
        return v

    @field_validator("ephemeral_public_key_b64url")
    @classmethod
    def _v_epk(cls, v: str) -> str:
        _decode_b64url(v, min_len=32, max_len=32, field="ephemeral_public_key_b64url")
        return v

    def ciphertext_bytes(self) -> bytes:
        return _decode_b64url(
            self.ciphertext_b64url, min_len=1, max_len=65536, field="ciphertext_b64url"
        )

    def nonce_bytes(self) -> bytes:
        return _decode_b64url(
            self.nonce_b64url, min_len=12, max_len=12, field="nonce_b64url"
        )

    def ephemeral_public_key_bytes(self) -> bytes:
        return _decode_b64url(
            self.ephemeral_public_key_b64url,
            min_len=32,
            max_len=32,
            field="ephemeral_public_key_b64url",
        )


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    ciphertext_b64url: str
    nonce_b64url: str
    ephemeral_public_key_b64url: str
    recipient_key_id: uuid.UUID | None = None
    sent_at: datetime
    read_at: datetime | None = None


class MessageListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[MessageResponse]
    next_cursor: str | None = None


class UpdateMessageRetentionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_retention_days: int = Field(..., ge=7, le=3650)


class MessageRetentionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_retention_days: int


class PurgeMessagesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purged_count: int
