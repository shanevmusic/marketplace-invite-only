"""DriverAssignment model — audit trail for admin driver-assignment actions."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin
from app.models.enums import driver_assignment_status_enum


class DriverAssignment(UUIDPKMixin, Base):
    """Records each driver-assignment action for audit and re-assignment.

    Multiple rows are possible for one order if the admin reassigns.
    The active assignment is the most-recent row for a given ``order_id``
    with a non-cancelled status.

    ``driver_id`` is NULL while in the ``requested`` pool state (before a
    specific driver is selected by the admin).
    """

    __tablename__ = "driver_assignments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "orders.id",
            name="fk_driver_assignments_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_driver_assignments_driver_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        comment="NULL while in 'requested' pool state.",
    )
    status: Mapped[str] = mapped_column(
        driver_assignment_status_enum,
        nullable=False,
    )
    requested_by_seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "sellers.id",
            name="fk_driver_assignments_requested_by_seller_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    requested_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    assigned_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_driver_assignments_assigned_by_admin_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    assigned_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    responded_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    decline_reason: Mapped[Optional[str]] = mapped_column(
        sa.Text, nullable=True
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    order: Mapped["Order"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Order",
        back_populates="driver_assignments",
    )
    driver: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[driver_id],
    )
    assigned_by_admin: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[assigned_by_admin_id],
    )

    __table_args__ = (
        sa.Index("ix_driver_assignments_status_requested_at", "status", "requested_at"),
        sa.Index("ix_driver_assignments_order_id", "order_id"),
        sa.Index("ix_driver_assignments_driver_id", "driver_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<DriverAssignment id={self.id} order_id={self.order_id} "
            f"status={self.status!r}>"
        )


from app.models.order import Order  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
