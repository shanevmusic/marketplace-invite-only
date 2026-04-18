# Post-v1 Backlog

Tracked follow-ups that were explicitly deferred past v1 launch. Each entry
names the trigger ("when do we need this?"), the design sketch, and a
pointer to the code or contract text that defines the behaviour. None of
these block production launch of the invite-only beta.

Status legend: 🟡 scaffolded (API surface exists, wiring incomplete) ·
⚪ not started.

---

## WS fan-out — swap in-memory ConnectionManager for Redis pub/sub

**Trigger:** moment we need to run more than one app instance behind the
load balancer. v1 is single-instance ECS Fargate (desired=1, max=1 via the
autoscaling target), so in-memory is correct and cheapest.

**Design sketch:**
- Keep `ConnectionManager` (`app/ws/connection_manager.py`) as the
  per-instance registry of live sockets.
- On publish, instead of iterating only local sockets, emit to a Redis
  pub/sub channel keyed by `conversation:<id>` or `order:<id>`.
- Each instance subscribes to its own set of channels lazily when a socket
  connects; unsubscribes when the last local listener drops.
- Message envelope stays identical to the on-wire format; no client
  changes needed.
- Redis is already listed in the stack (`PROJECT.md §2`) and the rate
  limiter will share the connection.

**Blast radius if we don't do it:** >1 instance → messages only reach the
subset of clients whose sockets terminated on the same pod. Acceptable for
v1 (single instance); mandatory before horizontal scale-out.

---

## Contract deviations deferred (from `docs/CONTRACT-DEVIATIONS.md`)

### B-G2 — Product image CDN invalidation on delete ⚪

**Contract:** deleting a product invalidates its CDN entries.
**Current:** DB row is soft-marked; no CloudFront / Fastly purge.
**Why deferred:** S3 bucket lifecycle policy cleans orphaned keys on a
7-day window; image URLs are versioned with the product key, so stale
cache hits cannot leak to a different product. Acceptable for invite-only
beta.
**When to revisit:** before opening signup to the public, or when first
user reports seeing a deleted image.

### B-G3 — Avatar cropping pipeline ⚪

**Contract:** server-side crop to square + thumbnail generation.
**Current:** client validates dimensions + aspect ratio before upload.
**Why deferred:** not security-critical; clients won't accept oversized
avatars. Thumbnail quality is "good enough" from the client-side crop.
**When to revisit:** after v1 if ops sees storage bloat from full-res
avatars, or if we want to drive thumbnails from email.

### C-G5 — WebSocket reconnection back-off guidance ⚪

**Contract:** clients SHOULD exponential-back-off reconnects up to 60s.
**Current:** backend enforces 429 on reconnect flood + connection cap;
client just retries every 3 s.
**Why deferred:** this is a client-side recommendation, not a server API.
**When to revisit:** when ops sees thundering-herd on ALB after a WS
gateway restart, implement 1s → 2s → 4s → … 60s jitter in
`ws_client.dart`.

### C-G6 — Per-conversation message retention override ⚪

**Contract:** admin endpoint to override retention for a single
conversation.
**Current:** global `message_retention_days` setting only.
**Why deferred:** no moderation need has surfaced in the beta cohort.
**When to revisit:** first legal / DMCA request that needs a longer hold
on one conversation without extending the global default.

### C-G7 — Push notifications integrated with message send 🟡

**Contract:** `message.new` triggers a push via FCM/APNs.
**Current:** `push_service.send_notification()` + `POST /devices/register`
exist; the messaging service does not yet call it on every send.
**Why deferred:** gated on real FCM/APNs credentials + mobile-release
pipeline (which ships unsigned scaffolds in v1).
**When to revisit:** as soon as first TestFlight / internal-track release
lands with working signing keys.

### C-G8 / C-G9 — Read receipts + typing indicators ⚪

**Contract:** WS message types `read` and `typing` documented in
api-contract.
**Current:** not wired.
**Why deferred:** low signal in the beta cohort; adds WS message-type
complexity.
**When to revisit:** when user feedback flags "I can't tell if they saw
it" as a top-5 request.

---

## Observability enhancements ⚪

- Export custom business metrics (`ws_connections_active`, `orders_placed`,
  `invites_redeemed`) as Prometheus gauges/counters so the CloudWatch
  dashboard can pull them via the OTEL sidecar. v1 dashboard uses infra
  metrics only (ALB, ECS).
- Stand up an error-budget SLO (99.5 % 5xx-free requests over 30 d) and
  page on burn-rate.

## Infra hardening ⚪

- Multi-AZ RDS / Supabase replica for v1.1; current single-AZ is fine
  while we're on Supabase free tier.
- WAF rule set in front of ALB — currently rely on rate-limit +
  SecurityHeadersMiddleware.

---

## Known CVE ignores ⚪

These CVEs are suppressed in CI (`.github/workflows/security.yml` →
`pip-audit --ignore-vuln ...`) because no upstream fix is available and
the exposure is outside our v1 threat model. Re-audit each quarter.

| Package | Version | CVE | Rationale | Exit plan |
| --- | --- | --- | --- | --- |
| `ecdsa` | 0.19.2 | CVE-2024-23342 (Minerva timing side-channel) | No upstream fix. Transitive via `python-jose[cryptography]`. The side-channel is only relevant if an attacker can control the timing of sign operations on attacker-chosen data — we sign JWTs for our own users server-side with fixed secrets, not a threat vector. | v1.1: migrate off `python-jose` to `PyJWT` (which uses `cryptography` directly and does not pull `ecdsa`). Tracked here. |
