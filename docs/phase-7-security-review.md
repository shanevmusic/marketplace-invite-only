# Phase 7 — Delivery Tracking Security Review

- Reviewer: Security Engineer (adversarial code audit)
- Commit audited: `1f5f2db` on `main`
- Date: 2026-04-18
- Scope: Phase 7 delivery tracking (asymmetric visibility invariant)

## Verdict: **CONDITIONAL PASS**

The core hard invariant — *a customer never receives driver/seller coordinates
via any channel* — holds under every code path audited. The two-type
schema separation plus the role-partitioned WS registry make the invariant
structurally enforced, not merely policy-enforced.

Two real (non-critical) issues were found that should be addressed before
Phase 8 integrations rely on this surface:

1. **Med-severity** — Stale internal subscription survives driver
   reassignment (previous driver keeps receiving live coordinates after
   being replaced by admin PATCH).
2. **Low/Med** — `@limiter.limit("600/minute")` keys on remote IP, not
   user, on `POST /deliveries/{id}/location`. One NAT'd fleet can burn
   the budget for all drivers behind it.

Everything else is PASS or info-level.

---

## 1. Serializer escape — PASS

**What I checked.** `build_customer_view` at
`backend/app/services/delivery_tracking_service.py:141-165`; the
`CustomerDeliveryView` / `CustomerDeliveryEtaEvent` /
`CustomerDeliveryStatusEvent` / `CustomerDeliverySubscribedEvent`
schemas at `backend/app/schemas/delivery_tracking.py:75-123`; and every
call site for `.model_dump()` / `.dict()` / dict-update in the delivery
paths.

**Findings.**

- `CustomerDeliveryView`, `CustomerDeliveryEtaEvent`,
  `CustomerDeliveryStatusEvent`, `CustomerDeliverySubscribedEvent` all
  set `model_config = ConfigDict(extra="forbid")`
  (`schemas/delivery_tracking.py:83, 100, 109, 119`). A stray `lat`/`lng`
  passed into any of these at construction raises
  `pydantic.ValidationError`.
- `build_customer_view` constructs the pydantic object field-by-field
  from `order` + optional `delivery`. No `**kwargs` spread, no
  `model_copy`, no `.dict()`, no reflection. The function *reads* only
  the coord-less fields (`current_eta_seconds`, `current_eta_updated_at`,
  `started_at`, `delivered_at`, `delivery_address`). A future dev who
  adds a `delivery.current_lat` reference here would still fail to leak,
  because they would have to also add a field to `CustomerDeliveryView`
  (Pydantic would reject the kwarg otherwise).
- No `.dict()` or `.model_dump()` on the raw `Delivery` ORM model is
  called on any customer-facing path. The only dump surface is FastAPI's
  response serialization, which runs against the declared `response_model`
  (`InternalDeliveryView | CustomerDeliveryView`). `get_track_view`
  returns the role-appropriate type; there is no branch that returns an
  internal view to a customer.
- `CustomerDeliveryView.delivery_address` is populated from
  `order.delivery_address`, which is the customer's **own** address
  (from `POST /orders` at creation time). This is the customer's data
  being shown back to them; even when the customer submitted their own
  destination lat/lng, that is self-disclosed — it is not driver/seller
  location.

**Severity: none.**

**Recommended action.** Keep the existing assertion tests; add the
defense-in-depth tests in §9.

---

## 2. WS dispatch escape — PASS (with a minor note)

**What I checked.** `backend/app/ws/gateway.py:74-294` end-to-end:
subscriber registry structure, both broadcasters, subscribe validation,
typing / heartbeat / ping handlers, `disconnect_all`, and close-reason
strings.

**Findings.**

- The subscriber registry is partitioned by role (`"internal"` /
  `"customer"`) at the bucket level (`gateway.py:99-101`). A customer
  is never in the `"internal"` set.
- `broadcast_delivery_location_internal` (`gateway.py:255-269`) reads
  `delivery_internal_subscribers(order_id)` only. There is no code path
  in that function that can reach the customer bucket — even if the
  payload contains coords, the *destination* iterator cannot return a
  customer socket.
