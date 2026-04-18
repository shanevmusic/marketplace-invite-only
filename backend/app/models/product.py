"""Product model — items listed in a store."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin, TimestampMixin, SoftDeleteMixin
from app.models.enums import product_status_enum


class Product(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A product listed by a seller in a store.

    ADR-0005: Per-row currency is omitted.  ``price_minor`` is in the
    platform currency (``platform_settings.currency_code``), stored as a
    bigint count of the smallest monetary unit (e.g. cents) to avoid
    floating-point drift.

    ``stock_quantity`` is nullable (NULL = unlimited stock).

    Soft-deleted products are excluded from listings but remain referenced
    by ``order_items`` via snapshot columns.  The ``product_id`` FK on
    ``order_items`` uses ON DELETE SET NULL to survive future hard-deletes.
    """

    __tablename__ = "products"

    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "sellers.id",
            name="fk_products_seller_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "stores.id",
            name="fk_products_store_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        server_default="",
    )
    # Smallest monetary unit (e.g. cents).  No per-row currency (ADR-0005).
    price_minor: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        comment="Price in smallest monetary unit.  Platform currency via platform_settings.",
    )
    stock_quantity: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        nullable=True,
        comment="NULL = unlimited stock.",
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    # Phase 11: admin moderation.
    status: Mapped[str] = mapped_column(
        product_status_enum,
        nullable=False,
        server_default=sa.text("'active'"),
    )
    disabled_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    disabled_reason: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # CHECK constraints
    # ------------------------------------------------------------------
    __table_args__ = (
        sa.CheckConstraint("price_minor > 0", name="ck_products_price_minor_positive"),
        sa.CheckConstraint(
            "stock_quantity IS NULL OR stock_quantity >= 0",
            name="ck_products_stock_quantity_non_negative",
        ),
        sa.Index("ix_products_seller_id_is_active", "seller_id", "is_active"),
        sa.Index("ix_products_store_id_is_active", "store_id", "is_active"),
        sa.Index("ix_products_status", "status"),
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    seller: Mapped["Seller"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Seller",
        back_populates="products",
    )
    store: Mapped["Store"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Store",
        back_populates="products",
    )
    images: Mapped[list["ProductImage"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.display_order",
    )
    cart_items: Mapped[list["CartItem"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CartItem",
        back_populates="product",
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r} price_minor={self.price_minor}>"


from app.models.seller import Seller  # noqa: E402, F401
from app.models.store import Store  # noqa: E402, F401
from app.models.product_image import ProductImage  # noqa: E402, F401
from app.models.cart_item import CartItem  # noqa: E402, F401
