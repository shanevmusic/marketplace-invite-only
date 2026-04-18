# 3. `out_for_delivery` trigger — driver or seller (driver path); seller only (self-delivery)

- Status: accepted
- Date: 2026-04-18
- Phase: 1 (Orchestrator resolution of PRD §9.2)

## Context

Tracking begins on the `preparing → out_for_delivery` transition. In the self-delivery path only the seller is present. In the driver-assigned path, the driver typically picks up from the seller and then departs; requiring the seller to tap the button creates a coordination dependency and risks tracking starting late.

## Decision

Transition to `out_for_delivery` may be triggered by:

- **Self-delivery path:** seller only (the seller IS the delivery actor).
- **Driver-assigned path:** the assigned driver OR the seller. Either party may trigger. The action is idempotent; the first caller wins and subsequent callers receive `409 CONFLICT` with the existing `out_for_delivery_at` timestamp.

The state machine enforcement must check both ownership (`order.seller_id = auth_user.id`) and assignment (`deliveries.driver_id = auth_user.id`) as valid transition authorities for this specific step.

## Consequences

- Tracking can start as soon as the driver has the goods, independent of seller action.
- Reduces operational friction in the driver path.
- `deliveries` row must be created lazily or pre-created at `request_driver` time so `driver_id` is set before the transition call.

## Alternatives considered

- **Seller only:** creates coordination dependency; rejected.
- **Driver only (driver path):** breaks the self-delivery fallback where a driver fails to appear; rejected.
