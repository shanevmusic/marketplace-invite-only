"""CartItem model — server-side cart persistence (ADR-0004)."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class CartItem(UUIDPKMixin, Base):
    """One item in a customer's server-side cart.

    ADR-0004: Cart state persists on the server to survive device switches.
    One row per (customer, product) combination; ``quantity`` is updated
    in-place rather than inserting a new row.

    Cart is pruned on successful checkout.
    """

    __tablename__ = "cart_items"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_cart_items_customer_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "products.id",
            name="fk_cart_items_product_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
    )
    added_at: Mapped[sa.DateTime] = mapped_column(
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
    customer: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[customer_id],
    )
    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Product",
        back_populates="cart_items",
    )

    __table_args__ = (
        sa.CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
        sa.UniqueConstraint("customer_id", "product_id", name="uq_cart_items_customer_product"),
        sa.Index("ix_cart_items_customer_id", "customer_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<CartItem id={self.id} customer_id={self.customer_id} "
            f"product_id={self.product_id} quantity={self.quantity}>"
        )


from app.models.user import User  # noqa: E402, F401
from app.models.product import Product  # noqa: E402, F401
