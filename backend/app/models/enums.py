"""Postgres-native ENUM type definitions.

Each enum is declared once here and imported by model modules.  Using
``sa.Enum(..., name=..., create_type=True)`` ensures Alembic emits
``CREATE TYPE ... AS ENUM (...)`` DDL in the migration and
``DROP TYPE ...`` in the downgrade.

NOTE: ``create_type=True`` is the default for ``sa.Enum`` but is set
explicitly here for clarity.
"""

from __future__ import annotations

import sqlalchemy as sa

user_role_enum = sa.Enum(
    "admin",
    "seller",
    "customer",
    "driver",
    name="user_role",
    create_type=True,
)

order_status_enum = sa.Enum(
    "pending",
    "accepted",
    "preparing",
    "out_for_delivery",
    "delivered",
    "completed",
    "cancelled",
    name="order_status",
    create_type=True,
)

delivery_status_enum = sa.Enum(
    "pending",
    "in_transit",
    "delivered",
    "failed",
    name="delivery_status",
    create_type=True,
)

driver_assignment_status_enum = sa.Enum(
    "requested",
    "assigned",
    "accepted",
    "declined",
    "cancelled",
    name="driver_assignment_status",
    create_type=True,
)

invite_link_type_enum = sa.Enum(
    "admin_invite",
    "seller_referral",
    name="invite_link_type",
    create_type=True,
)

# Phase 11 — admin moderation status (migration 0005 creates the PG types).
user_status_enum = sa.Enum(
    "active",
    "suspended",
    name="user_status",
    create_type=False,
)

product_status_enum = sa.Enum(
    "active",
    "disabled",
    "out_of_stock",
    name="product_status",
    create_type=False,
)
