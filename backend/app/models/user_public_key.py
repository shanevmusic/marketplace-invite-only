"""UserPublicKey model — X25519 public key registry (ADR-0009, ADR-0013).

Phase 6 change: multiple keys per user (rotation history), with an
``active|rotated|revoked`` lifecycle.  At most one row per ``user_id`` may
be ``active`` at any time (partial unique index).  Rotation is additive —
old rows are preserved because ``messages.recipient_key_id`` references
them for historical decryption on the recipient device.

Private keys never leave the device.
"""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class UserPublicKey(UUIDPKMixin, Base):
    """Stores a user's X25519 public key(s) — 32 bytes raw.

    ``status`` lifecycle: ``active`` → ``rotated`` (new key registered) or
    ``revoked`` (explicit DELETE). Once rotated or revoked, the row is
    preserved so clients can still decrypt historical messages that
    reference it via ``messages.recipient_key_id``.
    """

    __tablename__ = "user_public_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_user_public_keys_user_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    public_key: Mapped[bytes] = mapped_column(
        sa.LargeBinary,
        nullable=False,
        comment="X25519 public key — 32 bytes raw (not base64).",
    )
    key_version: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        server_default=sa.text("1"),
        comment="Client-declared monotonic version per user.",
    )
    status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        server_default=sa.text("'active'"),
        comment="'active' | 'rotated' | 'revoked'",
    )
    registered_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    rotated_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        onupdate=sa.text("now()"),
    )

    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="public_key",
    )

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('active','rotated','revoked')",
            name="ck_user_public_keys_status_valid",
        ),
        sa.Index(
            "uq_user_public_keys_one_active",
            "user_id",
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
        ),
        sa.Index("ix_user_public_keys_user_id_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserPublicKey id={self.id} user_id={self.user_id} "
            f"status={self.status} v={self.key_version}>"
        )


from app.models.user import User  # noqa: E402, F401
