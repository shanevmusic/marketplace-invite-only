# Phase 7 — Delivery tracking with asymmetric visibility

Phase 7 adds a live delivery-tracking channel with a hard privacy
invariant: customers never see the driver/seller's coordinates. ADR-0014
describes the design rationale; this note is the operational reference.

## Scope

- Live location updates while a delivery is `out_for_delivery`.
- Role-appropriate read API: customer sees status/ETA/own address;
  driver/seller/admin sees coordinates + metrics.
- WebSocket broadcasting for real-time UI.
- Analytics snapshot persistence of `delivery_duration_seconds` and
  `delivery_distance_meters` at order completion.

Out of scope for Phase 7:
- Geospatial indexing, ETA computation (driver app supplies ETA).
- Historical breadcrumb retention — only the latest breadcrumb is stored.
- Multi-driver or handoff flows.

## Data model

Migration `0004_phase7_delivery_tracking` adds:

```sql
ALTER TABLE deliveries
  ADD COLUMN current_eta_seconds     INT          NULL,
  ADD COLUMN current_eta_updated_at  TIMESTAMPTZ  NULL;

ALTER TABLE order_analytics_snapshots
  ADD COLUMN delivery_duration_seconds INT NULL,
  ADD COLUMN delivery_distance_meters  INT NULL;
```

`deliveries.current_lat` / `current_lng` / `last_location_at` already
existed from Phase 5.

All four new columns are nullable. Snapshots for orders that never
reached OFD (e.g. cancelled during `preparing`) keep the metric fields
as `NULL`.

## HTTP API

### `POST /deliveries/{order_id}/location` — driver/seller

Body:
```json
{ "lat": 40.71, "lng": -74.00, "eta_seconds": 420, "distance_meters": 15 }
```

- `lat` required, `lng` required, both floats, validated `-90..90` and
  `-180..180`.
- `eta_seconds` optional, non-negative int. When set, the server also
  stores `current_eta_updated_at = now()`.
- `distance_meters` optional; if set, the server accumulates a running
  max into `deliveries.distance_meters` (MVP heuristic — real distance
  tracking requires geospatial math, deferred).

Authorization:
- Caller must be the assigned `driver_id`, the `seller_id` (self-deliver
  mode), or admin.
- Order must be in `out_for_delivery`. Pre-OFD or post-`delivered`/
  `completed` returns `409 DELIVERY_NOT_ACTIVE`.
- Customers → `403 FORBIDDEN` (role mismatch).
- Strangers → `404 NOT_FOUND` (no info leak).

Rate limit: 600/minute per IP (accommodates driver apps polling GPS at 1
Hz with headroom).

Response: `204 No Content`. Side effects:
- Broadcasts `delivery.location` to internal WS subscribers.
- If `eta_seconds` is set, broadcasts `delivery.eta` to both buckets.

### `GET /deliveries/{order_id}/track` — role-appropriate

Response type depends on the caller's role:

- **Internal (driver/seller/admin)** — `InternalDeliveryView`:
  ```
  order_id, driver_id?, seller_id, status,
  last_known_lat?, last_known_lng?, last_known_at?,
  eta_seconds?, eta_updated_at?,
  distance_meters?, duration_seconds?,
  started_at?, delivered_at?, delivery_address
  ```
- **Customer** — `CustomerDeliveryView`:
  ```
  order_id, status,
  eta_seconds?, eta_updated_at?,
  started_at?, delivered_at?,
  delivery_address
  ```

  No coordinate, driver_id, or metric fields. Pydantic
  `extra="forbid"` rejects an accidental addition at model construction.

Non-participants get `404`.

### `PATCH /admin/deliveries/{order_id}` — admin only

Body:
```json
{
  "driver_id": "uuid-or-null",
  "distance_meters": 12345,
  "duration_seconds": 1800
}
```

All fields optional. Admin can reassign driver, override the metric
fields, and the changes are reflected in the next snapshot. Returns an
`InternalDeliveryView`. Admin is determined by `role = "admin"` claim.

