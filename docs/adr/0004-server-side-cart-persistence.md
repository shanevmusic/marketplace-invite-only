# 4. Server-side cart persistence

- Status: accepted
- Date: 2026-04-18
- Phase: 1 (Orchestrator resolution of PRD §9.3)

## Context

Cart persistence can live on the device (simple, lost on reinstall) or on the server (survives device switches; consistent with live product state). Given the invite-only, trusted-user model and the expectation that customers move between devices, the cost of server persistence is justified.

## Decision

Cart state is stored server-side in a `cart_items` table, keyed by `customer_id`. One active cart per customer. Cart is pruned on checkout success. The Database Engineer (Phase 2) must include `cart_items` in the initial schema.

Proposed columns (final shape owned by DB Engineer):

- `id` UUID PK
- `customer_id` UUID FK → users
- `product_id` UUID FK → products
- `quantity` integer (>0)
- `added_at` timestamp
- unique `(customer_id, product_id)`

## Consequences

- Cart API endpoints are required (add/update/remove/list). These will be added to `api-contract.md` in Phase 2 and implemented in Phase 4.
- Cart must be revalidated at checkout against current product availability and price; stale items flagged.
- Minor schema addition in Phase 2.

## Alternatives considered

- **Device-side (SharedPreferences / SQLite):** simpler, but breaks cross-device UX and gives us no insight into cart abandonment.
