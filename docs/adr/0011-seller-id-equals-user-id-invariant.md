# 11. Seller.id == User.id — shared-primary-key invariant

- Status: accepted
- Date: 2026-04-18
- Phase: 5 (pre-implementation cleanup of the Phase 4 follow-up)

## Context

Phase 2 shipped the `sellers` table with:

- `sellers.id` as `PRIMARY KEY` — no foreign-key constraint.
- `sellers.user_id` as `UUID NOT NULL UNIQUE` with FK → `users.id`.
- Model docstring: *"``id`` is the same UUID as ``users.id`` (shared PK pattern)."*

Phase 3's `auth_service.signup` silently relied on this invariant — it
set `users.referring_seller_id = invite_link.issuer_id` (where
`issuer_id` is a `users.id`) to satisfy customer visibility rules that
compare against `sellers.id`. That only works because the two UUIDs are
the same.

Phase 4 codified the comparison pattern (`product.seller_id ==
caller_seller.id`, `caller.referring_seller_id == product.seller_id`)
and flagged the invariant as undocumented. Phase 5 introduces drivers,
orders and deliveries that also assume the equality, so continuing to
leave it implicit is a growing footgun.

We considered two options:

- **A.** Treat `sellers.id` as explicitly equal to `users.id` and add a
  FK from `sellers.id` → `users.id`, keeping `user_id` for ORM
  convenience.
- **B.** Treat them as distinct. Rewrite `auth_service.signup` to look
  up `sellers.id` from the issuer's `user_id`, and update every
  downstream path accordingly.

Option B was rejected: it contradicts Phase 2's stated design intent,
adds an extra lookup to every signup that consumes a seller referral,
and would create a new class of bug where the referring-seller-id
points at a user that has not yet had its seller row created (there is
no such race in Option A because the ids are equal by construction).

## Decision

**`sellers.id == users.id` is an invariant.** Every seller row is
created with the same UUID as its user row. The ORM enforces this via
the explicit `Seller(id=user.id, user_id=user.id, ...)` construction in
all current creation paths (tests and future seller-signup flows).

We do NOT add a database-level FK from `sellers.id` → `users.id`
because the circular dependency between `users` and `sellers`
(cyclic FK problem already documented in `docs/schema.md`) makes a
proper FK set awkward. Instead:

1. The invariant is documented in `docs/schema.md` §Cyclic FK and in
   the `Seller` model docstring.
2. A runtime assertion lives in the sole creation path —
   `auth_service.signup` — which already has access to both ids.
3. Phase 5 test fixtures already honour the invariant
   (`seed_seller_with_profile` sets `Seller.id = user.id`).

Similarly, `drivers` is not a distinct table in Phase 2 — drivers are
`users` with `role = 'driver'`. Delivery rows point at `users.id`
directly via `deliveries.driver_id`. No parallel cleanup is needed
for drivers.

## Consequences

- `sellers.id` may continue to be compared directly against
  `users.referring_seller_id` and `users.id` (where the caller is a
  seller) throughout the codebase.
- Any new seller-creation path (admin impersonation, self-signup
  flows in future phases) MUST set `sellers.id = users.id` explicitly.
  A comment to that effect is added to `Seller.__init__` via its
  model docstring.
- If we later want DB-level enforcement, we can add a deferrable FK
  once the cyclic-FK problem is resolved (not this phase).

## Alternatives considered

- **Full refactor to separate ids (Option B):** rejected as above.
- **Add a trigger asserting `sellers.id IN (SELECT id FROM users)`:**
  rejected — triggers hide the invariant from code readers and add no
  value over the constructor assertion.
