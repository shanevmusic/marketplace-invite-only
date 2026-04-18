# 14. Phase 7 delivery tracking — asymmetric visibility

- Status: accepted
- Date: 2026-04-18
- Phase: 7 (Backend Engineer E)

## Context

Phase 5 established the order state machine and the `deliveries` row that
holds `current_lat` / `current_lng` breadcrumbs. Phase 7 must expose this
data to the three parties involved in a delivery while upholding a hard
privacy invariant:

> A customer MUST NOT, under any payload, endpoint, WebSocket event, or
> error response, receive the driver/seller's live coordinates.

Customers may only see the information they already possess (their own
delivery address) plus the delivery status and ETA. Drivers, sellers, and
admins may see the full breadcrumb stream.

Two naive approaches both fail:

1. **"Single view, filter in code."** A single `DeliveryView` schema with
   conditional field population ("customers get `None` for `lat`/`lng`"):
   one forgotten `if user.role == "customer"` anywhere — in the REST
   handler, the WS broadcaster, an error envelope, an admin tool later
   repurposed for customer-facing use — leaks coordinates. The Pydantic
   schema itself carries the coordinate fields; a JSON serializer that
   walks the dict cannot see why a field is populated for one request and
   not another.
2. **"One event, two subscriber lists."** A single `delivery.location`
   event broadcast to one WS topic, with per-subscriber filtering in the
   fanout loop: same hazard, plus a correctness footgun for every future
   event type someone adds.

## Decision

### 1. Two distinct Pydantic TYPES, not one filtered view

`app/schemas/delivery_tracking.py` defines two schemas with
`ConfigDict(extra="forbid")`:

- `InternalDeliveryView` — driver / seller / admin — includes
  `last_known_lat`, `last_known_lng`, `driver_id`, `distance_meters`,
  `duration_seconds`.
- `CustomerDeliveryView` — customer only — fields are
  `{order_id, status, eta_seconds, eta_updated_at, started_at,
  delivered_at, delivery_address}`. There is no code path in the
  codebase that can set a `lat` or `lng` on this type; Pydantic's
  `extra="forbid"` rejects the attempt at model construction.

The `GET /deliveries/{order_id}/track` endpoint is typed as
`InternalDeliveryView | CustomerDeliveryView`. The service picks the
right type based on `resolve_role(user, order)` — there is no branch
that populates a coordinate into the customer type.

### 2. Role-partitioned WebSocket subscriber registry

The gateway stores delivery subscribers as:

```python
_delivery_subs: dict[uuid.UUID, dict[DeliveryRole, set[WSConnection]]]
#                                  └── "internal" or "customer"
```

A `customer`-role subscriber is placed in the `customer` bucket; driver /
seller / admin go in `internal`. Two dispatchers exist:

- `broadcast_delivery_location_internal(order_id, event)` reads the
  `internal` bucket only. It has **no code path** that reaches a customer
  socket. Even if a dev accidentally calls it for every event type, the
  structural separation prevents customer leakage.
- `broadcast_delivery_event_all(order_id, event)` reads both buckets. It
  is used for the two customer-safe event types (`delivery.eta`,
  `delivery.status`). Schema validation at the call site ensures the
  event payload carries no coordinates.

Event types:

| Type                 | Coordinates | Bucket                    |
|----------------------|-------------|---------------------------|
| `delivery.location`  | yes         | internal only             |
| `delivery.eta`       | no          | internal + customer       |
| `delivery.status`    | no          | internal + customer       |

### 3. Role resolution is shared between REST and WS

Both `POST /deliveries/.../location` and the WS `subscribe` handler funnel
through `delivery_tracking_service.resolve_role`, returning
`"customer" | "seller" | "driver" | "admin" | "none"`. The WS layer then
maps `customer` → `"customer"` bucket; everything else → `"internal"`;
`"none"` closes the socket with 4403. REST returns the matching 403.
Same invariant, one place to change.

### 4. Location POST is gated by order state

`POST /deliveries/{order_id}/location` accepts writes only when the order
status is `out_for_delivery`. Before OFD it returns `409
DELIVERY_NOT_ACTIVE`; after `delivered` / `completed` it returns the same
409. This prevents stale breadcrumbs masquerading as live position once
the delivery has ended.

### 5. Analytics persistence

`order_analytics_snapshots` is extended (migration 0004) with nullable
`delivery_duration_seconds` and `delivery_distance_meters`. The snapshot
is written on `complete_order` and by the retention purge sweep; both
read the still-live `deliveries` row for metrics and store the
aggregates before the delivery row is eligible for purge. The fields are
nullable so snapshots from orders that never transitioned through OFD
(e.g. cancelled during preparing) remain valid.

## Consequences

Positive:

- No customer-leak bug can be introduced by a single code change. A dev
  who wants to leak coordinates must both add a field to
  `CustomerDeliveryView` (disabling `extra="forbid"` locally or adding
  the field explicitly) *and* call an internal broadcaster from a
  customer context. Two independent mistakes, not one.
- REST and WS share one role resolver. No "403 on HTTP / accepted on WS"
  divergence is possible.
- Every test asserting the invariant can be written against a strict
  Pydantic type: extra fields fail validation, not just assertions.

Negative / trade-offs:

- Two schemas means two places to update when the customer-safe fields
  change. This is intentional: every addition is forced to cross a type
  boundary and face review of "should the customer see this?".
- `broadcast_delivery_event_all` is misleadingly named if customers are
  later filtered out of a specific event. The convention is: add a third
  broadcaster rather than add an `exclude_customer=True` flag — flags
  are exactly the filtering pattern this ADR is rejecting.
- Dual broadcast on every OFD location POST adds ~1 map lookup + 2 set
  iterations over subscribers. Still O(#subscribers) and in-process;
  fine at single-node scale. Phase 12 Redis pubsub will keep the same
  two-channel design (`delivery.<order>.internal` vs
  `delivery.<order>.customer`).

## Alternatives considered

- **Gateway-layer HTTP response filter.** Strip `lat`/`lng` from any
  response to a customer. Rejected: response transformation is too far
  from the schema; new endpoints are trivial to add without remembering
  the filter; admin tools served from the same base URL could bypass.
- **Separate microservice for driver/seller view.** Overkill at this
  scale and creates its own auth surface; service boundary does not add
  any safety that the two-type approach doesn't already provide
  in-process.

## Compliance with prior ADRs

- ADR-0008 (two-participant conversations): unaffected.
- ADR-0011 (seller.id == user.id): `resolve_role` uses `order.seller_id
  == user.id` directly, relying on this invariant.
- ADR-0012 (order state machine + retention): the analytics snapshot
  extension respects the retention contract — metrics persist to the
  snapshot before the delivery row is eligible for purge.
