"""Phase 12 — user_devices table for push-notification endpoints.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-18 13:05:00.000000 UTC
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_devices",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id", name="fk_user_devices_user_id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "token", name="uq_user_devices_user_token"),
    )
    op.create_index(
        "ix_user_devices_user_id", "user_devices", ["user_id"], if_not_exists=True
    )
    op.create_index(
        "ix_user_devices_platform",
        "user_devices",
        ["platform"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_devices_platform", table_name="user_devices", if_exists=True
    )
    op.drop_index(
        "ix_user_devices_user_id", table_name="user_devices", if_exists=True
    )
    op.drop_table("user_devices")
