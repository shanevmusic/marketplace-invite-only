# 5. Single platform-level currency for v1

- Status: accepted
- Date: 2026-04-18
- Phase: 1 (Orchestrator resolution of PRD §9.4 and api-contract Q-C5)

## Context

Multi-currency would complicate analytics (`order_analytics_snapshots.lifetime_revenue` aggregation), seller dashboards, and checkout UI. v1 is city-scoped; assuming one country and one currency is acceptable.

## Decision

Currency is a single platform-level setting stored in `platform_settings.currency_code` (ISO 4217, e.g. `USD`). All monetary amounts in `orders`, `products`, `order_analytics_snapshots` are in this currency. The DB schema stores `amount_minor` as `bigint` (smallest unit, e.g. cents) to avoid floating-point drift; currency_code is implicit via platform settings, not per-row.

Multi-currency is explicitly **out of scope** through Phase 13. Reintroducing it will require (a) per-store currency, (b) FX conversion policy, (c) analytics currency normalization — all new ADRs.

## Consequences

- Simple analytics aggregation.
- Admin can change platform currency, but doing so after orders exist is forbidden at the service layer (the setting becomes immutable once any `order_analytics_snapshots` row exists).

## Alternatives considered

- **Per-seller currency:** deferred.
- **Per-order currency capture:** would prepare for the above but adds storage cost without a use case in v1; rejected.
