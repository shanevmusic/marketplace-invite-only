"""RefreshToken model — server-side refresh token storage (ADR-0006)."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class RefreshToken(UUIDPKMixin, Base):
    """Hashed refresh tokens keyed by user and device.

    Raw token value is never stored.  ``token_hash`` is a SHA-256 hex digest
    of the opaque random refresh token string issued to the client.

    Per ADR-0006: supports per-device revocation and rotation.
    Nightly sweep deletes rows where ``expires_at < now()``.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_refresh_tokens_user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        unique=True,
        comment="SHA-256 hex digest of the raw refresh token.  Raw value never stored.",
    )
    device_label: Mapped[Optional[str]] = mapped_column(
        sa.String(255),
        nullable=True,
        comment="User-agent or device label for session listing UI.",
    )
    issued_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    last_used_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="refresh_tokens",
    )

    __table_args__ = (
        sa.Index("ix_refresh_tokens_user_id", "user_id"),
        sa.Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),
        sa.Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user_id={self.user_id}>"


from app.models.user import User  # noqa: E402, F401
