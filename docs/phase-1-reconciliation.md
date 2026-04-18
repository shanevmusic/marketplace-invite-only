# Phase 1 — Orchestrator Reconciliation & Sign-off

Date: 2026-04-18.
Inputs reviewed: `architecture.md`, `api-contract.md`, `er-diagram.md`, `prd.md`.

## Cross-cutting checks (PM's five conflict-risk items from PRD §9.5)

| # | Concern | Finding | Status |
|---|---|---|---|
| 1 | State machine enforcement layer | Architect + API contract both enforce at service layer with explicit transitions documented per endpoint (`api-contract.md` lines 510, 518, 526, 600). DB-level CHECK constraint deliberately omitted from `er-diagram.md` so future states are non-breaking. **Dual-write:** service enforces legal transitions; DB has an `orders.status` enum. | ✅ Aligned |
| 2 | WS namespacing (messaging vs. tracking) | Separate namespaces confirmed: `/ws/v1/messaging` and `/ws/v1/delivery/{order_id}` (`api-contract.md` §13.1–13.3). Flutter client manages two connection lifecycles. | ✅ Aligned |
| 3 | Ciphertext-only messages schema | `messages` entity (`er-diagram.md` lines 118–131) contains only `ciphertext`, `nonce`, `ephemeral_public_key`, `ratchet_state`, and metadata. **No plaintext preview field, no subject field, no server-decrypt path.** Push notifications will use a "new message from X" template with no body (Phase 9 to confirm). | ✅ Aligned |
| 4 | Analytics ledger isolation | `order_analytics_snapshots` is append-only, never soft-deleted, uses plain UUID references (no FKs to survive purges), written atomically on `delivered` transition (`architecture.md` §5.5, `er-diagram.md` §5 table). | ✅ Aligned |
| 5 | Asymmetric tracking enforcement point | Server-side filter in `app/ws/delivery_gateway.py` (`api-contract.md` §13.3 "Server-Side Location Filter (normative)"). Filter is normative; requires Security Engineer review for any modification. REST `GET /deliveries/{id}` also excludes `lat/lng` when caller is a customer. | ✅ Aligned |

No conflicts requiring rework. All five PM concerns were pre-addressed by the Architect.

## Resolutions of all 15 architect + contract + ER open questions, plus PM open questions

| ID | Question | Resolution | ADR |
|---|---|---|---|
| PRD §9.1 | Referral token cardinality | Multi-use per seller; per-signup `referrals` rows for graph fidelity | ADR-0002 |
| PRD §9.2 | Who triggers `out_for_delivery` in driver path | Driver OR seller; idempotent; 409 on conflict | ADR-0003 |
| PRD §9.3 | Cart persistence | Server-side `cart_items` table | ADR-0004 |
| PRD §9.4 / Q-C5 | Currency | Single platform currency via `platform_settings.currency_code`; amounts as `bigint` minor units | ADR-0005 |
| Q-A1 | Refresh token storage | Server-side hashed `refresh_tokens` table | ADR-0006 |
| Q-A2 | Referral chain depth | Depth = 1 (direct only) | ADR-0007 |
| Q-A3 / Q-E4 / Q-C2 | Conversation participants + initiation | Strictly 2 participants; bidirectional initiation | ADR-0008 |
| D2 (PROJECT.md §7) | E2E scheme | X25519 + AES-256-GCM; extension seam for ratchet | ADR-0009 |
| Q-A4 | Driver location transport | Support **both** WS push (foreground) and REST POST (background). Phase 7 implements both. | Noted; no ADR needed |
| Q-A5 / Q-E5 | `seller_sales_rollups` table vs. view | Phase 2 DB Engineer decides; default to **materialized view** from `order_analytics_snapshots` unless performance requires a table. | Noted; Phase 2 decision |
| Q-C1 | Can sellers invite drivers? | **No.** Driver onboarding is admin-only. RBAC matrix is correct. | Closed |
| Q-C3 | Driver order-pool visibility | **No pool.** Admin-only assignment; drivers see only assigned orders. | Closed |
| Q-C4 | Who can call `/deliveries/{id}/complete` | Whoever owns the delivery: `deliveries.driver_id = auth_user.id OR deliveries.seller_id = auth_user.id`. 403 otherwise. | Closed |
| Q-E1 | `order_items.product_id` FK behavior | `ON DELETE SET NULL` + snapshot columns (`product_name_snapshot`, `unit_price_minor_snapshot`). DB Engineer implements in Phase 2. | Closed |
| Q-E2 | Delivery location history table | **Defer to Phase 7.** Phase 2 schema stores `current_lat/lng` on `deliveries`; Phase 7 adds `delivery_location_events` as a non-breaking migration. | Closed |
| Q-E3 | Messages GDPR erasure | Add `deleted_at` to `messages` in Phase 6. WS gateway + REST filter soft-deleted messages for non-admin callers. | Phase 6 task |

## Follow-up actions for later phases

- **Phase 2 (DB Engineer):**
  - Include `cart_items` (ADR-0004), `refresh_tokens` (ADR-0006) in initial schema.
  - `order_items`: `product_id` `ON DELETE SET NULL`, add snapshot columns.
  - `invite_links`: `max_uses` nullable, `used_count`, `revoked_at` columns.
  - `platform_settings`: `currency_code` non-null (ADR-0005).
  - Decide `seller_sales_rollups` as materialized view vs. table.
- **Phase 3 (Backend auth):** implement refresh-token rotation against `refresh_tokens` table; admin-only driver invites.
- **Phase 5 (Orders/deliveries):** idempotent `out_for_delivery` transition callable by seller OR driver; `/deliveries/{id}/complete` auth rule.
- **Phase 6 (Messaging):** X25519+AES-GCM implementation; add `messages.deleted_at` for GDPR erasure; audit that no server code path ever sees plaintext.
- **Phase 7 (Tracking):** implement both WS `delivery.location` and REST POST `/deliveries/{id}/location`; add `delivery_location_events` table; reassert server-side customer filter.
- **Phase 9 (Push):** push payloads for new messages carry no body — generic "New message" only.
- **Phase 11 (Admin):** referral graph UI uses per-signup `referrals` rows; admin can grant additional seller visibility to admin-invited customers (ADR-0007).

## Sign-off

Phase 1 stop condition met. Architecture and PRD are **frozen** as the source of truth. Nine ADRs recorded (0001–0009). Open decisions D2 closed; D1, D3, D4, D5 remain deferred to their target phases.

Ready to proceed to **Phase 2 — Database schema**.
