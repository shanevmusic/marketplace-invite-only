"""Phase 11 — user and product status columns for admin moderation.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-18 12:00:00.000000 UTC

Changes:
1. New enum ``user_status`` (``active`` | ``suspended``).
2. New enum ``product_status`` (``active`` | ``disabled`` | ``out_of_stock``).
3. ``users``
   - Add ``status user_status NOT NULL DEFAULT 'active'``.
   - Add ``suspended_at TIMESTAMPTZ NULL``.
   - Add ``suspended_reason TEXT NULL``.
   - Index on ``status``.
4. ``products``
   - Add ``status product_status NOT NULL DEFAULT 'active'``.
   - Add ``disabled_at TIMESTAMPTZ NULL``.
   - Add ``disabled_reason TEXT NULL``.
   - Index on ``status``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types explicitly so we can reuse them.
    user_status = sa.Enum("active", "suspended", name="user_status")
    product_status = sa.Enum(
        "active", "disabled", "out_of_stock", name="product_status"
    )
    user_status.create(op.get_bind(), checkfirst=True)
    product_status.create(op.get_bind(), checkfirst=True)

    # users.status + moderation fields
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.Enum("active", "suspended", name="user_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "users",
        sa.Column("suspended_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("suspended_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_users_status", "users", ["status"])

    # products.status + moderation fields
    op.add_column(
        "products",
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "disabled",
                "out_of_stock",
                name="product_status",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "products",
        sa.Column("disabled_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("disabled_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_products_status", "products", ["status"])


def downgrade() -> None:
    op.drop_index("ix_products_status", table_name="products")
    op.drop_column("products", "disabled_reason")
    op.drop_column("products", "disabled_at")
    op.drop_column("products", "status")

    op.drop_index("ix_users_status", table_name="users")
    op.drop_column("users", "suspended_reason")
    op.drop_column("users", "suspended_at")
    op.drop_column("users", "status")

    sa.Enum(name="product_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_status").drop(op.get_bind(), checkfirst=True)
