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

## Deferred

### B-G2 — Product image CDN invalidation on delete
- **Contract**: Deleting a product invalidates its CDN entries.
- **Deferred to**: Phase 13.  The deletion flow marks the DB row but does
  not issue a CloudFront / Fastly purge.  The lifecycle policy on the S3
  bucket will eventually clean orphaned keys; operational acceptable for
  the invite-only beta.

### B-G3 — Avatar cropping pipeline
- **Contract**: Server-side crop to square + thumbnail.
- **Deferred to**: Phase 13.  Client already validates dimensions; the
  server pipeline isn't a security-critical feature for the beta.

### C-G5 — WebSocket reconnection back-off guidance
- **Contract**: Recommends client exponential back-off up to 60s.
- **Deferred to**: client implementation doc.  Backend behaviour is correct
  (connection cap + 429 on reconnect flood); the back-off is a client
  recommendation, not an API surface.

### C-G6 — Per-conversation message retention override via UI
- **Contract**: Admin endpoint to override retention for a single
  conversation.
- **Deferred to**: Phase 13.  Current global `message_retention_days`
  setting is sufficient for the moderation cases we've seen so far.

### C-G7 — Push notifications integrated with message send
- **Contract**: `message.new` triggers a push.
- **Status**: 🟡 Scaffolded.  `push_service.send_notification()` exists
  and `POST /devices/register` persists tokens, but the messaging service
  does not yet dispatch pushes on every send (deferred to Phase 13 so the
  rollout can be gated on real FCM/APNs creds).

### C-G8 / C-G9 — Read receipts + typing indicators
- **Contract**: Documented in api-contract but not yet wired.
- **Deferred to**: Phase 13.  Requires extra WS message types and client
  UI; low signal in the beta cohort.
