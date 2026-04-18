"""Store model — one store per seller."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin, TimestampMixin, SoftDeleteMixin


class Store(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A seller's storefront.  One-to-one with ``sellers``.

    ``slug`` is unique and lower-cased.  City scoping gates all downstream
    product and order queries.

    Soft-delete of a store propagates visibility restrictions to products
    and orders at the service layer.
    """

    __tablename__ = "stores"

    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "sellers.id",
            name="fk_stores_seller_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
        unique=True,
        comment="URL-safe lower-cased identifier.  Must be unique across all stores.",
    )
    description: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        server_default="",
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    seller: Mapped["Seller"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Seller",
        back_populates="store",
    )
    products: Mapped[list["Product"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Product",
        back_populates="store",
    )
    orders: Mapped[list["Order"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Order",
        back_populates="store",
    )
    reviews: Mapped[list["Review"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Review",
        back_populates="store",
    )

    __table_args__ = (
        sa.UniqueConstraint("seller_id", name="uq_stores_seller_id"),
        sa.UniqueConstraint("slug", name="uq_stores_slug"),
        sa.Index("ix_stores_slug", "slug"),
    )

    def __repr__(self) -> str:
        return f"<Store id={self.id} name={self.name!r} slug={self.slug!r}>"


from app.models.seller import Seller  # noqa: E402, F401
from app.models.product import Product  # noqa: E402, F401
from app.models.order import Order  # noqa: E402, F401
from app.models.review import Review  # noqa: E402, F401
