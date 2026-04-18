"""Phase 6 — messaging: multi-key rotation, message retention, recipient_key_id.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-18 08:00:00.000000 UTC

Changes:
1. ``user_public_keys``
   - Drop the 1:1 ``UNIQUE (user_id)`` constraint (renamed index).
   - Add ``key_version INT NOT NULL DEFAULT 1``.
   - Add ``status VARCHAR(16) NOT NULL DEFAULT 'active'`` with CHECK.
   - Add ``rotated_at TIMESTAMPTZ NULL``, ``revoked_at TIMESTAMPTZ NULL``,
     ``created_at TIMESTAMPTZ NOT NULL DEFAULT now()``.
   - Add partial unique index: at most one ACTIVE key per user.
   - Add composite index ``(user_id, status)``.
2. ``messages``
   - Add ``recipient_key_id UUID NULL`` FK → ``user_public_keys.id``
     ON DELETE SET NULL.
3. ``platform_settings``
   - Add ``message_retention_days INT NOT NULL DEFAULT 90`` with CHECK >= 7.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # 1) user_public_keys — multi-key support
    # -------------------------------------------------------------------
    # Drop the 1:1 UNIQUE constraint on (user_id) — keys rotate additively.
    op.drop_constraint(
        "uq_user_public_keys_user_id",
        "user_public_keys",
        type_="unique",
    )

    op.add_column(
        "user_public_keys",
        sa.Column(
            "key_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "user_public_keys",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.add_column(
        "user_public_keys",
        sa.Column(
            "rotated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "user_public_keys",
        sa.Column(
            "revoked_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "user_public_keys",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_check_constraint(
        "ck_user_public_keys_status_valid",
        "user_public_keys",
        "status IN ('active','rotated','revoked')",
    )
    op.create_index(
        "uq_user_public_keys_one_active",
        "user_public_keys",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_user_public_keys_user_id_status",
        "user_public_keys",
        ["user_id", "status"],
    )

    # -------------------------------------------------------------------
    # 2) messages — recipient_key_id
    # -------------------------------------------------------------------
    op.add_column(
        "messages",
        sa.Column(
            "recipient_key_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_messages_recipient_key_id",
        "messages",
        "user_public_keys",
        ["recipient_key_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # -------------------------------------------------------------------
    # 3) platform_settings.message_retention_days
    # -------------------------------------------------------------------
    op.add_column(
        "platform_settings",
        sa.Column(
            "message_retention_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("90"),
        ),
    )
    op.create_check_constraint(
        "ck_platform_settings_message_retention_min",
        "platform_settings",
        "message_retention_days >= 7",
    )


def downgrade() -> None:
    # platform_settings
    op.drop_constraint(
        "ck_platform_settings_message_retention_min",
        "platform_settings",
        type_="check",
    )
    op.drop_column("platform_settings", "message_retention_days")

    # messages
    op.drop_constraint(
        "fk_messages_recipient_key_id",
        "messages",
        type_="foreignkey",
    )
    op.drop_column("messages", "recipient_key_id")

    # user_public_keys
    op.drop_index("ix_user_public_keys_user_id_status", table_name="user_public_keys")
    op.drop_index("uq_user_public_keys_one_active", table_name="user_public_keys")
    op.drop_constraint(
        "ck_user_public_keys_status_valid",
        "user_public_keys",
        type_="check",
    )
    op.drop_column("user_public_keys", "created_at")
    op.drop_column("user_public_keys", "revoked_at")
    op.drop_column("user_public_keys", "rotated_at")
    op.drop_column("user_public_keys", "status")
    op.drop_column("user_public_keys", "key_version")

    op.create_unique_constraint(
        "uq_user_public_keys_user_id",
        "user_public_keys",
        ["user_id"],
    )
