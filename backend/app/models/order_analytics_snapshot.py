"""OrderAnalyticsSnapshot — append-only analytics ledger (ADR-0005)."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class OrderAnalyticsSnapshot(UUIDPKMixin, Base):
    """Append-only record written atomically at the ``delivered`` transition.

    NEVER soft-deleted or hard-deleted.  All references (order_id,
    seller_id, store_id, customer_id) are stored as plain UUIDs with NO
    foreign-key constraints so this row survives order purges, seller
    soft-deletes, etc.

    ADR-0005: No per-row currency_code.  ``subtotal_minor`` and
    ``total_minor`` are in the platform currency.

    ``city`` is denormalized from ``stores.city`` at snapshot time.
    """

    __tablename__ = "order_analytics_snapshots"
    __table_comment__ = (
        "Append-only; never deleted; survives order purges.  "
        "Plain UUID refs — no FK constraints by design."
    )

    # Plain UUIDs — no FK constraints intentionally.
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Plain UUID reference to orders.id.  No FK — survives order hard-delete.",
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Plain UUID reference to sellers.id.  No FK — survives seller changes.",
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Plain UUID reference to stores.id.",
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Plain UUID reference to users.id.",
    )
    city: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Denormalized from stores.city at snapshot time.",
    )
    item_count: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
    )
    subtotal_minor: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        comment="Subtotal in platform currency minor units.",
    )
    total_minor: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        comment="Total in platform currency minor units.",
    )
    delivered_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        comment="Copy of orders.delivered_at at snapshot time.",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        comment="When the snapshot was written.",
    )

    __table_args__ = (
        sa.Index("ix_order_analytics_snapshots_seller_id_delivered_at", "seller_id", "delivered_at"),
        sa.Index("ix_order_analytics_snapshots_delivered_at", "delivered_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrderAnalyticsSnapshot id={self.id} seller_id={self.seller_id} "
            f"total_minor={self.total_minor}>"
        )
