# 7. Referral chain depth = 1 (direct referral only)

- Status: accepted
- Date: 2026-04-18
- Phase: 1 (Orchestrator resolution of architecture Q-A2)

## Context

PROJECT.md says customers see products from "sellers they are linked to via invite/referral." Depth is unspecified. Multi-hop visibility would require recursive CTEs or a closure table and materially complicates query design.

## Decision

Product visibility for customers is restricted to the **direct referring seller only** (depth = 1). If a customer was invited by seller A, they can browse only seller A's products. Admin-invited customers see a configurable default set (TBD in Phase 11 — admin may grant access to additional sellers manually).

## Consequences

- Query path is trivial: `products WHERE seller_id = customer.referring_seller_id`.
- Schema stays flat — no closure table, no recursive CTE.
- Expanding to multi-hop later is backwards-compatible (new endpoint surface, same schema).

## Alternatives considered

- **Multi-hop (N-degree) visibility:** deferred; not justified by current requirements.
- **Global visibility after onboarding:** contradicts the invite-only trust model.
