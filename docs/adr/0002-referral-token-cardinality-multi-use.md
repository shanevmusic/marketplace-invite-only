# 2. Referral token cardinality — multi-use per seller

- Status: accepted
- Date: 2026-04-18
- Phase: 1 (Orchestrator resolution of PRD §9.1)

## Context

`PROJECT.md` requires each seller to have a "unique, randomly generated invite link," but does not specify whether the link is single-use or multi-use. This affects UX, schema, and admin controls.

## Decision

Each seller has **exactly one active multi-use referral token**, stored in `invite_links` with `issuer_id = seller_id`, `max_uses = NULL` (unlimited) and an optional `expires_at`. Sellers may regenerate their token (invalidating the old one). Admins can revoke any token. Every signup through a token writes a `referrals` row capturing the edge (`referrer_id`, `referred_user_id`, `invite_link_id`, `created_at`) so the referral graph is always precise, even when the token itself is long-lived.

Admin-issued invites remain **single-use, short-TTL, role-targeted** (defaults: 7-day TTL, one signup).

## Consequences

- Sellers share a single URL on their channels; low-friction recruiting.
- Referral graph fidelity is preserved via per-signup `referrals` rows rather than per-token rows.
- Abuse handling is explicit: admin revocation + seller regeneration.
- Schema: `invite_links.max_uses` nullable; `used_count` incremented on each signup; `revoked_at` nullable.

## Alternatives considered

- **Single-use per signup:** cleaner audit, but forces sellers to generate/share a new link every time — poor UX.
- **Single-use per click via signed short-lived sub-tokens:** over-engineered for v1.
