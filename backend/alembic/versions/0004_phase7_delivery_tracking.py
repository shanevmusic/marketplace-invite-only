"""Phase 7 — delivery tracking: ETA fields on deliveries, metric fields on snapshots.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-18 10:00:00.000000 UTC

Changes:
1. ``deliveries``
   - Add ``current_eta_seconds INT NULL``.
   - Add ``current_eta_updated_at TIMESTAMPTZ NULL``.
2. ``order_analytics_snapshots``
   - Add ``delivery_duration_seconds INT NULL``.
   - Add ``delivery_distance_meters INT NULL``.
   Backwards-compatible; older snapshots keep NULL.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deliveries",
        sa.Column("current_eta_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "deliveries",
        sa.Column(
            "current_eta_updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "order_analytics_snapshots",
        sa.Column("delivery_duration_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "order_analytics_snapshots",
        sa.Column("delivery_distance_meters", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_analytics_snapshots", "delivery_distance_meters")
    op.drop_column("order_analytics_snapshots", "delivery_duration_seconds")
    op.drop_column("deliveries", "current_eta_updated_at")
    op.drop_column("deliveries", "current_eta_seconds")
