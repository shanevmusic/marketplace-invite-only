"""Seller model — 1:1 extension of users where role='seller'."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import TimestampMixin, SoftDeleteMixin


class Seller(TimestampMixin, SoftDeleteMixin, Base):
    """Extends the ``users`` table 1:1 for seller-specific data.

    ``id`` is the same UUID as ``users.id`` (shared PK pattern).
    ``user_id`` has a unique FK to ``users.id`` for the ORM join path.

    Note on cyclic reference: ``users.referring_seller_id`` logically points
    to ``sellers.id`` but has no FK constraint — see docs/schema.md §Cyclic FK.
    """

    __tablename__ = "sellers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        comment="Same UUID as users.id — shared-PK 1:1 extension pattern.",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_sellers_user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
    )
    display_name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    bio: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
    )
    city: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        index=True,
    )
    country_code: Mapped[str] = mapped_column(
        sa.String(2),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="seller_profile",
        foreign_keys=[user_id],
    )
    store: Mapped["Store"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Store",
        back_populates="seller",
        uselist=False,
        cascade="all, delete-orphan",
    )
    products: Mapped[list["Product"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Product",
        back_populates="seller",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        sa.UniqueConstraint("user_id", name="uq_sellers_user_id"),
        sa.Index("ix_sellers_city", "city"),
    )

    def __repr__(self) -> str:
        return f"<Seller id={self.id} display_name={self.display_name!r}>"


from app.models.user import User  # noqa: E402, F401
from app.models.store import Store  # noqa: E402, F401
from app.models.product import Product  # noqa: E402, F401
