"""Conversation model — two-participant E2E messaging thread (ADR-0008)."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class Conversation(UUIDPKMixin, Base):
    """A two-participant conversation thread.

    ADR-0008: Conversations are strictly two-participant in v1.
    Canonical ordering: ``user_a_id < user_b_id`` (by UUID value) is
    enforced at the service layer.  A CHECK constraint prevents reversed
    storage.  The unique constraint on ``(user_a_id, user_b_id)`` prevents
    duplicate conversations between the same pair.

    Either participant may initiate.  Driver ↔ customer messaging is out
    of scope for v1.
    """

    __tablename__ = "conversations"

    user_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_conversations_user_a_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        comment="Lower UUID of the two participants (canonical ordering).",
    )
    user_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_conversations_user_b_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        comment="Higher UUID of the two participants (canonical ordering).",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    last_message_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="Updated on each new message for fast inbox sorting.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    user_a: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[user_a_id],
    )
    user_b: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[user_b_id],
    )
    messages: Mapped[list["Message"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        sa.CheckConstraint(
            "user_a_id < user_b_id",
            name="ck_conversations_canonical_ordering",
        ),
        sa.UniqueConstraint(
            "user_a_id", "user_b_id",
            name="uq_conversations_user_pair",
        ),
        sa.Index("ix_conversations_user_a_id", "user_a_id"),
        sa.Index("ix_conversations_user_b_id", "user_b_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation id={self.id} user_a_id={self.user_a_id} "
            f"user_b_id={self.user_b_id}>"
        )


from app.models.user import User  # noqa: E402, F401
from app.models.message import Message  # noqa: E402, F401
