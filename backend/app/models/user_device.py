"""UserDevice model — registered push-notification endpoints (Phase 12).

One row per (user, platform, token) tuple.  Tokens are opaque — we don't
validate them server-side, the FCM/APNs push service does.
"""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin


class UserDevice(UUIDPKMixin, TimestampMixin, Base):
    """Push-notification endpoint registered for a user."""

    __tablename__ = "user_devices"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_user_devices_user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="'ios' | 'android' | 'web'",
    )
    token: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="FCM registration token or APNs device token (opaque).",
    )
    last_seen_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    disabled_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="Set when the push provider returned permanent failure for this token.",
    )

    __table_args__ = (
        sa.UniqueConstraint("user_id", "token", name="uq_user_devices_user_token"),
        sa.Index("ix_user_devices_user_id", "user_id"),
        sa.Index("ix_user_devices_platform", "platform"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserDevice id={self.id} user_id={self.user_id} platform={self.platform!r}>"
        )
