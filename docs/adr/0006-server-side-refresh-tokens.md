# 6. Server-side hashed refresh tokens

- Status: accepted
- Date: 2026-04-18
- Phase: 1 (Orchestrator resolution of architecture Q-A1)

## Context

Refresh tokens can be pure JWTs (stateless, cannot be revoked individually until expiry) or server-side records (stateful, revocable per device). PROJECT.md §5.6 requires per-device revocation capability.

## Decision

Refresh tokens are long random opaque strings (not JWTs). A SHA-256 hash is stored in a `refresh_tokens` table with `user_id`, `device_label`, `issued_at`, `last_used_at`, `revoked_at`, `expires_at`. Access tokens remain short-lived JWTs (15 min). Logout, admin ban, and "sign out all devices" actions delete or revoke the corresponding `refresh_tokens` rows.

## Consequences

- Per-device session listing and individual revocation are possible.
- One DB lookup per refresh; mitigated by an index on the hash.
- Admin-initiated bans take effect on the next refresh (≤15 min).

## Alternatives considered

- **Stateless JWT refresh:** rejected — violates the per-device revocation requirement.
- **Redis-only store:** viable, but Postgres keeps device history durable and auditable; Redis is optional as a cache.
