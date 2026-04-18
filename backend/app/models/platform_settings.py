"""PlatformSettings model — singleton configuration row."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class PlatformSettings(Base):
    """Singleton platform-wide settings row.

    PK is a plain integer fixed to 1.  A CHECK constraint enforces the
    singleton invariant at the database level.

    ``retention_min_days``: admin-configurable minimum order retention
    period (default 30).  Orders cannot be hard-deleted until this many
    days have elapsed since ``delivered_at``.

    ``currency_code``: ISO 4217 three-letter code (ADR-0005).  Immutable
    once any ``order_analytics_snapshots`` row exists (enforced at service
    layer).

    ``updated_by_user_id``: optional FK to the admin user who last changed
    settings.  ON DELETE SET NULL so settings row is never orphaned.
    """

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(
        sa.Integer,
        primary_key=True,
        comment="Singleton row: always 1.  CHECK id = 1 enforces invariant.",
    )
    retention_min_days: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=30,
        server_default=sa.text("30"),
        comment="Minimum days after delivery before an order may be hard-deleted.",
    )
    order_auto_complete_grace_hours: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=72,
        server_default=sa.text("72"),
        comment=(
            "Hours after delivery before a delivered order auto-completes "
            "(ADR-0012 D4)."
        ),
    )
    message_retention_days: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=90,
        server_default=sa.text("90"),
        comment=(
            "Minimum days to retain messages before admin purge (ADR-0013). "
            "CHECK message_retention_days >= 7."
        ),
    )
    currency_code: Mapped[str] = mapped_column(
        sa.String(3),
        nullable=False,
        default="USD",
        server_default="USD",
        comment="ISO 4217 platform currency.  ADR-0005: single global currency.",
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        onupdate=sa.text("now()"),
    )
    updated_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_platform_settings_updated_by_user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    __table_args__ = (
        sa.CheckConstraint("id = 1", name="ck_platform_settings_singleton"),
        sa.CheckConstraint(
            "order_auto_complete_grace_hours >= 1",
            name="ck_platform_settings_auto_complete_grace_positive",
        ),
        sa.CheckConstraint(
            "message_retention_days >= 7",
            name="ck_platform_settings_message_retention_min",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PlatformSettings retention_min_days={self.retention_min_days} "
            f"currency_code={self.currency_code!r}>"
        )
