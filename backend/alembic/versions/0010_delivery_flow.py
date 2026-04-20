"""Delivery flow — order tracking, driver-customer chat, delivery codes.

Adds four new tables (``order_tracking_points``, ``order_messages``,
``delivery_codes``, ``delivery_code_attempts``) plus four nullable columns
on ``orders`` to support the Uber-style delivery flow and the tiered
order-history retention rules.

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-20 21:00:00.000000 UTC
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # orders — add retention + delivery-flow timestamps
    # ------------------------------------------------------------------
    op.add_column(
        "orders",
        sa.Column(
            "driver_accepted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Set when assigned driver accepts the delivery.",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "customer_visible_after",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Customer history visibility resumes after this timestamp.",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "seller_full_visible_until",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Seller sees full order detail until this timestamp; then stripped.",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "delivery_code_locked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Mirror of delivery_codes.locked for quick filtering.",
        ),
    )

    # Backfill seller visibility window for existing orders so history
    # queries behave deterministically on legacy rows.
    op.execute(
        "UPDATE orders SET seller_full_visible_until = placed_at + interval '7 days'"
        " WHERE seller_full_visible_until IS NULL"
    )
    op.execute(
        "UPDATE orders SET customer_visible_after = delivered_at + interval '30 minutes'"
        " WHERE delivered_at IS NOT NULL AND customer_visible_after IS NULL"
    )

    # ------------------------------------------------------------------
    # order_tracking_points
    # ------------------------------------------------------------------
    op.create_table(
        "order_tracking_points",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column(
            "recorded_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_order_tracking_points_order_recorded_at",
        "order_tracking_points",
        ["order_id", "recorded_at"],
    )

    # ------------------------------------------------------------------
    # order_messages — driver/customer chat, archived on delivery.
    # ------------------------------------------------------------------
    op.create_table(
        "order_messages",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sender_role", sa.Text, nullable=False),
        sa.Column("ciphertext", sa.Text, nullable=False),
        sa.Column("nonce", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "archived_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Set when delivery completes; once set, message is admin-only.",
        ),
        sa.CheckConstraint(
            "sender_role IN ('customer','driver')",
            name="ck_order_messages_sender_role",
        ),
    )
    op.create_index(
        "ix_order_messages_order_created_at",
        "order_messages",
        ["order_id", "created_at"],
    )

    # ------------------------------------------------------------------
    # delivery_codes — one 6-digit code per order (customer → driver).
    # ------------------------------------------------------------------
    op.create_table(
        "delivery_codes",
        sa.Column(
            "order_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("code_hash", sa.Text, nullable=False),
        sa.Column(
            "code_plain",
            sa.Text,
            nullable=False,
            comment=(
                "Plaintext code so the customer screen can re-display; "
                "trade-off documented in spec §delivery_codes."
            ),
        ),
        sa.Column(
            "attempts_used",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "locked",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "consumed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # delivery_code_attempts — audit log.
    # ------------------------------------------------------------------
    op.create_table(
        "delivery_code_attempts",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("submitted_code", sa.Text, nullable=False),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column(
            "attempted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_delivery_code_attempts_order",
        "delivery_code_attempts",
        ["order_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_code_attempts_order", table_name="delivery_code_attempts")
    op.drop_table("delivery_code_attempts")
    op.drop_table("delivery_codes")
    op.drop_index("ix_order_messages_order_created_at", table_name="order_messages")
    op.drop_table("order_messages")
    op.drop_index(
        "ix_order_tracking_points_order_recorded_at",
        table_name="order_tracking_points",
    )
    op.drop_table("order_tracking_points")
    op.drop_column("orders", "delivery_code_locked")
    op.drop_column("orders", "seller_full_visible_until")
    op.drop_column("orders", "customer_visible_after")
    op.drop_column("orders", "driver_accepted_at")
