"""Initial schema — all tables, types, indexes, constraints, and seed data.

Revision ID: 0001
Revises: (none)
Create Date: 2026-04-18 00:00:00.000000 UTC

Creates:
  Extensions  : pgcrypto, citext
  Enum types  : user_role, order_status, delivery_status,
                driver_assignment_status, invite_link_type
  Tables (19) : users, refresh_tokens, invite_links, referrals,
                sellers, stores, products, product_images, cart_items,
                orders, order_items, deliveries, driver_assignments,
                conversations, messages, user_public_keys, reviews,
                platform_settings, order_analytics_snapshots
  Mat view    : seller_sales_rollups
  Seed data   : platform_settings singleton row
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB, CITEXT, ENUM as PGEnum

# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Pre-existing enum type references (create_type=False: types already created
# by raw SQL in upgrade() before these are used in op.create_table).
# ---------------------------------------------------------------------------
user_role = PGEnum(
    "admin", "seller", "customer", "driver",
    name="user_role", create_type=False,
)
order_status = PGEnum(
    "pending", "accepted", "preparing", "out_for_delivery",
    "delivered", "completed", "cancelled",
    name="order_status", create_type=False,
)
delivery_status = PGEnum(
    "pending", "in_transit", "delivered", "failed",
    name="delivery_status", create_type=False,
)
driver_assignment_status = PGEnum(
    "requested", "assigned", "accepted", "declined", "cancelled",
    name="driver_assignment_status", create_type=False,
)
invite_link_type = PGEnum(
    "admin_invite", "seller_referral",
    name="invite_link_type", create_type=False,
)


# ---------------------------------------------------------------------------
# UPGRADE
# ---------------------------------------------------------------------------
def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 0. Extensions                                                        #
    # ------------------------------------------------------------------ #
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')

    # ------------------------------------------------------------------ #
    # 1. Enum types                                                        #
    # ------------------------------------------------------------------ #
    op.execute(
        "CREATE TYPE user_role AS ENUM ('admin', 'seller', 'customer', 'driver')"
    )
    op.execute(
        "CREATE TYPE order_status AS ENUM ("
        "'pending', 'accepted', 'preparing', 'out_for_delivery', "
        "'delivered', 'completed', 'cancelled')"
    )
    op.execute(
        "CREATE TYPE delivery_status AS ENUM ('pending', 'in_transit', 'delivered', 'failed')"
    )
    op.execute(
        "CREATE TYPE driver_assignment_status AS ENUM ("
        "'requested', 'assigned', 'accepted', 'declined', 'cancelled')"
    )
    op.execute(
        "CREATE TYPE invite_link_type AS ENUM ('admin_invite', 'seller_referral')"
    )

    # ------------------------------------------------------------------ #
    # 2. users                                                             #
    # ------------------------------------------------------------------ #
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "email",
            CITEXT,
            nullable=False,
            comment="Case-insensitive unique email; stored via CITEXT extension.",
        ),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("disabled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "referring_seller_id",
            UUID(as_uuid=True),
            nullable=True,
            comment=(
                "Plain UUID reference to sellers.id.  No FK constraint to avoid "
                "the users ↔ sellers circular dependency.  See docs/schema.md."
            ),
        ),
        # TimestampMixin
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
        # SoftDeleteMixin
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])
    op.create_index("ix_users_referring_seller_id", "users", ["referring_seller_id"])

    # ------------------------------------------------------------------ #
    # 3. refresh_tokens                                                    #
    # ------------------------------------------------------------------ #
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_refresh_tokens_user_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 hex digest of the raw refresh token.",
        ),
        sa.Column("device_label", sa.String(255), nullable=True),
        sa.Column(
            "issued_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])

    # ------------------------------------------------------------------ #
    # 4. invite_links                                                      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "invite_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "issuer_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_invite_links_issuer_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("type", invite_link_type, nullable=False),
        sa.Column(
            "token",
            sa.String(64),
            nullable=False,
            comment="32-byte URL-safe base64 random token.",
        ),
        sa.Column("role_target", user_role, nullable=True),
        sa.Column(
            "max_uses",
            sa.Integer,
            nullable=True,
            comment="NULL = unlimited (ADR-0002).",
        ),
        sa.Column(
            "used_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.UniqueConstraint("token", name="uq_invite_links_token"),
    )
    op.create_index("ix_invite_links_token", "invite_links", ["token"], unique=True)
    op.create_index("ix_invite_links_issuer_id", "invite_links", ["issuer_id"])
    op.create_index("ix_invite_links_expires_at", "invite_links", ["expires_at"])
    # Partial unique index: one active seller_referral per issuer.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_invite_links_active_seller_referral
            ON invite_links (issuer_id)
            WHERE type = 'seller_referral' AND revoked_at IS NULL
        """
    )

    # ------------------------------------------------------------------ #
    # 5. referrals                                                         #
    # ------------------------------------------------------------------ #
    op.create_table(
        "referrals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "referrer_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_referrals_referrer_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "referred_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_referrals_referred_user_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "invite_link_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "invite_links.id",
                name="fk_referrals_invite_link_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("referred_user_id", name="uq_referrals_referred_user_id"),
    )
    op.create_index("ix_referrals_referrer_id", "referrals", ["referrer_id"])
    op.create_index("ix_referrals_invite_link_id", "referrals", ["invite_link_id"])

    # ------------------------------------------------------------------ #
    # 6. sellers                                                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "sellers",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Same UUID as users.id — shared-PK 1:1 extension pattern.",
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_sellers_user_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("city", sa.Text, nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
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
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_sellers_user_id"),
    )
    op.create_index("ix_sellers_city", "sellers", ["city"])

    # ------------------------------------------------------------------ #
    # 7. stores                                                            #
    # ------------------------------------------------------------------ #
    op.create_table(
        "stores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "seller_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "sellers.id",
                name="fk_stores_seller_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "slug",
            sa.String(255),
            nullable=False,
            comment="URL-safe lower-cased identifier.",
        ),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
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
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("seller_id", name="uq_stores_seller_id"),
        sa.UniqueConstraint("slug", name="uq_stores_slug"),
    )
    op.create_index("ix_stores_slug", "stores", ["slug"])

    # ------------------------------------------------------------------ #
    # 8. products                                                          #
    # ------------------------------------------------------------------ #
    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "seller_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "sellers.id",
                name="fk_products_seller_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "stores.id",
                name="fk_products_store_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "price_minor",
            sa.BigInteger,
            nullable=False,
            comment="Price in smallest monetary unit.  Platform currency (ADR-0005).",
        ),
        sa.Column(
            "stock_quantity",
            sa.Integer,
            nullable=True,
            comment="NULL = unlimited.",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
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
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("price_minor > 0", name="ck_products_price_minor_positive"),
        sa.CheckConstraint(
            "stock_quantity IS NULL OR stock_quantity >= 0",
            name="ck_products_stock_quantity_non_negative",
        ),
    )
    op.create_index(
        "ix_products_seller_id_is_active", "products", ["seller_id", "is_active"]
    )
    op.create_index(
        "ix_products_store_id_is_active", "products", ["store_id", "is_active"]
    )

    # ------------------------------------------------------------------ #
    # 9. product_images                                                    #
    # ------------------------------------------------------------------ #
    op.create_table(
        "product_images",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "products.id",
                name="fk_product_images_product_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "s3_key",
            sa.Text,
            nullable=False,
            comment="S3/GCS object key.  Signed URL generated on demand.",
        ),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_product_images_product_id", "product_images", ["product_id"])

    # ------------------------------------------------------------------ #
    # 10. cart_items                                                       #
    # ------------------------------------------------------------------ #
    op.create_table(
        "cart_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "customer_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_cart_items_customer_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "products.id",
                name="fk_cart_items_product_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column(
            "added_at",
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
        sa.CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
        sa.UniqueConstraint(
            "customer_id", "product_id", name="uq_cart_items_customer_product"
        ),
    )
    op.create_index("ix_cart_items_customer_id", "cart_items", ["customer_id"])

    # ------------------------------------------------------------------ #
    # 11. orders                                                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "customer_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_orders_customer_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "seller_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "sellers.id",
                name="fk_orders_seller_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            comment="Denormalized seller_id for efficient dashboard queries.",
        ),
        sa.Column(
            "store_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "stores.id",
                name="fk_orders_store_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("status", order_status, nullable=False),
        sa.Column("subtotal_minor", sa.BigInteger, nullable=False),
        sa.Column("total_minor", sa.BigInteger, nullable=False),
        sa.Column(
            "delivery_address",
            JSONB,
            nullable=False,
            comment="Keys: line1, line2, city, region, postal, country, lat, lng, notes.",
        ),
        sa.Column(
            "placed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("accepted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("preparing_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("out_for_delivery_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "delivered_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Starts the retention timer.",
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text, nullable=True),
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
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_orders_seller_id_status", "orders", ["seller_id", "status"]
    )
    op.create_index(
        "ix_orders_customer_id_status", "orders", ["customer_id", "status"]
    )
    op.create_index(
        "ix_orders_status_placed_at", "orders", ["status", "placed_at"]
    )
    op.create_index("ix_orders_delivered_at", "orders", ["delivered_at"])

    # ------------------------------------------------------------------ #
    # 12. order_items                                                      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "order_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                name="fk_order_items_order_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "products.id",
                name="fk_order_items_product_id",
                ondelete="SET NULL",
            ),
            nullable=True,
            comment="ON DELETE SET NULL: survives product hard-delete (Q-E1).",
        ),
        sa.Column(
            "product_name_snapshot",
            sa.Text,
            nullable=False,
            comment="Product name at order time.  Immutable.",
        ),
        sa.Column(
            "unit_price_minor_snapshot",
            sa.BigInteger,
            nullable=False,
            comment="Unit price at order time in minor currency units.",
        ),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    # ------------------------------------------------------------------ #
    # 13. deliveries                                                       #
    # ------------------------------------------------------------------ #
    op.create_table(
        "deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                name="fk_deliveries_order_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_deliveries_driver_id",
                ondelete="SET NULL",
            ),
            nullable=True,
            comment="NULL for seller self-deliveries.",
        ),
        sa.Column(
            "seller_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "sellers.id",
                name="fk_deliveries_seller_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("status", delivery_status, nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "current_lat",
            sa.Double(),
            nullable=True,
            comment="Last-known latitude.  History deferred to Phase 7 (Q-E2).",
        ),
        sa.Column("current_lng", sa.Double(), nullable=True),
        sa.Column("last_location_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("distance_meters", sa.Integer, nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.CheckConstraint(
            "driver_id IS NOT NULL OR seller_id IS NOT NULL",
            name="ck_deliveries_at_least_one_actor",
        ),
        sa.UniqueConstraint("order_id", name="uq_deliveries_order_id"),
    )

    # ------------------------------------------------------------------ #
    # 14. driver_assignments                                               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "driver_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                name="fk_driver_assignments_order_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_driver_assignments_driver_id",
                ondelete="SET NULL",
            ),
            nullable=True,
            comment="NULL while in 'requested' pool state.",
        ),
        sa.Column("status", driver_assignment_status, nullable=False),
        sa.Column(
            "requested_by_seller_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "sellers.id",
                name="fk_driver_assignments_requested_by_seller_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "requested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "assigned_by_admin_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_driver_assignments_assigned_by_admin_id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("responded_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_driver_assignments_status_requested_at",
        "driver_assignments",
        ["status", "requested_at"],
    )
    op.create_index(
        "ix_driver_assignments_order_id", "driver_assignments", ["order_id"]
    )
    op.create_index(
        "ix_driver_assignments_driver_id", "driver_assignments", ["driver_id"]
    )

    # ------------------------------------------------------------------ #
    # 15. conversations                                                    #
    # ------------------------------------------------------------------ #
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_a_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_conversations_user_a_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            comment="Lower UUID (canonical ordering enforced by CHECK).",
        ),
        sa.Column(
            "user_b_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_conversations_user_b_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            comment="Higher UUID (canonical ordering enforced by CHECK).",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_message_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "user_a_id < user_b_id",
            name="ck_conversations_canonical_ordering",
        ),
        sa.UniqueConstraint(
            "user_a_id", "user_b_id", name="uq_conversations_user_pair"
        ),
    )
    op.create_index("ix_conversations_user_a_id", "conversations", ["user_a_id"])
    op.create_index("ix_conversations_user_b_id", "conversations", ["user_b_id"])

    # ------------------------------------------------------------------ #
    # 16. messages                                                         #
    # ------------------------------------------------------------------ #
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "conversations.id",
                name="fk_messages_conversation_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_messages_sender_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        # Crypto fields — opaque blobs
        sa.Column(
            "ciphertext",
            sa.LargeBinary,
            nullable=False,
            comment="AES-256-GCM ciphertext.  Opaque to the server.",
        ),
        sa.Column(
            "nonce",
            sa.LargeBinary,
            nullable=False,
            comment="12-byte AES-GCM nonce.",
        ),
        sa.Column(
            "ephemeral_public_key",
            sa.LargeBinary,
            nullable=False,
            comment="32-byte X25519 ephemeral sender public key.",
        ),
        sa.Column(
            "ratchet_state",
            JSONB,
            nullable=True,
            comment="Reserved for Signal double-ratchet upgrade (ADR-0009).  NULL in v1.",
        ),
        sa.Column(
            "sent_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "deleted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="GDPR soft-erasure (Q-E3).  Non-admin callers filter deleted_at IS NULL.",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        "COMMENT ON TABLE messages IS "
        "'E2E-encrypted ciphertext storage.  Server never decrypts.  "
        "No plaintext column exists on this table by design (ADR-0009).'"
    )
    op.create_index(
        "ix_messages_conversation_id_sent_at",
        "messages",
        ["conversation_id", "sent_at"],
    )

    # ------------------------------------------------------------------ #
    # 17. user_public_keys                                                 #
    # ------------------------------------------------------------------ #
    op.create_table(
        "user_public_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_user_public_keys_user_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "public_key",
            sa.LargeBinary,
            nullable=False,
            comment="X25519 public key — 32 bytes raw.",
        ),
        sa.Column(
            "registered_at",
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
        sa.UniqueConstraint("user_id", name="uq_user_public_keys_user_id"),
    )

    # ------------------------------------------------------------------ #
    # 18. reviews                                                          #
    # ------------------------------------------------------------------ #
    op.create_table(
        "reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                name="fk_reviews_order_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_reviews_customer_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "stores.id",
                name="fk_reviews_store_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
            comment="Denormalized for efficient per-store review queries.",
        ),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
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
        sa.CheckConstraint(
            "rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"
        ),
        sa.UniqueConstraint("order_id", name="uq_reviews_order_id"),
    )
    op.create_index("ix_reviews_store_id", "reviews", ["store_id"])
    op.create_index("ix_reviews_customer_id", "reviews", ["customer_id"])

    # ------------------------------------------------------------------ #
    # 19. platform_settings (singleton)                                   #
    # ------------------------------------------------------------------ #
    op.create_table(
        "platform_settings",
        sa.Column(
            "id",
            sa.Integer,
            primary_key=True,
            comment="Singleton row: always 1.  CHECK id = 1 enforces invariant.",
        ),
        sa.Column(
            "retention_min_days",
            sa.Integer,
            nullable=False,
            server_default=sa.text("30"),
            comment="Minimum days after delivery before order may be hard-deleted.",
        ),
        sa.Column(
            "currency_code",
            sa.String(3),
            nullable=False,
            server_default="USD",
            comment="ISO 4217 platform currency (ADR-0005).",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                name="fk_platform_settings_updated_by_user_id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.CheckConstraint("id = 1", name="ck_platform_settings_singleton"),
    )

    # ------------------------------------------------------------------ #
    # 20. order_analytics_snapshots                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "order_analytics_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="Plain UUID — no FK.  Survives order hard-delete.",
        ),
        sa.Column(
            "seller_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="Plain UUID — no FK.",
        ),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "city",
            sa.Text,
            nullable=False,
            comment="Denormalized from stores.city at snapshot time.",
        ),
        sa.Column("item_count", sa.Integer, nullable=False),
        sa.Column("subtotal_minor", sa.BigInteger, nullable=False),
        sa.Column("total_minor", sa.BigInteger, nullable=False),
        sa.Column(
            "delivered_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            comment="Copy of orders.delivered_at.",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="When the snapshot was written.",
        ),
    )
    op.execute(
        "COMMENT ON TABLE order_analytics_snapshots IS "
        "'Append-only; never deleted; survives order purges.'"
    )
    op.create_index(
        "ix_order_analytics_snapshots_seller_id_delivered_at",
        "order_analytics_snapshots",
        ["seller_id", "delivered_at"],
    )
    op.create_index(
        "ix_order_analytics_snapshots_delivered_at",
        "order_analytics_snapshots",
        ["delivered_at"],
    )

    # ------------------------------------------------------------------ #
    # 21. seller_sales_rollups — materialized view                        #
    # ------------------------------------------------------------------ #
    # Refreshed nightly by a Phase-5 background job.
    # REFRESH MATERIALIZED VIEW CONCURRENTLY requires a unique index
    # (created below on seller_id).
    op.execute(
        """
        CREATE MATERIALIZED VIEW seller_sales_rollups AS
        SELECT
            seller_id,
            SUM(total_minor)  AS lifetime_revenue_minor,
            COUNT(*)          AS lifetime_order_count
        FROM order_analytics_snapshots
        GROUP BY seller_id
        WITH DATA
        """
    )
    op.execute(
        "COMMENT ON MATERIALIZED VIEW seller_sales_rollups IS "
        "'Pre-aggregated seller lifetime sales.  "
        "Refreshed nightly via REFRESH MATERIALIZED VIEW CONCURRENTLY by Phase-5 background job.  "
        "Unique index on seller_id required for CONCURRENTLY.'"
    )
    # Unique index required for REFRESH CONCURRENTLY
    op.execute(
        "CREATE UNIQUE INDEX uq_seller_sales_rollups_seller_id "
        "ON seller_sales_rollups (seller_id)"
    )

    # ------------------------------------------------------------------ #
    # 22. Seed: platform_settings singleton row                           #
    # ------------------------------------------------------------------ #
    op.execute(
        """
        INSERT INTO platform_settings (id, retention_min_days, currency_code, updated_at)
        VALUES (1, 30, 'USD', now())
        ON CONFLICT (id) DO NOTHING
        """
    )


