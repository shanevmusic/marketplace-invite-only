"""Phase 5 — order auto-complete grace, snapshot idempotency.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-18 06:30:00.000000 UTC

- Adds ``platform_settings.order_auto_complete_grace_hours`` (default 72).
- Adds ``UNIQUE (order_id)`` on ``order_analytics_snapshots`` so the
  completion writer can use ``INSERT ... ON CONFLICT DO NOTHING`` for
  idempotency (ADR-0012 D3).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column(
            "order_auto_complete_grace_hours",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("72"),
            comment=(
                "Hours after delivery before a delivered order auto-completes "
                "(ADR-0012 D4)."
            ),
        ),
    )
    op.create_check_constraint(
        "ck_platform_settings_auto_complete_grace_positive",
        "platform_settings",
        "order_auto_complete_grace_hours >= 1",
    )

    op.create_unique_constraint(
        "uq_order_analytics_snapshots_order_id",
        "order_analytics_snapshots",
        ["order_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_order_analytics_snapshots_order_id",
        "order_analytics_snapshots",
        type_="unique",
    )
    op.drop_constraint(
        "ck_platform_settings_auto_complete_grace_positive",
        "platform_settings",
        type_="check",
    )
    op.drop_column("platform_settings", "order_auto_complete_grace_hours")
