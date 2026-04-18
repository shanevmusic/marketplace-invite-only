# Contract Deviations

Authoritative register of places the implementation intentionally diverges
from `docs/api-contract.md`, including every gap tagged `B-G*` (Phase 9) and
`C-G*` (Phase 10).  Items here are either (1) resolved in Phase 12 with a
pointer to the commit/module, or (2) explicitly deferred with rationale.

## Resolved in Phase 12

### B-G1 — Product image upload flow
- **Contract**: Upload endpoint presigns a PUT and returns a key + CDN URL.
- **Status**: ✅ Implemented. `POST /api/v1/uploads/presign` and
  `POST /api/v1/uploads/confirm` in `backend/app/api/v1/uploads.py`, backed by
  `backend/app/services/upload_service.py`.  Falls back to 503
  `UPLOAD_NOT_CONFIGURED` when creds are absent (dev default).

### C-G1 — Suspended accounts must be rejected at login
- **Contract**: Suspended users cannot obtain new tokens.
- **Status**: ✅ Implemented.  `auth_service.login` raises `AccountSuspended`
  (403 `AUTH_ACCOUNT_SUSPENDED`) before tokens are minted.

### C-G4 — Security headers on every response
- **Contract**: HSTS, CSP, Referrer-Policy, Permissions-Policy,
  X-Content-Type-Options.
- **Status**: ✅ Implemented via `SecurityHeadersMiddleware` in `app.main`.

## Deferred to v1.1 — tracked in `POST-V1-BACKLOG.md`

Each entry below was reviewed in Phase 14 and migrated to
[`POST-V1-BACKLOG.md`](./POST-V1-BACKLOG.md) with a design sketch and
revisit trigger.  None block the invite-only beta launch.

### B-G2 — Product image CDN invalidation on delete
- **Contract**: Deleting a product invalidates its CDN entries.
- **Current**: DB row is marked deleted; no CloudFront / Fastly purge.
- **Why safe for v1**: S3 lifecycle policy expires orphaned keys on a
  7-day window; image keys are product-versioned so stale cache hits
  can't leak to a different product.
- **Tracked**: POST-V1-BACKLOG.md § B-G2.

### B-G3 — Avatar cropping pipeline
- **Contract**: Server-side crop to square + thumbnail.
- **Current**: Client validates dimensions and crops before upload.
- **Why safe for v1**: not security-critical; acceptable thumbnail
  quality from the client crop.
- **Tracked**: POST-V1-BACKLOG.md § B-G3.

### C-G5 — WebSocket reconnection back-off guidance
- **Contract**: Client SHOULD exponential back-off reconnects up to 60s.
- **Current**: backend enforces connection cap + 429 on flood; client
  retries every 3 s.
- **Why safe for v1**: server-side guardrails are in place; back-off is
  a client recommendation, not an API surface.
- **Tracked**: POST-V1-BACKLOG.md § C-G5.

### C-G6 — Per-conversation message retention override
- **Contract**: Admin endpoint to override retention for a single
  conversation.
- **Current**: global `message_retention_days` setting only.
- **Why safe for v1**: no moderation request has surfaced in the beta
  cohort; will build when first legal/DMCA case requires it.
- **Tracked**: POST-V1-BACKLOG.md § C-G6.

### C-G7 — Push notifications on message send 🟡
- **Contract**: `message.new` triggers FCM/APNs push.
- **Current**: `push_service.send_notification()` + `POST /devices/register`
  scaffolded; messaging service does not dispatch pushes on every send.
- **Why safe for v1**: gated on real FCM/APNs creds which land with the
  mobile-release pipeline.
- **Tracked**: POST-V1-BACKLOG.md § C-G7.

### C-G8 / C-G9 — Read receipts + typing indicators
- **Contract**: WS message types documented in api-contract.
- **Current**: not wired.
- **Why safe for v1**: low signal in the beta cohort.
- **Tracked**: POST-V1-BACKLOG.md § C-G8 / C-G9.
