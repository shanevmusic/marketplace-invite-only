"""Store visibility — add stores.is_public flag.

Adds a public/invite-only toggle on each store. Default is FALSE (invite-only)
to preserve current ADR-0007 referral-scoped behavior. Sellers opt-in to public
discovery via PATCH /stores/me.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-20 18:50:00.000000 UTC
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stores",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment=(
                "If true, any logged-in customer can browse this store via "
                "Discover. If false (default), only customers referred by "
                "this seller's invite link can see it (ADR-0007)."
            ),
        ),
    )
    # Partial index so the public-store filter in browse queries is fast.
    op.create_index(
        "ix_stores_is_public_true",
        "stores",
        ["id"],
        postgresql_where=sa.text("is_public = true AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_stores_is_public_true", table_name="stores")
    op.drop_column("stores", "is_public")
