# Schema Reference — Invite-Only Marketplace

> **Phase 2 deliverable.** Authoritative reference for the database schema
> implemented in `backend/alembic/versions/0001_initial_schema.py`.
> ORM models live in `backend/app/models/`.

---

## Table of Contents

1. [Extensions](#1-extensions)
2. [Enum Types](#2-enum-types)
3. [Entity Reference](#3-entity-reference)
4. [Soft-delete vs Hard-delete Policy](#4-soft-delete-vs-hard-delete-policy)
5. [Retention Enforcement](#5-retention-enforcement)
6. [Cyclic FK Note — users ↔ sellers](#6-cyclic-fk-note--users--sellers)
7. [Materialized View — seller_sales_rollups](#7-materialized-view--seller_sales_rollups)
8. [Open Items for Later Phases](#8-open-items-for-later-phases)

---

## 1. Extensions

| Extension   | Purpose                                                        |
|-------------|----------------------------------------------------------------|
| `pgcrypto`  | `gen_random_uuid()` fallback; available for future crypto ops. |
| `citext`    | Case-insensitive text type used for `users.email`.             |

---

## 2. Enum Types

All enums are Postgres-native `CREATE TYPE … AS ENUM`. They are created before
any table that references them and dropped in the downgrade migration.

| Type name                   | Values                                                                         |
|-----------------------------|--------------------------------------------------------------------------------|
| `user_role`                 | `admin`, `seller`, `customer`, `driver`                                        |
| `order_status`              | `pending`, `accepted`, `preparing`, `out_for_delivery`, `delivered`, `completed`, `cancelled` |
| `delivery_status`           | `pending`, `in_transit`, `delivered`, `failed`                                 |
| `driver_assignment_status`  | `requested`, `assigned`, `accepted`, `declined`, `cancelled`                   |
| `invite_link_type`          | `admin_invite`, `seller_referral`                                              |

---

## 3. Entity Reference

### 3.1 `users`

**Purpose:** Central identity table for all roles. All actors (admin, seller,
customer, driver) share one row here. Role tag drives RBAC.

| Column                | Type                          | Nullable | Notes |
|-----------------------|-------------------------------|----------|-------|
| `id`                  | `uuid` PK                     | ✗        | UUID v4, default `uuid_generate_v4()` |
| `email`               | `citext` UNIQUE               | ✗        | Case-insensitive via CITEXT extension |
| `password_hash`       | `text`                        | ✗        | Argon2id hash |
| `role`                | `user_role`                   | ✗        | Indexed |
| `display_name`        | `varchar(255)`                | ✗        | |
| `phone`               | `varchar(32)`                 | ✓        | |
| `is_active`           | `boolean`                     | ✗        | Default `true` |
| `disabled_at`         | `timestamptz`                 | ✓        | Set when admin disables account |
| `referring_seller_id` | `uuid` (plain, no FK)         | ✓        | See §6 |
| `created_at`          | `timestamptz`                 | ✗        | Server default `now()` |
| `updated_at`          | `timestamptz`                 | ✗        | Server default `now()` |
| `deleted_at`          | `timestamptz`                 | ✓        | Soft-delete |

**Indexes:** `uq_users_email` (UNIQUE), `ix_users_role`, `ix_users_deleted_at`,
`ix_users_referring_seller_id`.

**FKs:** None outbound (avoids cycle — see §6).

**Soft-delete:** `deleted_at IS NOT NULL` hides the user from non-admin callers.
Orders, messages, and analytics snapshots are retained per retention rules.
Hard-erase path (GDPR) deferred to Phase 12.

---

### 3.2 `refresh_tokens`

**Purpose:** Server-side hashed refresh token storage (ADR-0006). Enables
per-device session listing and revocation. Raw token value is never stored.

| Column         | Type           | Nullable | Notes |
|----------------|----------------|----------|-------|
| `id`           | `uuid` PK      | ✗        | |
| `user_id`      | `uuid` FK→users | ✗       | CASCADE on user delete |
| `token_hash`   | `varchar(64)` UNIQUE | ✗  | SHA-256 hex digest of raw token |
| `device_label` | `varchar(255)` | ✓        | User-agent / device label for session UI |
| `issued_at`    | `timestamptz`  | ✗        | |
| `last_used_at` | `timestamptz`  | ✓        | Updated on every successful refresh |
| `expires_at`   | `timestamptz`  | ✗        | Nightly job deletes expired rows |
| `revoked_at`   | `timestamptz`  | ✓        | Set on logout / admin ban |

**Indexes:** `ix_refresh_tokens_user_id`, `ix_refresh_tokens_token_hash`
(UNIQUE), `ix_refresh_tokens_expires_at`.

**FKs:** `fk_refresh_tokens_user_id` → `users.id` ON DELETE CASCADE.

---

### 3.3 `invite_links`

**Purpose:** Invite tokens issued by admins (`admin_invite`) or sellers
(`seller_referral`).

ADR-0002: Each seller has exactly one active multi-use referral token
(`max_uses IS NULL`). Admin invites are single-use, short-TTL, role-targeted.

| Column         | Type                  | Nullable | Notes |
|----------------|-----------------------|----------|-------|
| `id`           | `uuid` PK             | ✗        | |
| `issuer_id`    | `uuid` FK→users       | ✗        | RESTRICT on delete |
| `type`         | `invite_link_type`    | ✗        | |
| `token`        | `varchar(64)` UNIQUE  | ✗        | 32-byte URL-safe base64 |
| `role_target`  | `user_role`           | ✓        | Required for admin_invite; NULL for seller_referral |
| `max_uses`     | `integer`             | ✓        | NULL = unlimited (ADR-0002) |
| `used_count`   | `integer`             | ✗        | Default 0; incremented each signup |
| `expires_at`   | `timestamptz`         | ✓        | NULL = never expires |
| `revoked_at`   | `timestamptz`         | ✓        | Admin/seller revocation |
| `created_at`   | `timestamptz`         | ✗        | |
| `updated_at`   | `timestamptz`         | ✗        | |

**Indexes:** `ix_invite_links_token` (UNIQUE), `ix_invite_links_issuer_id`,
`ix_invite_links_expires_at`.

**Partial unique index:** `uq_invite_links_active_seller_referral` — ensures at
most one active (`revoked_at IS NULL`) `seller_referral` row per `issuer_id`.

**FKs:** `fk_invite_links_issuer_id` → `users.id` ON DELETE RESTRICT.

---

### 3.4 `referrals`

**Purpose:** Immutable referral edge per signup. Enables the admin referral
graph and per-signup audit. ADR-0007: depth = 1.

| Column           | Type            | Nullable | Notes |
|------------------|-----------------|----------|-------|
| `id`             | `uuid` PK       | ✗        | |
| `referrer_id`    | `uuid` FK→users | ✗        | RESTRICT |
| `referred_user_id` | `uuid` FK→users UNIQUE | ✗ | Each user referred at most once |
| `invite_link_id` | `uuid` FK→invite_links | ✗ | RESTRICT |
| `created_at`     | `timestamptz`   | ✗        | |

**Indexes:** `ix_referrals_referrer_id`, `ix_referrals_invite_link_id`,
`uq_referrals_referred_user_id` (UNIQUE).

**FKs:** RESTRICT on all three — referral rows must not be orphaned.

---

### 3.5 `sellers`

**Purpose:** 1:1 extension of `users` for seller-specific data. `id` is the
same UUID as `users.id` (shared-PK pattern).

| Column         | Type            | Nullable | Notes |
|----------------|-----------------|----------|-------|
| `id`           | `uuid` PK       | ✗        | Same as `users.id` |
| `user_id`      | `uuid` FK→users UNIQUE | ✗  | RESTRICT; unique enforces 1:1 |
| `display_name` | `varchar(255)`  | ✗        | |
| `bio`          | `text`          | ✓        | |
| `city`         | `text`          | ✗        | Indexed; gates all downstream queries |
| `country_code` | `char(2)`       | ✗        | ISO 3166-1 alpha-2 |
| `created_at`   | `timestamptz`   | ✗        | |
| `updated_at`   | `timestamptz`   | ✗        | |
| `deleted_at`   | `timestamptz`   | ✓        | Soft-delete |

**Indexes:** `uq_sellers_user_id` (UNIQUE), `ix_sellers_city`.

**Cyclic FK note:** `users.referring_seller_id` logically references
`sellers.id` but has no FK constraint — see §6.

---

### 3.6 `stores`

**Purpose:** Seller's storefront. One-to-one with `sellers`.

| Column        | Type                   | Nullable | Notes |
|---------------|------------------------|----------|-------|
| `id`          | `uuid` PK              | ✗        | |
| `seller_id`   | `uuid` FK→sellers UNIQUE | ✗      | RESTRICT; unique enforces 1:1 |
| `name`        | `varchar(255)`         | ✗        | |
| `slug`        | `varchar(255)` UNIQUE  | ✗        | Lower-cased; URL-safe |
| `description` | `text`                 | ✗        | Default empty string |
| `is_active`   | `boolean`              | ✗        | Default `true` |
| `created_at`  | `timestamptz`          | ✗        | |
| `updated_at`  | `timestamptz`          | ✗        | |
| `deleted_at`  | `timestamptz`          | ✓        | Soft-delete |

**Indexes:** `uq_stores_seller_id`, `uq_stores_slug`, `ix_stores_slug`.

---

### 3.7 `products`

**Purpose:** Items listed in a store. ADR-0005: no per-row currency; amounts in
`platform_settings.currency_code`.

| Column           | Type                    | Nullable | Notes |
|------------------|-------------------------|----------|-------|
| `id`             | `uuid` PK               | ✗        | |
| `seller_id`      | `uuid` FK→sellers       | ✗        | RESTRICT |
| `store_id`       | `uuid` FK→stores        | ✗        | RESTRICT |
| `name`           | `varchar(255)`          | ✗        | |
| `description`    | `text`                  | ✗        | |
| `price_minor`    | `bigint`                | ✗        | Minor currency units; CHECK > 0 |
| `stock_quantity` | `integer`               | ✓        | NULL = unlimited |
| `is_active`      | `boolean`               | ✗        | Default `true` |
| `created_at`     | `timestamptz`           | ✗        | |
| `updated_at`     | `timestamptz`           | ✗        | |
| `deleted_at`     | `timestamptz`           | ✓        | Soft-delete |

**CHECK constraints:** `ck_products_price_minor_positive` (`price_minor > 0`),
`ck_products_stock_quantity_non_negative` (`stock_quantity IS NULL OR stock_quantity >= 0`).

**Indexes:** `ix_products_seller_id_is_active`, `ix_products_store_id_is_active`.

**Soft-delete:** Soft-deleted products hidden from listings. `order_items` FKs
survive via `ON DELETE SET NULL` + snapshot columns.

---

### 3.8 `product_images`

**Purpose:** S3/GCS object keys for product photos. Signed GET URLs generated
on-the-fly; never stored.

| Column          | Type             | Nullable | Notes |
|-----------------|------------------|----------|-------|
| `id`            | `uuid` PK        | ✗        | |
| `product_id`    | `uuid` FK→products | ✗      | CASCADE on product hard-delete |
| `s3_key`        | `text`           | ✗        | S3/GCS object key |
| `display_order` | `integer`        | ✗        | Default 0 |
| `created_at`    | `timestamptz`    | ✗        | |

**Indexes:** `ix_product_images_product_id`.

---

### 3.9 `cart_items`

**Purpose:** Server-side cart persistence (ADR-0004). One row per
(customer, product) combination.

| Column        | Type              | Nullable | Notes |
|---------------|-------------------|----------|-------|
| `id`          | `uuid` PK         | ✗        | |
| `customer_id` | `uuid` FK→users   | ✗        | CASCADE on user delete |
| `product_id`  | `uuid` FK→products | ✗       | CASCADE on product delete |
| `quantity`    | `integer`         | ✗        | CHECK > 0 |
| `added_at`    | `timestamptz`     | ✗        | |
| `updated_at`  | `timestamptz`     | ✗        | |

**CHECK constraints:** `ck_cart_items_quantity_positive`.

**Indexes:** `uq_cart_items_customer_product` (UNIQUE), `ix_cart_items_customer_id`.

---

### 3.10 `orders`

**Purpose:** Order lifecycle from placement to completion and retention.

State machine: `pending → accepted → preparing → out_for_delivery → delivered
→ completed`. `cancelled` reachable from most states by admin or customer
(pre-`accepted`).

ADR-0005: All monetary amounts as bigint minor units; no per-row currency.

| Column                  | Type               | Nullable | Notes |
|-------------------------|--------------------|----------|-------|
| `id`                    | `uuid` PK          | ✗        | |
| `customer_id`           | `uuid` FK→users    | ✗        | RESTRICT |
| `seller_id`             | `uuid` FK→sellers  | ✗        | RESTRICT; denormalized |
| `store_id`              | `uuid` FK→stores   | ✗        | RESTRICT |
| `status`                | `order_status`     | ✗        | |
| `subtotal_minor`        | `bigint`           | ✗        | Sum of line items |
| `total_minor`           | `bigint`           | ✗        | Including fees if any |
| `delivery_address`      | `jsonb`            | ✗        | Keys: line1, line2, city, region, postal, country, lat, lng, notes |
| `placed_at`             | `timestamptz`      | ✗        | |
| `accepted_at`           | `timestamptz`      | ✓        | |
| `preparing_at`          | `timestamptz`      | ✓        | |
| `out_for_delivery_at`   | `timestamptz`      | ✓        | |
| `delivered_at`          | `timestamptz`      | ✓        | Starts retention timer |
| `completed_at`          | `timestamptz`      | ✓        | |
| `cancelled_at`          | `timestamptz`      | ✓        | |
| `cancellation_reason`   | `text`             | ✓        | |
| `created_at`            | `timestamptz`      | ✗        | |
| `updated_at`            | `timestamptz`      | ✗        | |
| `deleted_at`            | `timestamptz`      | ✓        | Soft-delete by retention job only |

**Indexes:** `ix_orders_seller_id_status`, `ix_orders_customer_id_status`,
`ix_orders_status_placed_at`, `ix_orders_delivered_at` (retention sweep).

**Soft-delete:** `deleted_at` is set only by the nightly retention job after
`order_analytics_snapshots` is written. Direct cancellation sets
`status=cancelled`, not `deleted_at`.

---

### 3.11 `order_items`

**Purpose:** Line items with price/name snapshots. Q-E1 resolution:
`product_id ON DELETE SET NULL`; snapshot columns preserve history.

| Column                      | Type                     | Nullable | Notes |
|-----------------------------|--------------------------|----------|-------|
| `id`                        | `uuid` PK                | ✗        | |
| `order_id`                  | `uuid` FK→orders         | ✗        | CASCADE |
| `product_id`                | `uuid` FK→products       | ✓        | ON DELETE SET NULL |
| `product_name_snapshot`     | `text`                   | ✗        | Immutable after INSERT |
| `unit_price_minor_snapshot` | `bigint`                 | ✗        | Price at order time |
| `quantity`                  | `integer`                | ✗        | CHECK > 0 |

**CHECK constraints:** `ck_order_items_quantity_positive`.

**Indexes:** `ix_order_items_order_id`.

---

### 3.12 `deliveries`

**Purpose:** Delivery record lifecycle and last-known location.

Created when seller (or driver) transitions order to `out_for_delivery`.
Full location history deferred to Phase 7 (`delivery_location_events` — Q-E2).

| Column              | Type                  | Nullable | Notes |
|---------------------|-----------------------|----------|-------|
| `id`                | `uuid` PK             | ✗        | |
| `order_id`          | `uuid` FK→orders UNIQUE | ✗      | CASCADE; one delivery per order |
| `driver_id`         | `uuid` FK→users       | ✓        | ON DELETE SET NULL; NULL for self-delivery |
| `seller_id`         | `uuid` FK→sellers     | ✗        | RESTRICT; seller who started delivery |
| `status`            | `delivery_status`     | ✗        | |
| `started_at`        | `timestamptz`         | ✓        | |
| `delivered_at`      | `timestamptz`         | ✓        | |
| `current_lat`       | `double precision`    | ✓        | Last-known latitude |
| `current_lng`       | `double precision`    | ✓        | Last-known longitude |
| `last_location_at`  | `timestamptz`         | ✓        | Timestamp of most-recent location |
| `distance_meters`   | `integer`             | ✓        | |
| `duration_seconds`  | `integer`             | ✓        | |

**CHECK constraints:** `ck_deliveries_at_least_one_actor`
(`driver_id IS NOT NULL OR seller_id IS NOT NULL`).

**Unique:** `uq_deliveries_order_id`.

---

### 3.13 `driver_assignments`

**Purpose:** Audit trail for admin driver-assignment actions. Multiple rows
per order if the admin reassigns.

| Column                     | Type                          | Nullable | Notes |
|----------------------------|-------------------------------|----------|-------|
| `id`                       | `uuid` PK                     | ✗        | |
| `order_id`                 | `uuid` FK→orders              | ✗        | CASCADE |
| `driver_id`                | `uuid` FK→users               | ✓        | ON DELETE SET NULL; NULL in `requested` state |
| `status`                   | `driver_assignment_status`    | ✗        | |
| `requested_by_seller_id`   | `uuid` FK→sellers             | ✗        | RESTRICT |
| `requested_at`             | `timestamptz`                 | ✗        | |
| `assigned_by_admin_id`     | `uuid` FK→users               | ✓        | ON DELETE SET NULL |
| `assigned_at`              | `timestamptz`                 | ✓        | |
| `responded_at`             | `timestamptz`                 | ✓        | |
| `decline_reason`           | `text`                        | ✓        | |

**Indexes:** `ix_driver_assignments_status_requested_at`,
`ix_driver_assignments_order_id`, `ix_driver_assignments_driver_id`.

---

### 3.14 `conversations`

**Purpose:** Two-participant E2E messaging thread (ADR-0008). Canonical
ordering: `user_a_id < user_b_id` (by UUID bytes).

| Column           | Type             | Nullable | Notes |
|------------------|------------------|----------|-------|
| `id`             | `uuid` PK        | ✗        | |
| `user_a_id`      | `uuid` FK→users  | ✗        | RESTRICT; lower UUID |
| `user_b_id`      | `uuid` FK→users  | ✗        | RESTRICT; higher UUID |
| `created_at`     | `timestamptz`    | ✗        | |
| `last_message_at`| `timestamptz`    | ✓        | Updated on each message |

**CHECK constraints:** `ck_conversations_canonical_ordering`
(`user_a_id < user_b_id`).

**Unique:** `uq_conversations_user_pair` on `(user_a_id, user_b_id)`.

**Indexes:** `ix_conversations_user_a_id`, `ix_conversations_user_b_id`.

---

### 3.15 `messages`

**Purpose:** E2E-encrypted ciphertext storage (ADR-0009).

> ⚠️ **This table stores ciphertext only. No plaintext column exists by
> design. The server never decrypts.**

| Column                | Type            | Nullable | Notes |
|-----------------------|-----------------|----------|-------|
| `id`                  | `uuid` PK       | ✗        | |
| `conversation_id`     | `uuid` FK→conversations | ✗  | CASCADE |
| `sender_id`           | `uuid` FK→users | ✗        | RESTRICT |
| `ciphertext`          | `bytea`         | ✗        | AES-256-GCM ciphertext |
| `nonce`               | `bytea`         | ✗        | 12-byte AES-GCM nonce |
| `ephemeral_public_key`| `bytea`         | ✗        | 32-byte X25519 sender ephemeral key |
| `ratchet_state`       | `jsonb`         | ✓        | Reserved for double-ratchet (ADR-0009) |
| `sent_at`             | `timestamptz`   | ✗        | |
| `read_at`             | `timestamptz`   | ✓        | Set when recipient reads |
| `deleted_at`          | `timestamptz`   | ✓        | GDPR soft-erasure (Q-E3) |
| `created_at`          | `timestamptz`   | ✗        | |

**Indexes:** `ix_messages_conversation_id_sent_at` (cursor pagination).

**Table comment:** stored in Postgres as a `COMMENT ON TABLE`.

---

### 3.16 `user_public_keys`

**Purpose:** X25519 public key registry. 1:1 with `users`. Private keys never
leave the device.

| Column          | Type             | Nullable | Notes |
|-----------------|------------------|----------|-------|
| `id`            | `uuid` PK        | ✗        | |
| `user_id`       | `uuid` FK→users UNIQUE | ✗   | CASCADE; upsert for key rotation |
| `public_key`    | `bytea`          | ✗        | 32-byte X25519 public key (raw) |
| `registered_at` | `timestamptz`    | ✗        | |
| `updated_at`    | `timestamptz`    | ✗        | |

**Unique:** `uq_user_public_keys_user_id`.

---

### 3.17 `reviews`

**Purpose:** Private order reviews. 1:1 with `orders`. Not public — visibility
restricted to seller + admin at the service layer.

| Column        | Type              | Nullable | Notes |
|---------------|-------------------|----------|-------|
| `id`          | `uuid` PK         | ✗        | |
| `order_id`    | `uuid` FK→orders UNIQUE | ✗   | CASCADE; one review per order |
| `customer_id` | `uuid` FK→users   | ✗        | RESTRICT |
| `store_id`    | `uuid` FK→stores  | ✗        | RESTRICT; denormalized |
| `rating`      | `integer`         | ✗        | CHECK 1..5 |
| `comment`     | `text`            | ✓        | |
| `created_at`  | `timestamptz`     | ✗        | |
| `updated_at`  | `timestamptz`     | ✗        | |

**CHECK constraints:** `ck_reviews_rating_range` (`rating >= 1 AND rating <= 5`).

**Indexes:** `uq_reviews_order_id`, `ix_reviews_store_id`, `ix_reviews_customer_id`.

---

### 3.18 `platform_settings`

**Purpose:** Singleton platform-wide configuration row. PK is integer 1.

| Column                  | Type              | Nullable | Notes |
|-------------------------|-------------------|----------|-------|
| `id`                    | `integer` PK      | ✗        | Always 1; CHECK enforces singleton |
| `retention_min_days`    | `integer`         | ✗        | Default 30; admin-configurable |
| `currency_code`         | `char(3)`         | ✗        | ISO 4217 (ADR-0005); default 'USD' |
| `updated_at`            | `timestamptz`     | ✗        | |
| `updated_by_user_id`    | `uuid` FK→users   | ✓        | ON DELETE SET NULL |

**CHECK constraints:** `ck_platform_settings_singleton` (`id = 1`).

**Seed:** Row `(id=1, retention_min_days=30, currency_code='USD')` inserted by
the initial migration via `ON CONFLICT (id) DO NOTHING`.

---

### 3.19 `order_analytics_snapshots`

**Purpose:** Append-only analytics ledger. Written atomically at the
`delivered` transition. Never soft-deleted or hard-deleted. Survives all order
purges.

All references are plain UUIDs with **no FK constraints** by design.

| Column           | Type             | Nullable | Notes |
|------------------|------------------|----------|-------|
| `id`             | `uuid` PK        | ✗        | |
| `order_id`       | `uuid` (plain)   | ✗        | No FK — survives order delete |
| `seller_id`      | `uuid` (plain)   | ✗        | No FK |
| `store_id`       | `uuid` (plain)   | ✗        | No FK |
| `customer_id`    | `uuid` (plain)   | ✗        | No FK |
| `city`           | `text`           | ✗        | Denormalized from stores.city |
| `item_count`     | `integer`        | ✗        | |
| `subtotal_minor` | `bigint`         | ✗        | |
| `total_minor`    | `bigint`         | ✗        | |
| `delivered_at`   | `timestamptz`    | ✗        | Copy of orders.delivered_at |
| `created_at`     | `timestamptz`    | ✗        | When snapshot was written |

**Indexes:** `ix_order_analytics_snapshots_seller_id_delivered_at`,
`ix_order_analytics_snapshots_delivered_at`.

**Table comment:** stored as a Postgres `COMMENT ON TABLE`.

---

## 4. Soft-delete vs Hard-delete Policy

| Entity                      | Deletion mode       | Retention gating                             | Analytics persist independently? |
|-----------------------------|---------------------|----------------------------------------------|----------------------------------|
| `users`                     | Soft-delete         | Profile hidden; data retained                | N/A (analytics use plain UUIDs)  |
| `sellers`                   | Soft-delete         | Implicit via user soft-delete                | Yes — analytics use plain UUIDs  |
| `stores`                    | Soft-delete         | Visibility propagated to products/orders     | Yes                              |
| `products`                  | Soft-delete         | Hidden from listings; order snapshots intact | Yes (snapshot columns)           |
| `orders`                    | Soft-delete → hard-purge by retention job | Gated by `platform_settings.retention_min_days` after `delivered_at` | Yes — `order_analytics_snapshots` |
| `order_items`               | Cascade with orders | Same as orders                               | Yes (snapshot columns)           |
| `deliveries`                | Cascade with orders | Same as orders                               | N/A                              |
| `driver_assignments`        | Cascade with orders | Same as orders                               | N/A                              |
| `reviews`                   | Cascade with orders | Survives if order row remains                | N/A                              |
| `cart_items`                | Hard-delete on checkout / CASCADE on product | No gating | N/A               |
| `conversations`             | No delete implemented in v1 | No retention job | N/A             |
| `messages`                  | Soft-delete via `deleted_at` | GDPR erasure path (Phase 6/12) | N/A  |
| `order_analytics_snapshots` | **Never deleted**   | Permanent record                             | N/A — IS the analytics record    |
| `refresh_tokens`            | Hard-delete by nightly sweep | After `expires_at`                  | N/A                              |
| `platform_settings`         | Singleton — not deleted | N/A                                     | N/A                              |
| `user_public_keys`          | Cascade with users  | N/A                                          | N/A                              |

---

## 5. Retention Enforcement

Sequence of events for order retention:

1. **Order delivered** — service layer transitions order `status` to
   `delivered`, sets `delivered_at = now()`.
2. **Analytics snapshot written** — in the same DB transaction (or an
   immediate background task with error handling), a row is inserted into
   `order_analytics_snapshots` with plain UUID references. This row is
   permanent.
3. **Retention timer starts** — the nightly background job (Phase 5)
   queries: `orders WHERE delivered_at < now() - retention_min_days * INTERVAL '1 day'
   AND deleted_at IS NULL`.
4. **Eligibility check** — the job confirms an analytics snapshot exists for
   the order before deleting (belt-and-suspenders guard).
5. **Hard-purge** — the job hard-deletes eligible order rows. `order_items`
   cascade-deletes. `deliveries` and `driver_assignments` cascade-delete.
   `reviews` cascade-deletes. **Analytics snapshots are unaffected** (no FK).
6. **Admin configuration** — `platform_settings.retention_min_days` (default
   30) is the platform minimum. Sellers cannot configure a lower threshold
   (enforced at service layer in Phase 5).

---

## 6. Cyclic FK Note — users ↔ sellers

`users.referring_seller_id` logically references `sellers.id` — a customer or
newly-onboarded seller was referred by that seller.

However, `sellers.user_id` already has a FK to `users.id`. If
`users.referring_seller_id` also had a FK to `sellers.id`, we would have a
circular dependency:

```
users → sellers (via referring_seller_id FK)
sellers → users (via user_id FK)
```

This prevents `CREATE TABLE` from completing without deferrable constraints and
complicates Alembic migration ordering.

**Resolution:** `users.referring_seller_id` is a **plain `uuid` column with
no FK constraint**. The referential integrity is enforced at the service layer
(Phase 3/4): when a user signs up via a seller's referral link, the service
verifies that the seller exists before writing the signup. This is documented
in code comments on both the `User` model and this schema doc.

---

## 7. Materialized View — `seller_sales_rollups`

```sql
CREATE MATERIALIZED VIEW seller_sales_rollups AS
SELECT
    seller_id,
    SUM(total_minor)  AS lifetime_revenue_minor,
    COUNT(*)          AS lifetime_order_count
FROM order_analytics_snapshots
GROUP BY seller_id
WITH DATA;

CREATE UNIQUE INDEX uq_seller_sales_rollups_seller_id
    ON seller_sales_rollups (seller_id);
```

**Purpose:** Pre-aggregated seller lifetime revenue and order count for fast
seller-dashboard queries. Reduces load on the primary at scale.

**Refresh policy:** Refreshed **nightly** by the Phase-5 background job using:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY seller_sales_rollups;
```

`CONCURRENTLY` allows reads to continue during refresh (no exclusive lock).
It requires the unique index `uq_seller_sales_rollups_seller_id` — already
created in the initial migration.

**ORM:** No SQLAlchemy model is defined for this view (it is read-only and
refreshed by the background job). The analytics service (Phase 5) may query it
directly with `text(...)` or a Core `select()` against a `Table` reflection.

---

## 8. Open Items for Later Phases

These items were deferred and are tracked here for the implementing phase:

| ID    | Item                                                              | Target phase |
|-------|-------------------------------------------------------------------|--------------|
| Q-E2  | `delivery_location_events` time-series table for location history | Phase 7      |
| Q-E3  | `messages.deleted_at` for GDPR erasure; WS/REST filtering        | Phase 6      |
| D1    | AWS vs GCP primary cloud target                                   | Phase 13     |
| D3    | Admin surface: Flutter tab vs lightweight web client             | Phase 11     |
| D4    | Map provider: Mapbox vs Google Maps                               | Phase 10     |
| D5    | Push provider: FCM+APNs vs OneSignal                             | Phase 9      |
| GDPR  | Full user hard-erase path (GDPR Article 17)                      | Phase 12     |
| ADR-0009 | Signal double-ratchet upgrade (`ratchet_state` column reserved) | Post-GA   |

**Phase 7 extension point** (Q-E2): `delivery_location_events` can be added
as a non-breaking migration alongside the existing `deliveries.current_lat/lng`
columns. The current schema is designed to accommodate this without changes to
existing indexes or FK relationships.
