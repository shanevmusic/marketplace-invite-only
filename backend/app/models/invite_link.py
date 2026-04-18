"""InviteLink model — invite tokens issued by admins and sellers."""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.db.mixins import UUIDPKMixin, TimestampMixin
from app.models.enums import invite_link_type_enum, user_role_enum


class InviteLink(UUIDPKMixin, TimestampMixin, Base):
    """Invite links created by admins (admin_invite) or sellers (seller_referral).

    ADR-0002: Each seller has exactly one active multi-use referral token.
    Admin invites are single-use, short-TTL, role-targeted.

    ``max_uses`` is nullable (NULL = unlimited per ADR-0002).
    ``role_target`` is required for admin_invite; implicit for seller_referral.

    Partial unique index ensures at most one active (revoked_at IS NULL)
    seller_referral token per issuer.
    """

    __tablename__ = "invite_links"

    issuer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="fk_invite_links_issuer_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        invite_link_type_enum,
        nullable=False,
    )
    token: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        unique=True,
        comment="32-byte URL-safe base64 random token.",
    )
    role_target: Mapped[Optional[str]] = mapped_column(
        user_role_enum,
        nullable=True,
        comment=(
            "Required for admin_invite (specifies the role granted on signup). "
            "NULL for seller_referral (role is determined by signup flow)."
        ),
    )
    max_uses: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        nullable=True,
        comment="NULL = unlimited (ADR-0002).  Positive integer for limited invites.",
    )
    used_count: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
    )
    expires_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    issuer: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="invite_links",
        foreign_keys=[issuer_id],
    )
    referrals: Mapped[list["Referral"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Referral",
        back_populates="invite_link",
    )

    __table_args__ = (
        sa.Index("ix_invite_links_token", "token", unique=True),
        sa.Index("ix_invite_links_issuer_id", "issuer_id"),
        sa.Index("ix_invite_links_expires_at", "expires_at"),
        # Partial unique index: only one active seller_referral per issuer.
        sa.Index(
            "uq_invite_links_active_seller_referral",
            "issuer_id",
            unique=True,
            postgresql_where=sa.text(
                "type = 'seller_referral' AND revoked_at IS NULL"
            ),
        ),
    )

    def __repr__(self) -> str:
        return f"<InviteLink id={self.id} type={self.type!r} token={self.token!r}>"


from app.models.user import User  # noqa: E402, F401
from app.models.referral import Referral  # noqa: E402, F401