## WebSocket protocol

Connect: `GET /ws?token=<jwt>` (same handshake as Phase 6).

### Subscribe to delivery

Client → server:
```json
{ "type": "subscribe", "delivery_order_id": "<uuid>" }
```

Server → client (success):
```json
{ "type": "delivery.subscribed", "order_id": "<uuid>" }
```

On auth failure: close 4401. On non-participant: close 4403. The same
`resolve_role` function that gates REST drives the WS subscribe — there
is no divergence.

Subscriber is placed in the `internal` or `customer` bucket based on
role. Bucket membership is the only thing that determines which events
the socket receives.

### Event types

| Event               | Fields                                                        | Bucket              |
|---------------------|---------------------------------------------------------------|---------------------|
| `delivery.location` | `order_id, lat, lng, at`                                      | internal only       |
| `delivery.eta`      | `order_id, eta_seconds, eta_updated_at`                       | internal + customer |
| `delivery.status`   | `order_id, status, started_at?, delivered_at?`                | internal + customer |

`delivery.status` is emitted when the order transitions into
`out_for_delivery` (carries `started_at`) and into `delivered` (carries
`delivered_at`). Broadcast from the REST handler after the service call
commits.

## Event flow — happy path

1. Seller or driver POSTs `/deliveries/{id}/location` with lat/lng.
2. Service validates role + OFD status, updates `deliveries` row.
3. Router calls `broadcast_delivery_location_internal` (internal bucket
   only) and, if ETA changed, `broadcast_delivery_event_all`.
4. Subscribed driver/seller/admin sockets receive `delivery.location`.
   All subscribed sockets (including customer) receive `delivery.eta`.
5. On `POST /orders/{id}/delivered`, router emits `delivery.status =
   delivered`. On `complete_order`, the retention/analytics snapshot
   captures `delivery_duration_seconds` and `delivery_distance_meters`
   from the now-finalized delivery row.

## Privacy invariant — how we test it

`tests/test_phase7_delivery_tracking.py` (17 tests) covers:

- **Schema-level** — `CustomerDeliveryView.model_fields` must exactly
  equal the safe set; sending an `extra` `lat` into a customer event
  model raises a ValidationError (`extra="forbid"` is load-bearing).
- **REST-level** — adversarial sentinel test posts coordinates
  `12.3456 / -98.7654` as the seller, then fetches `/track` as the
  customer; the raw response body (as text) must not contain
  `last_known`, `current_lat`, `current_lng`, `driver_id`, or any of
  the sentinel digits.
- **OFD gating** — POST before OFD → 409; after delivered → 409;
  customer POST → 403; stranger GET → 404.
- **Metrics persistence** — `complete_order` writes
  `delivery_duration_seconds` and `delivery_distance_meters` into the
  snapshot; admin PATCH overrides are reflected there.
- **WS-level** — customer subscribed to an order receives 0
  `delivery.location` events and N `delivery.eta` events after N
  location POSTs; every event the customer receives validates against
  the strict customer schema.
- **Isolation** — a stranger cannot subscribe (4403). A user who is
  customer-of-A and driver-of-B, subscribed to A, does not receive any
  order-B events.

All 194 backend tests pass (177 pre-existing + 17 new).

## Operational notes

- The WS gateway uses module-scoped `AsyncSessionFactory` connections.
  Test fixtures (both Phase 6 and Phase 7) use `scope="module"`
  `TestClient`; Phase 7's fixture disposes the async engine on teardown
  to prevent asyncpg connections from leaking across event loops.
- The rate limit on `POST /deliveries/{order_id}/location` (600/min) is
  high because a driver app will stream GPS at ~1 Hz; tune down in
  production if a client is observed exceeding it.
- Distance accumulation is deliberately the simple "max of running
  totals" — real vector-sum distance needs a geospatial engine; Phase
  12 or later.
