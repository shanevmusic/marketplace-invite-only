"""Message model — E2E-encrypted ciphertext storage (ADR-0009).

SECURITY NOTE: This table stores CIPHERTEXT ONLY.
No plaintext, no preview, no subject, no body column.
Server never decrypts.  Keys stay on client devices.

Scheme: X25519 ECDH per-message ephemeral key + AES-256-GCM authenticated
encryption.  See ADR-0009 and docs/schema.md §Materialized view.
"""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class Message(UUIDPKMixin, Base):
    """End-to-end encrypted message.

    ⚠️  This table stores E2E-encrypted ciphertext ONLY.
        The server never holds, derives, or logs plaintext.
        Column names ``ciphertext``, ``nonce``, ``ephemeral_public_key``
        are opaque byte blobs from the client's perspective.

    ``deleted_at`` supports GDPR soft-erasure (Q-E3).  Non-admin API
    callers see only messages where ``deleted_at IS NULL``.

    ``ratchet_state`` is reserved for a future Signal double-ratchet
    upgrade (ADR-0009).  Currently NULL.
    """

    __tablename__ = "messages"
    __table_comment__ = (
        "E2E-encrypted ciphertext storage.  Server never decrypts.  "
        "No plaintext column exists on this table by design (ADR-0009)."
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "conversations.id",
            name="fk_messages_conversation_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_messages_sender_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    # -------------------------------------------------------------------
    # Crypto fields — opaque binary blobs
    # -------------------------------------------------------------------
    ciphertext: Mapped[bytes] = mapped_column(
        sa.LargeBinary,
        nullable=False,
        comment="AES-256-GCM ciphertext.  Opaque to the server.",
    )
    nonce: Mapped[bytes] = mapped_column(
        sa.LargeBinary,
        nullable=False,
        comment="AES-GCM 12-byte nonce.  Unique per message.",
    )
    ephemeral_public_key: Mapped[bytes] = mapped_column(
        sa.LargeBinary,
        nullable=False,
        comment="Sender's ephemeral X25519 public key (32 bytes).",
    )
    ratchet_state: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Reserved for Signal double-ratchet state (ADR-0009).  "
            "NULL under current X25519+AES-GCM scheme."
        ),
    )
    # -------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------
    sent_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    read_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="Set when the recipient marks the message as read.",
    )
    deleted_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment=(
            "Soft-delete for GDPR erasure (Q-E3).  "
            "Non-admin callers see only messages where deleted_at IS NULL."
        ),
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    conversation: Mapped["Conversation"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Conversation",
        back_populates="messages",
    )
    sender: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[sender_id],
    )

    __table_args__ = (
        sa.Index("ix_messages_conversation_id_sent_at", "conversation_id", "sent_at"),
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} conversation_id={self.conversation_id}>"


from app.models.conversation import Conversation  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