- `broadcast_delivery_event_all` (`gateway.py:272-293`) reads both
  buckets but is used only for `eta_event` / `status_event`, which are
  constructed via `dts.eta_event(delivery)` and `dts.status_event(...)`
  (`delivery_tracking_service.py:302-331`). Neither includes lat/lng.
- Typing events (`gateway.py:469-496`) are strictly scoped to a
  `conversation_id` topic (the conversation subscriber set), a different
  dict from `_delivery_subs`. There is no path where typing could carry
  a coord payload into the delivery topic.
- Heartbeat (`_heartbeat`, `gateway.py:520-529`) only sends
  `{"type":"ping"}`. No coord surface.
- The `delivery.subscribed` ack (`gateway.py:426-429`) is a two-field
  dict: `type`, `order_id`. It is explicitly modelled by
  `CustomerDeliverySubscribedEvent`. No coord surface.
- **Close-reason strings**: closes use `CLOSE_AUTH = 4401` and
  `CLOSE_FORBIDDEN = 4403` as numeric codes, with no `reason` string
  passed. Starlette's `WebSocket.close(code=...)` accepts a `reason`
  kwarg but the code does not supply one. No data leak via close frame.

**Race / role-bypass check.** `_resolve_delivery_role` at
`gateway.py:351-370` opens a fresh `AsyncSessionFactory()` session. A
customer tries to subscribe to `delivery:{order_B}` where they are not
the customer: `load_order` finds the order, `resolve_role` matches none
of the role branches (`order.customer_id != user.id`), returns
`"none"`, and the socket gets 4403. Confirmed by
`test_ws_stranger_subscribe_4403` and by the two-delivery isolation test
at `tests/test_phase7_delivery_tracking.py:822-871`.

**Dual-role edge case.** A single `User.role` column
(`models/user.py:45`) — a user has exactly one role. `resolve_role`
gates every branch on `user.role == "seller"` / `"customer"` /
`"driver"` before the ownership check. A user cannot simultaneously be
`customer` and `seller` on the same order. Safe.

**Minor note (info, not a bug).** Invalid `delivery_order_id` at
subscribe (`gateway.py:419`) replies with an error message and keeps
the socket open; invalid `conversation_id` behaves the same
(`gateway.py:439`). But stranger access to a valid order (`role is
None`) calls `ws.close(code=CLOSE_FORBIDDEN)` *and returns from
`handle_ws`*, tearing down all other subscriptions that user had
(messaging, etc.). This is aggressive for the adversary but also
affects legit users who mistype; acceptable for Phase 7, consider
downgrading to a soft error in Phase 12.

**Severity: none.**

---

## 3. REST role bypass — PASS

**What I checked.** `backend/app/api/v1/deliveries.py` (all three
endpoints), query-param handling in FastAPI, and the admin PATCH
response shape.

**Findings.**

- All three endpoints route through `dts.resolve_role(db, user, order)`
  via `get_track_view` / `post_location` / `admin_patch_delivery`. No
  endpoint reads a `?role=`, `?view=`, or header to decide view type.
- `GET /deliveries/{id}/track` is typed `InternalDeliveryView |
  CustomerDeliveryView` (`deliveries.py:77`). FastAPI picks the
  response-model at runtime using the returned object's type. Because
  the service branch returns a *different Pydantic class* for customers,
  even a misconfigured serializer cannot render coords for them.
- `POST /deliveries/{id}/location` (`deliveries.py:42-67`) calls
  `dts.post_location`, which raises `AuthorizationError` with code
  `PERMISSION_DENIED` for customers (service line 216-219). A customer
  gets 403 before the body is touched.
- `admin_patch` requires `get_current_admin` dependency
  (`deliveries.py:102`) **and** the service re-checks `caller.role ==
  "admin"` (service line 256-257). Defense-in-depth.
- **422 echo of user-submitted lat/lng.** FastAPI's
  `RequestValidationError.errors()` includes an `input` field. The
  exception handler at `app/main.py:146-183` sanitizes `ctx` but
  preserves `input`. If a **driver/seller** submits a malformed lat/lng
  (e.g. `lat: 999`), the 422 response echoes `"input": 999` — but this
  is the caller's *own* submission and they never reach the DB, so no
  cross-tenant leak is possible. A customer POSTing to `/location` is
  rejected by the service with 403, not 422, because Pydantic validates
  successfully first; the 422 path can only return the customer their
  own input. **Not a Phase 7 violation** — flagged for completeness.
