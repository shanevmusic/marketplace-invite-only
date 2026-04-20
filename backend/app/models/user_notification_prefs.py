"""UserNotificationPrefs model — per-user notification preference flags."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class UserNotificationPrefs(TimestampMixin, Base):
    """Stores notification opt-in/out flags for each user.

    One row per user (user_id is unique).  Rows are lazily created on first
    GET with all-default values so every user always has preferences.
    """

    __tablename__ = "user_notification_prefs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        comment="FK to users.id; one row per user.",
    )

    push_enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    email_enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    order_updates: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    messages: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    marketing: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )

    # Relationship back to User (optional — useful for joins)
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="notification_prefs",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserNotificationPrefs user_id={self.user_id}>"


# Deferred import to avoid circular dependency
from app.models.user import User  # noqa: E402, F401
