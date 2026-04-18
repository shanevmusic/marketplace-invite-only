"""User model — central identity table for all roles."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import CITEXT, UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin, TimestampMixin, SoftDeleteMixin
from app.models.enums import user_role_enum


class User(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Stores identity and role for every actor: admin, seller, customer, driver.

    Soft-delete semantics: ``deleted_at IS NOT NULL`` hides the profile from
    non-admin callers.  Orders, messages, and analytics snapshots are retained
    per retention rules.

    ``referring_seller_id`` is stored as a plain UUID (no FK constraint) to
    avoid a circular reference between ``users`` and ``sellers``.  See
    docs/schema.md §Cyclic FK note.
    """

    __tablename__ = "users"

    # Email uses the CITEXT extension for case-insensitive uniqueness.
    # The extension is created in the initial migration:
    #   CREATE EXTENSION IF NOT EXISTS "citext";
    email: Mapped[str] = mapped_column(
        CITEXT,
        nullable=False,
        unique=True,
        comment="Case-insensitive unique email; stored via CITEXT extension.",
    )
    password_hash: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Argon2id hash of the user's password.",
    )
    role: Mapped[str] = mapped_column(
        user_role_enum,
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        sa.String(32),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    disabled_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    # Plain UUID — no FK — to avoid users ↔ sellers cycle.
    # Logically references sellers.id; enforced at service layer.
    referring_seller_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment=(
            "Plain UUID reference to sellers.id.  No FK constraint to avoid "
            "the users ↔ sellers circular dependency.  Enforced at service layer."
        ),
    )

    # ------------------------------------------------------------------
    # Relationships (back-populated from child tables)
    # ------------------------------------------------------------------
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    invite_links: Mapped[list["InviteLink"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "InviteLink",
        back_populates="issuer",
        foreign_keys="InviteLink.issuer_id",
    )
    public_key: Mapped[list["UserPublicKey"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "UserPublicKey",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    seller_profile: Mapped[Optional["Seller"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Seller",
        back_populates="user",
        uselist=False,
        foreign_keys="Seller.user_id",
    )

    __table_args__ = (
        sa.Index("ix_users_deleted_at", "deleted_at"),
        sa.Index("ix_users_role", "role"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"


# Deferred imports to avoid circular dependencies at module load time.
from app.models.refresh_token import RefreshToken  # noqa: E402, F401
from app.models.invite_link import InviteLink  # noqa: E402, F401
from app.models.user_public_key import UserPublicKey  # noqa: E402, F401
from app.models.seller import Seller  # noqa: E402, F401
