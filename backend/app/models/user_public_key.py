"""UserPublicKey model — X25519 public key registry (ADR-0009)."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class UserPublicKey(UUIDPKMixin, Base):
    """Stores a user's long-term X25519 public key (32 bytes).

    1:1 with ``users``.  Key rotation is handled by ON CONFLICT DO UPDATE
    (upsert) on ``user_id``.  Private keys never leave the device.
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
        unique=True,
    )
    public_key: Mapped[bytes] = mapped_column(
        sa.LargeBinary,
        nullable=False,
        comment="X25519 public key — 32 bytes raw (not base64).",
    )
    registered_at: Mapped[sa.DateTime] = mapped_column(
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

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="public_key",
    )

    __table_args__ = (
        sa.UniqueConstraint("user_id", name="uq_user_public_keys_user_id"),
    )

    def __repr__(self) -> str:
        return f"<UserPublicKey id={self.id} user_id={self.user_id}>"


from app.models.user import User  # noqa: E402, F401
