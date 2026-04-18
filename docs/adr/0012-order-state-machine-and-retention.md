# 12. Order state machine, retention timer, and snapshot idempotency

- Status: accepted
- Date: 2026-04-18
- Phase: 5 (Backend C — orders & fulfillment)

## Context

Phase 5 implements the full order lifecycle, retention-gated deletion,
and purge job. Several cross-cutting design decisions deserve explicit
records so the rules are discoverable in one place.

## Decisions

### D1 — Initial state name

The Phase 2 `order_status` enum uses `pending` for the initial state;
the PRD / API contract refers to the initial state as `placed`. We
keep the enum as-is and treat `pending` as synonymous with "placed" in
all user-facing descriptions. The dashboard active-order filter (Phase
4) already hard-codes `pending`, so renaming the enum value would
thrash the existing code for no database benefit.

The state diagram is therefore:

```
pending → accepted → preparing → out_for_delivery → delivered → completed
   └──────────────────┬──────────────────┘            │
                     ▼                                ▼
                cancelled (admin after OFD)       cancelled (n/a, terminal)
```

Terminal states: `completed`, `cancelled`.

### D2 — Retention timer starts at **terminal-at**, not `delivered_at`

The model comment says "delivered_at starts the retention timer",
but the PRD says retention is measured from the order's terminal
state. A cancelled order that never delivered still needs to age past
the retention window before deletion.

Phase 5 defines **terminal-at** as:

- `completed_at` if the order is in state `completed`;
- `cancelled_at` if the order is in state `cancelled`;
- NULL otherwise (order is not yet eligible for deletion).

Retention gate: `DELETE /orders/{id}` succeeds only when
`now() - terminal_at >= platform_settings.retention_min_days`.
Non-terminal orders return `ORDER_RETENTION_NOT_MET` (409).

**No admin override.** The task spec is explicit: admins cannot delete
orders before the retention window expires. If someone needs to, they
lower `platform_settings.retention_min_days` first and then run the
purge (both are audited actions).

### D3 — Analytics snapshot at `completed`, idempotent

Snapshots are written on the `delivered → completed` transition, NOT
at `delivered`. Reasoning: "completed" is the point at which revenue
is recognised (customer confirmed OR auto-completed), matching the
dashboard's lifetime-sales semantics. Cancellations never snapshot.

**Idempotency:** this migration adds
`UNIQUE (order_id)` on `order_analytics_snapshots`. The snapshot
writer uses `INSERT ... ON CONFLICT (order_id) DO NOTHING` so
re-running the completion path (e.g. retry after network error) is
safe. The purge job also calls the snapshot writer as a pre-flight —
if the transition somehow skipped snapshotting, the purge will catch
it up before deleting the order row.

The snapshot + state-transition happens in a single DB transaction:
if the snapshot insert fails, the transition fails. This preserves
the invariant "every completed order has an immortal analytics row."

### D4 — Auto-complete after grace period

Customers may forget to confirm receipt. The task spec calls for an
admin-configurable grace period (default 72 hours) after which a
`delivered` order auto-completes. We store this as
`platform_settings.order_auto_complete_grace_hours` (added in this
phase's migration). The autocomplete runner is plumbed via the purge
job endpoint (`POST /admin/jobs/purge-orders`) which, in addition to
purging, promotes `delivered → completed` for orders whose
`delivered_at + grace_hours < now()`. This keeps the scheduler stub
minimal; splitting into two endpoints is a later-phase optimisation.

### D5 — Fulfillment-mode choice

There is no dedicated `fulfillment_mode` column. Instead:

- Self-deliver path: `deliveries.driver_id` is NULL, `seller_id`
  equals the order's seller. Created by `POST /orders/{id}/self-deliver`.
- Driver-assigned path: a `driver_assignments` row with
  `status='requested'` and `driver_id IS NULL` is created by
  `POST /orders/{id}/request-driver`. An admin later flips the row to
  `status='assigned'` with a `driver_id` via
  `POST /admin/orders/{id}/assign-driver`, and a `deliveries` row is
  lazily created at the `out_for_delivery` transition with the
  assigned driver.

The existing Phase 2 tables cover both modes — no new tables are
required. This matches the Option B language in the task spec
("flip a flag on deliveries row depending on Phase 2 schema").

### D6 — Retention gate on `DELETE /orders/{id}` is purely time-based

The deletion endpoint does NOT care which actor is calling (customer,
seller, admin) beyond authentication. If the retention window has
elapsed, any of (customer who placed the order, seller who sold, admin)
may delete it. This deliberately differs from cancellation rules
(which are state-dependent) to keep retention semantics simple.

### D7 — Test-time override of "now"

For retention and grace-period tests we follow Option (b) from the task
prompt: fixtures advance `delivered_at` / `cancelled_at` /
`completed_at` via direct SQL, rather than introducing a global clock
override. This keeps production code free of "if in test, shift time"
branches.

## Consequences

- One new Alembic migration (`0002_phase5_orders.py`) that:
  - adds `platform_settings.order_auto_complete_grace_hours` (integer,
    default 72, CHECK >= 1);
  - adds a unique index `uq_order_analytics_snapshots_order_id`;
  - adds `driver_assignment_status` enum value `pending_assignment` via
    `ALTER TYPE` — **NOT** needed; we reuse the existing `requested` value.
    (Left as a note so future readers don't chase it.)
- All new endpoints enforce the invariants described above.
- The snapshot idempotency invariant means double-completion attempts
  now return 409 `ORDER_INVALID_TRANSITION` rather than silently
  duplicating rows.

## Alternatives considered

- **Rename `pending` → `placed` in the enum**: rejected — the existing
  dashboard tests and service code depend on the value; no DB benefit.
- **Retention timer off `delivered_at` only**: rejected — excludes
  cancelled orders from ever being purged, growing the table
  indefinitely.
- **`fulfillment_mode` enum column on orders**: rejected — redundant
  with existing delivery/driver_assignment rows.
