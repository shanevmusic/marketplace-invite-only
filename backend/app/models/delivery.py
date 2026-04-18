"""Delivery model — delivery lifecycle and last-known location."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin
from app.models.enums import delivery_status_enum


class Delivery(UUIDPKMixin, Base):
    """One delivery record per order (1:1).

    Created when the seller (or driver) transitions the order to
    ``out_for_delivery``.

    ``driver_id`` is NULL for seller self-deliveries.
    ``seller_id`` is the seller who started / is supervising the delivery.
    CHECK ensures at least one of driver_id / seller_id is not null.

    ``current_lat`` / ``current_lng`` store the last-known position only.
    Full location history is deferred to Phase 7 (``delivery_location_events``
    table — Q-E2 resolution).

    ADR-0003: The ``out_for_delivery`` transition may be triggered by the
    assigned driver OR the seller; first caller wins.
    """

    __tablename__ = "deliveries"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "orders.id",
            name="fk_deliveries_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        comment="One delivery per order.",
    )
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_deliveries_driver_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        comment="NULL when seller self-delivers.",
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "sellers.id",
            name="fk_deliveries_seller_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        comment="Seller who started or is supervising the delivery.",
    )
    status: Mapped[str] = mapped_column(
        delivery_status_enum,
        nullable=False,
    )
    started_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    delivered_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    current_lat: Mapped[Optional[float]] = mapped_column(
        sa.Double,
        nullable=True,
        comment="Last-known latitude.  Full history deferred to Phase 7.",
    )
    current_lng: Mapped[Optional[float]] = mapped_column(
        sa.Double,
        nullable=True,
        comment="Last-known longitude.  Full history deferred to Phase 7.",
    )
    last_location_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="Timestamp of the most recent location update.",
    )
    distance_meters: Mapped[Optional[int]] = mapped_column(
        sa.Integer, nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        sa.Integer, nullable=True
    )
    current_eta_seconds: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        nullable=True,
        comment=(
            "Current ETA (seconds remaining to destination), as reported by "
            "driver/seller app.  Safe to expose to the customer."
        ),
    )
    current_eta_updated_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="Timestamp at which current_eta_seconds was last updated.",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    order: Mapped["Order"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Order",
        back_populates="delivery",
    )
    driver: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[driver_id],
    )

    __table_args__ = (
        sa.CheckConstraint(
            "driver_id IS NOT NULL OR seller_id IS NOT NULL",
            name="ck_deliveries_at_least_one_actor",
        ),
        sa.UniqueConstraint("order_id", name="uq_deliveries_order_id"),
    )

    def __repr__(self) -> str:
        return f"<Delivery id={self.id} order_id={self.order_id} status={self.status!r}>"


from app.models.order import Order  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