# ---------------------------------------------------------------------------
# DOWNGRADE
# ---------------------------------------------------------------------------
def downgrade() -> None:
    # Drop in reverse order of dependencies.

    # Seed row is implicitly removed when the table is dropped.

    # Materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS seller_sales_rollups")

    # Tables (reverse order)
    op.drop_table("order_analytics_snapshots")
    op.drop_table("platform_settings")
    op.drop_table("reviews")
    op.drop_table("user_public_keys")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("driver_assignments")
    op.drop_table("deliveries")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("cart_items")
    op.drop_table("product_images")
    op.drop_table("products")
    op.drop_table("stores")
    op.drop_table("sellers")
    op.drop_table("referrals")
    op.drop_table("invite_links")
    op.drop_table("refresh_tokens")
    op.drop_table("users")

    # Enum types
    op.execute("DROP TYPE IF EXISTS invite_link_type")
    op.execute("DROP TYPE IF EXISTS driver_assignment_status")
    op.execute("DROP TYPE IF EXISTS delivery_status")
    op.execute("DROP TYPE IF EXISTS order_status")
    op.execute("DROP TYPE IF EXISTS user_role")

    # Extensions (leave pgcrypto/citext installed — they may be used elsewhere)
    # op.execute('DROP EXTENSION IF EXISTS "citext"')
    # op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')