- **Error envelopes don't echo stored coords.** `OrderNotFound`,
  `OrderInvalidTransition`, `AuthorizationError` raise static messages
  (`exceptions.py`); `AppException` serializer at `main.py:130-144`
  copies `exc.message` / `exc.details`. Nothing in the call path sets
  `details` to a coord-bearing value. The 409 path message in
  `post_location` only includes `order.status`, not coords.

**Severity: none.**

---

## 4. Auth / authz on WS topic — PASS, with a stale-subscription caveat

**What I checked.** Handshake 4401, subscribe 4403, cross-order
isolation, driver reassignment semantics, user-deactivation mid-session.

**Findings.**

- No-token / bad-token → `ws.accept()` then `ws.close(CLOSE_AUTH=4401)`
  (`gateway.py:379-385`). Confirmed by `test_ws_no_token_closes_4401`.
- Non-participant subscribe → 4403. Confirmed by
  `test_ws_stranger_subscribe_4403` and the two-order isolation test.
- The user row is fetched fresh in `_authenticate` (`gateway.py:313-333`)
  and checked for `is_active` / `disabled_at`. After handshake the user
  is cached on the `WSConnection`; if the user is deactivated *during*
  the session, they keep their socket until reconnect. Same behavior as
  Phase 6 messaging; not a Phase 7 regression.

### Finding 4.1 — Stale internal subscription after driver reassignment (Med)

**Where.** `backend/app/services/delivery_tracking_service.py:247-282`
(`admin_patch_delivery`) and the WS registry in `gateway.py:88-187`.

**Problem.** When an admin reassigns a driver:

```python
delivery.driver_id = driver_id  # service line 276
```

No code path forcibly unsubscribes the previous `driver_id`'s open
WebSocket from the `internal` bucket. The previous driver keeps
receiving `delivery.location`, `delivery.eta`, and `delivery.status`
events for that order until they disconnect — even though
`resolve_role` for that user would now return `"none"` (their assignment
status has presumably been flipped to `cancelled` / `reassigned`, or
they were never on the `driver_assignments` table if they were
admin-patched directly onto the delivery row).

The ex-driver therefore continues to see the new driver's live
coordinates.

**Impact.** Internal-to-internal leak, not customer-facing. Still a
real violation of the authorization model: a user whose relationship
to the order has ended retains a live data feed. Labour-law /
privacy-policy issue in delivery platforms.

**Severity.** **Medium** (internal information disclosure; bounded
by "needs to be a driver, needs an open WS, needs the admin to
reassign mid-stream").

**Recommended fix (do not implement per instructions).**

In `admin_patch_delivery`, after the DB mutation, if `driver_id` is
being changed and `delivery.driver_id` had a previous value, look up
the previous driver's connections and evict them from the delivery
topic — or close their socket. A lightweight design:

```python
# service (pseudo):
old_driver_id = delivery.driver_id
...
delivery.driver_id = driver_id
await db.flush()
if old_driver_id and old_driver_id != driver_id:
    await ws_gateway.evict_user_from_delivery_topic(
        order_id, old_driver_id
    )
```

where `evict_user_from_delivery_topic(order_id, user_id)` iterates the
registry's `_delivery_subs[order_id]["internal"]` set and removes
entries whose `conn.user_id == user_id` (and optionally sends a
`delivery.unsubscribed` courtesy event so the client can re-auth). The
same helper should run when `cancel_order` / `mark_delivered` transitions
the delivery out of `in_transit` — though `post_location` is already
gated by `order.status == "out_for_delivery"`, so no *new* coords flow
post-delivered; the delivered event broadcast itself is customer-safe.

A second, complementary hardening is to re-validate
`resolve_role` on each outbound internal event. That is O(n) DB hits
per broadcast which is too expensive; the eviction-on-state-change
design above is preferable.

---

## 5. Metrics leakage — PASS (info on timing)

**What I checked.** Whether `duration_seconds` / `distance_meters` can
reach customers; and whether `delivered_at - started_at` delta is a
useful fingerprint.

**Findings.**

- `CustomerDeliveryView` does **not** include `distance_meters` or
  `duration_seconds` (`schemas/delivery_tracking.py:85-91`). Confirmed
  by `test_customer_view_schema_has_no_coordinate_fields` which
  enumerates the full allowed field set.
- `CustomerDeliveryView` **does** include `started_at` and `delivered_at`
  (service `build_customer_view` line 152-153). The difference is
  roughly the delivery duration — customers can compute it
  post-delivery. This is acceptable: the customer knows when their
  order started and when it arrived; that is core product UX, not a
  side channel.
- `distance_meters` is persisted onto the delivery row
  (`post_location`, service line 241-242) as a monotonic `max`; snapshot
  ingests it on `_write_snapshot` (order_service line 644-653). Not
  exposed to customers anywhere.

**Severity: none / info.** Timing-based fingerprinting of the driver's
path (e.g. inferring route length from duration) is a theoretical
concern; not worth mitigating at this scale.

---

## 6. Rate limiting / DoS — LOW-MED

### Finding 6.1 — `POST /deliveries/{id}/location` limit is per-IP, not per-user (Low-Med)

**Where.** `backend/app/api/v1/deliveries.py:43` with
`@limiter.limit("600/minute")`. The `limiter` singleton uses
`slowapi.util.get_remote_address` as its `key_func`
(`core/rate_limiter.py:25, 32`).

**Problem.**

- Behind any NAT'd network (corporate VPN, mobile carrier CG-NAT, rider
  fleet hotspot), *all* drivers share the same remote IP, so 600/min
  covers the entire NAT pool, not one driver.
