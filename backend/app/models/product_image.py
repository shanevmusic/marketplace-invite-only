"""ProductImage model — S3/GCS object keys for product photos."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class ProductImage(UUIDPKMixin, Base):
    """Stores S3/GCS object keys for product images.

    Signed GET URLs are generated on-the-fly at request time and are never
    persisted.  ``display_order`` controls the gallery order shown to customers.
    """

    __tablename__ = "product_images"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "products.id",
            name="fk_product_images_product_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    s3_key: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="S3 or GCS object key.  Signed GET URL generated on-demand.",
    )
    display_order: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Product",
        back_populates="images",
    )

    __table_args__ = (
        sa.Index("ix_product_images_product_id", "product_id"),
    )

    def __repr__(self) -> str:
        return f"<ProductImage id={self.id} product_id={self.product_id}>"


from app.models.product import Product  # noqa: E402, F401
