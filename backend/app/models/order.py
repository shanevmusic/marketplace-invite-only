"""Order model — order lifecycle and retention enforcement."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import Base
from app.db.mixins import UUIDPKMixin, TimestampMixin, SoftDeleteMixin
from app.models.enums import order_status_enum


class Order(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """An order from a customer to a seller's store.

    State machine: pending → accepted → preparing → out_for_delivery →
                   delivered → completed; cancelled reachable from most states.

    Soft-delete (``deleted_at``) is set **only** by the nightly retention job
    after the analytics snapshot is written.  Cancellation sets
    ``status=cancelled``, NOT ``deleted_at``.

    ADR-0005: All monetary amounts stored as bigint minor units (e.g. cents).
    No per-row currency_code — platform currency from ``platform_settings``.

    Retention gating: orders hard-deletable only after
    ``platform_settings.retention_min_days`` have elapsed since ``delivered_at``.
    """

    __tablename__ = "orders"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_orders_customer_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "sellers.id",
            name="fk_orders_seller_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        comment="Denormalized seller_id for efficient seller-dashboard queries.",
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "stores.id",
            name="fk_orders_store_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        order_status_enum,
        nullable=False,
    )
    subtotal_minor: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        comment="Sum of (unit_price_minor * quantity) before any fees.",
    )
    total_minor: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        comment="Total amount charged.  Platform currency (ADR-0005).",
    )
    delivery_address: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment=(
            "JSONB with keys: line1, line2, city, region, postal, country, "
            "lat, lng, notes."
        ),
    )
    placed_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    accepted_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    preparing_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    out_for_delivery_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    delivered_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="Set on delivered transition.  Starts the retention timer.",
    )
    completed_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    cancelled_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        sa.Text, nullable=True
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    customer: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[customer_id],
    )
    store: Mapped["Store"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Store",
        back_populates="orders",
    )
    order_items: Mapped[list["OrderItem"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    delivery: Mapped[Optional["Delivery"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Delivery",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan",
    )
    driver_assignments: Mapped[list["DriverAssignment"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "DriverAssignment",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    review: Mapped[Optional["Review"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Review",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        sa.Index("ix_orders_seller_id_status", "seller_id", "status"),
        sa.Index("ix_orders_customer_id_status", "customer_id", "status"),
        sa.Index("ix_orders_status_placed_at", "status", "placed_at"),
        # Retention job sweep index
        sa.Index("ix_orders_delivered_at", "delivered_at"),
    )

    def __repr__(self) -> str:
        return f"<Order id={self.id} status={self.status!r} customer_id={self.customer_id}>"


from app.models.user import User  # noqa: E402, F401
from app.models.store import Store  # noqa: E402, F401
from app.models.order_item import OrderItem  # noqa: E402, F401
from app.models.delivery import Delivery  # noqa: E402, F401
from app.models.driver_assignment import DriverAssignment  # noqa: E402, F401
from app.models.review import Review  # noqa: E402, F401
