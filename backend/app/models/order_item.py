"""OrderItem model — line items with price/name snapshots (Q-E1 resolution)."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class OrderItem(UUIDPKMixin, Base):
    """A single line item within an order.

    Q-E1 resolution (phase-1-reconciliation.md): ``product_id`` uses
    ON DELETE SET NULL so order history survives product hard-delete.
    Snapshot columns capture the product name and price at order-placement
    time, ensuring order history is accurate after product edits or deletion.
    """

    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "orders.id",
            name="fk_order_items_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    # ON DELETE SET NULL — product may be soft- or hard-deleted later.
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "products.id",
            name="fk_order_items_product_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        comment="Nullable: set to NULL if the product is later hard-deleted.",
    )
    product_name_snapshot: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Product name at order-placement time.  Immutable after INSERT.",
    )
    unit_price_minor_snapshot: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        comment="Unit price in minor currency units at order-placement time.",
    )
    quantity: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    order: Mapped["Order"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Order",
        back_populates="order_items",
    )
    product: Mapped[Optional["Product"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Product",
        foreign_keys=[product_id],
    )

    __table_args__ = (
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        sa.Index("ix_order_items_order_id", "order_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrderItem id={self.id} order_id={self.order_id} "
            f"product_name_snapshot={self.product_name_snapshot!r}>"
        )


from app.models.order import Order  # noqa: E402, F401
from app.models.product import Product  # noqa: E402, F401
