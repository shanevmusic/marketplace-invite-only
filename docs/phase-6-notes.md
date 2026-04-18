# Phase 6 — Implementation Notes

## Scope

- E2E-encrypted messaging via per-message ephemeral X25519 ECDH → HKDF-SHA256
  → AES-256-GCM (ADR-0009, ADR-0013).
- Multi-key registry per user with active / rotated / revoked states.
- 1:1 conversations with referral-linked eligibility.
- REST + WebSocket delivery paths.
- Admin-configurable message retention (min 7 days) and on-demand purge.

## Architecture highlights

### Canonical conversation ordering
`Conversation.user_a_id < user_b_id` is enforced by the service (`a, b =
sorted_by_bytes`) and the DB partial unique index
`uq_conversations_user_a_user_b`. Creation is idempotent on the canonical
pair — a re-POST returns 201 with the same conversation id (ADR-0008).

### Key rotation
`POST /keys` locks existing active keys `FOR UPDATE`, marks them `rotated`,
flushes, and inserts the new active row. The partial unique index
`uq_user_public_keys_one_active WHERE status='active'` is the DB-level
guarantee that at most one key is active at any time.

### WebSocket gateway
- Path: `/ws`
- Auth: `?token=<jwt>` or `Authorization: Bearer` at handshake.
- Close codes: `4401` (auth), `4403` (non-participant).
- Client → server: `subscribe` / `unsubscribe` / `typing` / `ping`.
- Server → client: `subscribed` / `message.new` / `message.read` /
  `typing` / `pong` / `ping` (30s heartbeat).
- Fanout is in-process for Phase 6; Redis pub/sub is Phase 12.

### Retention
- `platform_settings.message_retention_days` (default 90, min 7).
- `POST /admin/jobs/purge-messages` deletes all rows where
  `sent_at < now() - interval '<days> days'`.
- The scheduler is wired and opt-in via `APP_ENABLE_SCHEDULER=1`; when
  enabled it runs `purge_old_messages` daily at 03:00 local.

## Gotchas & rationale

### Why per-message ephemeral key (and not ratchets)?
Ratchets (Signal / Double-Ratchet) are the gold standard but need
two-sided state machines and secure key storage on clients. Phase 6's
threat model is "operator read-only access" and we explicitly descope
post-compromise security. Per-message ephemeral ECDH gives forward
secrecy against an attacker who later steals the recipient's long-term
private key, which is the primary property we care about for retained
messages.

### Why 4401 / 4403 rather than 1008?
Close codes ≥ 4000 are application-defined; existing libraries (starlette,
websockets) surface them unchanged. `1008` is "policy violation" but does
not let the client distinguish auth-missing from not-a-participant. Using
4401/4403 mirrors HTTP semantics (the RFC allows 4xxx for exactly this).

### Why `extra='forbid'` on SendMessageRequest?
Any accepted plaintext-looking field (body/text/content/...) is a
foot-gun waiting to happen during future extensions. Pydantic's
`extra='forbid'` makes the 422 response load-bearing as a security
assertion — tested in `test_plaintext_field_rejected_422`.

### Why 404 (not 403) for eligibility failures?
ADR-0007 forbids leaking resource existence. `GET /conversations/{id}`
from a stranger returns 404 whether the id exists or not. Key lookup on a
non-eligible peer returns 404. Sending a message to a conversation the
caller isn't a participant of returns 404. This is uniform.

### Why `@dataclass(eq=False)` on `WSConnection`?
Default `@dataclass` equality on mutable fields makes the instance
unhashable — but we need instances in a `set` for the fanout registry.
`eq=False` + `__hash__ = id(self)` gives identity-equality which is
exactly what we want for connection pooling.

### Why the conftest needs to set env BEFORE import?
`app.main` imports `app.db.session` which reads `settings.database_url`
at module-load time to create the singleton `async_engine`. The WS
handler uses this singleton (not the test's `get_db` override), so the
test DB URL must be in the environment before any `from app.X` import.
Done via a top-of-`conftest.py` `os.environ.setdefault`.

### Why disable the rate limiter in tests?
SlowAPI uses an in-memory counter keyed on IP + route. All tests come from
the same `testserver` host, so the 10/minute login limit gets exhausted by
the time we're on the 30th-ish auth test. Session-autouse fixture disables
it; the one rate-limit test re-enables it locally via `monkeypatch`.

## Library choices

- **WebSocket tests use `fastapi.testclient.TestClient`** (the Starlette
  sync client) rather than `httpx.AsyncClient`. httpx does not natively
  support WebSocket upgrades; Starlette's client handles the ASGI
  handshake in-process.
- **Seeding from `test_websocket.py` uses `psycopg2` directly**, not
  AsyncSessionFactory. Reason: TestClient runs its own anyio portal; any
  asyncpg call from the test body would cross event loops and raise
  "attached to a different loop". The sync psycopg2 path sidesteps this.
- **REST tests continue to use the existing `db` + `client` fixtures**
  (per-test engine + transaction rollback).

## Migration

`0003_phase6_messaging.py` is additive + idempotent under down/up:

- drops `uq_user_public_keys_user_id` (the legacy 1:1 constraint),
- adds `key_version INT NOT NULL DEFAULT 1`, `status text NOT NULL DEFAULT
  'active'` (CHECK in `('active','rotated','revoked')`), `rotated_at`,
  `revoked_at`, `created_at` to `user_public_keys`,
- creates the partial unique index
  `uq_user_public_keys_one_active WHERE status='active'`,
- adds `recipient_key_id UUID` FK on `messages` with `ON DELETE SET NULL`,
- adds `message_retention_days INT NOT NULL DEFAULT 90` with
  `CHECK >= 7` on `platform_settings`.

Verified clean up/down/up on the test DB.

## Phase 12 follow-ups

See `docs/phase-6-security-review.md` §7 — Redis pub/sub, WS subprotocol,
key-pinning UX, message size cap, admin audit trail, required
`recipient_key_id`, test rate-limit strategy.
