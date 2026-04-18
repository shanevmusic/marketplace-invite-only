"""Phase 12 — hot-path performance indexes.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-18 13:00:00.000000 UTC

Adds composite / directional indexes for the queries most often hit by
admin dashboards and user-facing lists.  Every index is created with
``if_not_exists=True`` so reapplying against the already-migrated Supabase
primary is safe.

Nothing is dropped.  Dropping indexes that may be in use is deferred to a
dedicated maintenance window.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users — admin filter list (role + status)
    op.create_index(
        "ix_users_role_status",
        "users",
        ["role", "status"],
        if_not_exists=True,
    )

    # Messages — paginated conversation fetch (DESC for "latest N")
    op.create_index(
        "ix_messages_conversation_id_sent_at_desc",
        "messages",
        ["conversation_id", "sent_at"],
        postgresql_using="btree",
        postgresql_ops={"sent_at": "DESC"},
        if_not_exists=True,
    )

    # Orders — seller inbox (status filter + newest first)
    op.create_index(
        "ix_orders_seller_status_placed_at_desc",
        "orders",
        ["seller_id", "status", "placed_at"],
        postgresql_using="btree",
        postgresql_ops={"placed_at": "DESC"},
        if_not_exists=True,
    )

    # Orders — customer's "my orders" list (newest first)
    op.create_index(
        "ix_orders_customer_placed_at_desc",
        "orders",
        ["customer_id", "placed_at"],
        postgresql_using="btree",
        postgresql_ops={"placed_at": "DESC"},
        if_not_exists=True,
    )

    # Products — seller products list filtered by status
    op.create_index(
        "ix_products_seller_status",
        "products",
        ["seller_id", "status"],
        if_not_exists=True,
    )

    # Invites — admin user-detail "who referred whom" (newest first)
    op.create_index(
        "ix_invite_links_issuer_created_at_desc",
        "invite_links",
        ["issuer_id", "created_at"],
        postgresql_using="btree",
        postgresql_ops={"created_at": "DESC"},
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invite_links_issuer_created_at_desc",
        table_name="invite_links",
        if_exists=True,
    )
    op.drop_index("ix_products_seller_status", table_name="products", if_exists=True)
    op.drop_index(
        "ix_orders_customer_placed_at_desc", table_name="orders", if_exists=True
    )
    op.drop_index(
        "ix_orders_seller_status_placed_at_desc", table_name="orders", if_exists=True
    )
    op.drop_index(
        "ix_messages_conversation_id_sent_at_desc",
        table_name="messages",
        if_exists=True,
    )
    op.drop_index("ix_users_role_status", table_name="users", if_exists=True)
