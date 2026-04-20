"""Delivery-flow models — tracking points, order-chat messages, codes.

Part of migration 0010. These tables back the Uber-style delivery flow:

- ``OrderTrackingPoint`` — admin-retained GPS breadcrumb log.
- ``OrderMessage`` — customer/driver E2E chat; ``archived_at`` hides from
  participants once delivery completes.
- ``DeliveryCode`` — single 6-digit code per order, attempts + lockout.
- ``DeliveryCodeAttempt`` — audit log for every submission.
"""

from __future__ import annotations

import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderTrackingPoint(Base):
    __tablename__ = "order_tracking_points"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    lat: Mapped[float] = mapped_column(sa.Float, nullable=False)
    lng: Mapped[float] = mapped_column(sa.Float, nullable=False)
    recorded_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


class OrderMessage(Base):
    __tablename__ = "order_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    sender_role: Mapped[str] = mapped_column(sa.Text, nullable=False)
    ciphertext: Mapped[str] = mapped_column(sa.Text, nullable=False)
    nonce: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    archived_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )


class DeliveryCode(Base):
    __tablename__ = "delivery_codes"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="CASCADE"),
        primary_key=True,
    )
    code_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    code_plain: Mapped[str] = mapped_column(sa.Text, nullable=False)
    attempts_used: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    locked: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    consumed_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
    )


class DeliveryCodeAttempt(Base):
    __tablename__ = "delivery_code_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_code: Mapped[str] = mapped_column(sa.Text, nullable=False)
    success: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    attempted_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