- Conversely, a single malicious driver can rotate IPs (residential
  proxies, IPv6 address expansion) to bypass the limit cheaply.
- 600/min is also lenient per-driver: 10 updates/second. Not a coord
  leak, but it inflates DB write volume and the broadcast fan-out cost.

**Impact.**

- **DoS amplifier**: 600 updates/min fan out to every internal
  subscriber (sellers, admins watching fleet dashboards) plus every
  customer subscribed to `delivery.eta`. A hot-spamming driver in a
  10-subscriber order is 6000 msg/min of WS traffic.
- **Budget sharing on NAT**: legitimate drivers on the same NAT lose
  updates under contention.

**Severity.** **Low-Med** — not a hard-invariant breach; operational
resilience and fairness issue.

**Recommended fix (do not implement).**

Switch `key_func` for this specific endpoint to user ID, e.g.:

```python
@router.post("/{order_id}/location", status_code=204)
@limiter.limit("120/minute", key_func=lambda request: str(request.state.user_id))
```

(the `user_id` would need to be set onto `request.state` in the auth
dep). A reasonable rate is 120/min (2/sec) per driver-order pair.
Additionally limit by `(user_id, order_id)` to bound any single
delivery's WS fan-out.

### Finding 6.2 — No WS connection cap per user (Info)

**Where.** `gateway.py:378-511`.

**Problem.** Nothing caps how many simultaneous WebSocket connections
one user can hold, nor how many delivery topics one connection can
subscribe to. A driver could open 1000 sockets; the registry set grows
unbounded per order.

**Severity.** **Info.** Existing Phase 6 pattern — not a Phase 7
regression. Worth a Phase 12 hardening: cap per-user connections (e.g.
5) and per-connection delivery subscriptions (e.g. 20).

---

## 7. Data at rest — PASS

**What I checked.** Grep for `logger.(info|warning|error|debug)` near
all coord-handling code; retention purge behavior for the `deliveries`
row; snapshot's metric retention.

**Findings.**

- No log statement in Phase 7 code writes `current_lat`, `current_lng`,
  `lat`, or `lng`. The only delivery-path log is
  `logger.debug("drop broadcast to dead socket user=%s", conn.user_id)`
  at `gateway.py:214` — coord-free.
- **Purge cascade**: `deliveries.order_id` has `ON DELETE CASCADE`
  (`models/delivery.py:37-47`). When `run_purge_job` hard-deletes an
  order (`order_service.py:918-923`), the `deliveries` row (including
  `current_lat` / `current_lng`) goes with it. Confirmed.
- **Snapshot carries metrics, NOT coords**: `_write_snapshot`
  (`order_service.py:642-669`) copies only `duration_seconds` and
  `distance_meters` from the delivery row into the snapshot, never
  `current_lat` / `current_lng`. The snapshot schema itself has no
  coord columns (`models/order_analytics_snapshot.py:30-98`).

