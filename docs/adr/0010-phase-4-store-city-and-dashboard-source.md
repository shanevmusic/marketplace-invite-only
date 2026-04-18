# 10. Phase 4 — Store city stored on `sellers.city`; dashboard reads from snapshots

- Status: accepted
- Date: 2026-04-18
- Phase: 4 (Backend B — sellers, stores, products)

## Context

Phase 4 required two decisions that the Phase 2 schema left ambiguous.

### 1. Where does a store's city live?

The Phase 1 API contract (`docs/api-contract.md §5`) advertises `city` as a
field on the store payload (POST /stores body, GET /stores response).  The
Phase 2 schema, however, puts `city` on the `sellers` table, not `stores`.
Adding a redundant `stores.city` column would create two writable sources
of truth — an invitation to drift.

### 2. Where does the seller dashboard read its lifetime metrics from?

Phase 2 shipped two candidate sources:

- `order_analytics_snapshots` — append-only, no foreign keys, written at
  the `delivered` transition, designed to survive order and product
  deletion.
- `seller_sales_rollups` — a materialized view aggregating the above,
  refreshed nightly by a Phase-5 job that does not yet exist.

The orchestrator prompt demanded that `lifetime_sales_amount` persist
across both product soft-delete and order deletion.

## Decision

### 1. `sellers.city` is the single source of truth; POST /stores requires `city` in the body.

The seller's city lives on `sellers.city` (as shipped in Phase 2).  The
`POST /stores` and `PATCH /stores/me` endpoints accept `city` in the body
and persist it to the seller profile.  Store responses include `city` via
a join against the seller row.  The store model itself is not modified,
so no migration is needed.

This keeps the schema flat, preserves the invariant that a seller has
exactly one city (via the 1:1 `sellers`↔`stores` relationship), and
continues to satisfy the contract's promise that a store exposes a
`city` field.

### 2. The seller dashboard reads directly from `order_analytics_snapshots`.

`GET /sellers/me/dashboard` aggregates `total_minor` and row counts
directly from `order_analytics_snapshots` filtered by `seller_id`.  The
materialized view `seller_sales_rollups` is NOT queried; it will become
useful in later phases for admin-level cross-seller reports where the
read cost of aggregating N snapshots dominates.

Reading directly from the snapshot table means:

- numbers are strictly correct without waiting for a nightly refresh;
- the dashboard inherits the table's deletion-survival guarantees for
  free (snapshots have no FKs, so orders/products/stores can disappear
  without affecting the aggregate);
- no refresh job needs to exist for Phase 4 to ship;
- the query is O(snapshots-per-seller), which is acceptable for the
  foreseeable future and easily switched to the MV later without
  changing the endpoint's contract.

## Consequences

- `city` is only mutable via the seller-owned endpoints (POST /stores /
  PATCH /stores/me); no `sellers/me/city` endpoint exists in Phase 4.
- If a seller changes their city via `PATCH /stores/me`, the snapshot
  rows for prior orders keep their denormalized `city` (intentional —
  snapshots are a ledger, not a live view).
- Phase 5's planned refresh job for `seller_sales_rollups` becomes an
  optimization rather than a correctness requirement.

## Alternatives considered

- **Add `stores.city`**: rejected — creates two writable sources of truth.
- **Serve `city` only via `GET /sellers/me`**: rejected — breaks the
  contract's store payload shape and forces clients to do two reads.
- **Read the dashboard off `seller_sales_rollups`**: rejected — couples
  correctness to a not-yet-built refresh job and would break the "sales
  survive deletion" stop-condition until that job runs.
