"""Referral model — records each invite-link signup for the referral graph."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin


class Referral(UUIDPKMixin, Base):
    """Immutable referral edge: referrer → referred user, via which invite link.

    ADR-0002: One row per signup through a referral link.  Enables the admin
    referral-graph visualisation and supports per-signup auditing even when
    the originating invite token is long-lived (seller_referral).

    ADR-0007: Referral chain depth = 1.  The graph is stored flat; no
    closure table is required.
    """

    __tablename__ = "referrals"

    referrer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_referrals_referrer_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    referred_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_referrals_referred_user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        unique=True,
        comment="Each user can be referred at most once.",
    )
    invite_link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "invite_links.id",
            name="fk_referrals_invite_link_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    referrer: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[referrer_id],
    )
    referred_user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[referred_user_id],
    )
    invite_link: Mapped["InviteLink"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "InviteLink",
        back_populates="referrals",
    )

    __table_args__ = (
        sa.Index("ix_referrals_referrer_id", "referrer_id"),
        sa.UniqueConstraint("referred_user_id", name="uq_referrals_referred_user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Referral id={self.id} referrer_id={self.referrer_id} "
            f"referred_user_id={self.referred_user_id}>"
        )


from app.models.user import User  # noqa: E402, F401
from app.models.invite_link import InviteLink  # noqa: E402, F401