**Severity: none.**

---

## 8. Frozen logic conflicts — PASS

**What I checked.** PROJECT.md §3 (order lifecycle), ADR-0003
(out_for_delivery idempotency), ADR-0011 (seller.id == user.id),
ADR-0012 (state machine + retention).

**Findings.**

- ADR-0003 (OFD is idempotent, first-caller wins): `out_for_delivery`
  in `order_service.py:464-540` short-circuits with
  `DeliveryAlreadyStarted` on re-entry. No Phase 7 regression.
- ADR-0011 (`seller.id == user.id`): `resolve_role` relies on this
  identity at `delivery_tracking_service.py:90` (`order.seller_id ==
  user.id`). Consistent with the model; ADR-0014 (Phase 7 ADR)
  explicitly calls this out.
- ADR-0012 state machine: `post_location` requires
  `order.status == "out_for_delivery"` (service line 220-223), matching
  the "tracking window closed" rule. Transitions `preparing →
  out_for_delivery → delivered → completed` are unchanged; Phase 7 only
  *stamps* `started_at` at OFD and `delivered_at` + computes
  `duration_seconds` at delivered (`order_service.py:533, 575-582`).
- Retention (ADR-0012 D6, ADR-0010): analytics snapshot is written on
  `complete_order` *before* the delivery row is purge-eligible
  (`_write_snapshot` runs inside `complete_order`'s transaction); the
  `delivery_duration_seconds` / `delivery_distance_meters` fields
  preserve the metrics past hard-delete. Matches the ADR.

**Severity: none.**

---

## 9. Suggested defense-in-depth tests

None of these are blockers, but they tighten the net:

1. **422 response sanity** — drive a seller to POST `{"lat": 999,
   "lng": 0}` and assert the 422 response does NOT contain any
   *previously stored* coord for the order. Belt-and-suspenders against
   a future error handler that might include DB state in the validation
   error detail.
2. **Stale driver subscription eviction** — simulate admin reassign of
   a driver while the old driver's WS is subscribed; assert old driver's
   socket stops receiving `delivery.location` events. Will fail today;
   fails closed after Finding 4.1 fix.
3. **Customer WS receives zero events for cancelled orders** — after
   `cancel_order`, broadcasting should stop. Today there is no
   broadcaster firing on cancel (so de-facto passes), but a regression
   test locks that in.
4. **Close-frame fuzz** — send binary, oversized, and non-JSON frames
   and assert the server never echoes coord-bearing state in any close
   reason.
5. **Log-capture assertion** — in CI, attach a `logging` handler to
   `marketplace.*` loggers during a Phase 7 scenario (OFD → 5 location
   posts → delivered) and assert no emitted record contains the string
   of any posted lat/lng.
6. **Per-user rate-limit contract test** — once Finding 6.1 is
   addressed, assert two drivers behind the same IP can both post at
   their full per-user quota.
7. **Retention purge + snapshot preservation** — drive an order to
   completed, age it past `retention_min_days`, run the purge job,
   assert the `deliveries` row is gone AND the snapshot row still
   carries `delivery_duration_seconds` / `delivery_distance_meters`.

---

## Summary of findings

| # | Finding | Severity | File / Line |
|---|---------|----------|-------------|
| 4.1 | Stale internal subscription after driver reassignment | **Med** | `delivery_tracking_service.py:247-282`; `ws/gateway.py:88-187` |
| 6.1 | `/deliveries/{id}/location` rate-limit is per-IP, not per-user | **Low-Med** | `api/v1/deliveries.py:43`; `core/rate_limiter.py:25-35` |
| 6.2 | No per-user WS connection / subscription cap | Info | `ws/gateway.py` (Phase-12 defer) |
| 3.a | 422 validation error echoes caller's own input | Info | `app/main.py:146-183` |

**The hard invariant — customer never obtains driver/seller coordinates
via REST, WS, HTTP headers, validation errors, close frames, or logs —
holds.**

No *customer*-facing leak was found. The Med-severity issue is an
internal-to-internal leak (ex-driver keeps receiving live coords). Fix
it before Phase 8 or before this feature ships to production drivers.
