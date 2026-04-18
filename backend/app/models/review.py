"""Review model — private order reviews (not shown publicly)."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class Review(UUIDPKMixin, Base):
    """A private review left by a customer after a completed order.

    1:1 with ``orders`` (unique constraint on ``order_id``).
    NOT public — visibility is restricted to the seller who received the
    order and admin users.  This is enforced at the service layer.

    ``store_id`` is denormalized for efficient ``GET /reviews?store_id=``
    queries without joining orders.

    ``updated_at`` is included to support review edits within a grace period
    (service-layer policy, not enforced here).
    """

    __tablename__ = "reviews"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "orders.id",
            name="fk_reviews_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_reviews_customer_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "stores.id",
            name="fk_reviews_store_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        comment="Denormalized for query convenience.",
    )
    rating: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
    )
    comment: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
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
    order: Mapped["Order"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Order",
        back_populates="review",
    )
    customer: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[customer_id],
    )
    store: Mapped["Store"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Store",
        back_populates="reviews",
    )

    __table_args__ = (
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
        sa.UniqueConstraint("order_id", name="uq_reviews_order_id"),
        sa.Index("ix_reviews_store_id", "store_id"),
        sa.Index("ix_reviews_customer_id", "customer_id"),
    )

    def __repr__(self) -> str:
        return f"<Review id={self.id} order_id={self.order_id} rating={self.rating}>"


from app.models.order import Order  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
from app.models.store import Store  # noqa: E402, F401
