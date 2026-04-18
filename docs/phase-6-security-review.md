# Phase 6 Security Review — Messaging & WebSockets

**Reviewer:** Security Engineer persona
**Date:** 2026-04-18
**Scope:** All Phase-6 code: ADR-0013, models, schemas, services, REST routers,
WebSocket gateway, admin retention + purge, key rotation endpoints.
**Verdict:** **PASS** — the server-sees-only-ciphertext invariant holds in
code, in static audit, in unit tests, and in live DB scans. Findings below
are hardening follow-ups for Phase 12, not release blockers.

---

## 1. Threat model summary

An adversary who achieves any of the following should NOT be able to read
plaintext message content:

1. Full read access to every row in every table (DB dump, read replica leak,
   debug log, Stripe-webhook-like error envelope spill).
2. A curious or malicious operator running ad-hoc SQL.
3. An operator inspecting application logs or stdout.
4. A referrer/Slack/pastebin receiving an error payload from the API.

For all four, ciphertext, nonce, and ephemeral public key are all that the
server sees; plaintext is exchanged only between the two clients. Messages
can still be *deleted* by the server operator (admin retention policy), and
metadata (sender, recipient, conversation, timestamps, ciphertext length)
remains visible — these are acknowledged and documented in ADR-0013.

---

## 2. Invariants verified

| # | Invariant | How verified |
|---|-----------|--------------|
| I1 | Message send schema forbids `body`/`text`/`plaintext`/`content`/`message`/`subject` fields | `SendMessageRequest` uses `extra='forbid'`; `test_plaintext_field_rejected_422` posts each name and asserts 422 |
| I2 | `messaging_service.py` never calls any symmetric or asymmetric crypto primitive on message data | Static audit in `test_messaging_service_has_no_crypto_primitives`: greps for `AESGCM`, `X25519`, `HKDF`, `decrypt`, `Decrypt`, `cryptography.hazmat` |
| I3 | No persisted row contains plaintext substrings of a real encrypted message | `test_server_sees_only_ciphertext` inserts `"Hello Bob"`, encrypts client-side, POSTs, then does `SELECT row_to_json(t)::text` across `messages`, `conversations`, `user_public_keys` and asserts `Hello`/`Bob`/full plaintext bytes absent. Confirmed live via `/tmp/probe.py` DB scan on the dev DB. |
| I4 | Ciphertext round-trips: client B decrypts what client A encrypted | `test_server_sees_only_ciphertext` does an HKDF+X25519+AES-GCM encrypt/decrypt end-to-end; live probe `(f)` decrypts `"Secret probe message 42"` |
| I5 | Conversation eligibility never 403s (which leaks existence) — always 404 when the caller is not eligible | `test_list_messages_by_stranger_returns_404`, `test_stranger_send_message_returns_404`; live probe `(g)` `Carl GET conversation → 404` |
| I6 | WS rejects unauthenticated sockets with close 4401 (not 1008 or 1006) | `test_ws_connect_without_token_closes_4401`, `test_ws_connect_with_garbage_token_closes_4401`; live probe `(h)` |
| I7 | WS rejects non-participants trying to subscribe with close 4403 | `test_ws_subscribe_non_participant_closes_4403` |
| I8 | Admin retention minimum is 7 days | `CHECK (message_retention_days >= 7)` in migration 0003 + `PATCH` validator; `test_patch_rejects_below_minimum` |
| I9 | Only admins can call PATCH retention / POST purge | `require_admin` dependency; `test_non_admin_forbidden` |

### Static code audit artefacts

`messaging_service.py` — greps that MUST return zero hits:
```
AESGCM, X25519, HKDF, decrypt, Decrypt, cryptography.hazmat
```
(enforced as a test.)

`schemas/conversations.py` — greps for `str`/`bytes` field declarations whose
name is any of `body|text|plaintext|content|message|subject` MUST be empty.

---

## 3. Key management review

- **Rotation model** (ADR-0013): each `register_key` call locks the caller's
  existing active keys `FOR UPDATE` in the same transaction, marks them
  `rotated` with `rotated_at=now()`, and inserts a new `active` row. A
  **partial unique index** `uq_user_public_keys_one_active WHERE status='active'`
  guarantees at most one active key per user even under concurrent calls.
  Concurrent calls serialize on the `FOR UPDATE` lock; the second one
  rotates the first's just-inserted key. Verified by inspecting the code path
  in `key_service.register_key`.
- **Revocation** (`DELETE /keys/{key_id}`) only operates on the caller's own
  keys. Non-owners receive 404 (`KeyOwnershipError` → 404 code
  `NOT_FOUND`) — no existence leak.
- **Eligibility check on GET /keys/{user_id}**: reuses the shared
  `_can_converse` helper from `messaging_service` so a stranger cannot even
  learn whether a user has a key registered. Returns 404 otherwise.
- **No key material ever leaves the server outside a b64url string** — the
  server only stores and echoes the 32-byte public keys.

---

## 4. WebSocket gateway review

- **Handshake auth** (`_authenticate`): tries `?token=` first, then
  `Authorization: Bearer` header. Any decode failure, expired JWT, missing
  user, disabled/deactivated user → return None → close 4401.
- **Custom close codes**: Starlette requires `accept()` before a custom
  close frame; the gateway accepts, then closes with 4401. The test suite
  confirms the client observes `WebSocketDisconnect(code=4401)` rather than
  a generic 1008.
- **Participant check** (`_is_participant`): admin bypass; otherwise caller
  must be user_a or user_b on the conversation row. Non-participants are
  closed with 4403 — **after** subscribe, which matches the threat model
  (an attacker who already has a valid JWT but not the conversation is the
  threat, not an anonymous HTTP caller).
- **In-process fanout**: `_registry` is a process-local `dict[UUID, set]`.
  This is the documented Phase-6 limitation — a multi-node deploy would
  lose cross-node fanout. Phase 12 migrates to Redis pub/sub.
- **Heartbeat**: 30 s server-initiated ping; dead sockets are dropped
  silently on any send exception.
- **No broadcast leaks**: `_broadcast_event` only sends to subscribers of
  the `conversation_id` the message was posted to. Typing events are
  filtered to subscribers *other than* the sender.

---

## 5. Message send / list / read review

- `store_message` persists `(ciphertext, nonce, ephemeral_public_key,
  recipient_key_id?)` — all opaque bytes — and never touches the payload's
  semantic content.
- `list_messages` uses a DESC cursor on `sent_at` and enforces a 100/page
  cap; opaque `before=<ISO timestamp>` cursor. URL-encoding of the `+` in
  `+00:00` is handled by httpx's `params=` in the test and by real clients.
- `mark_message_read` refuses to mark one's own message; read receipts
  broadcast over WS to the conversation subscribers.
- **Rate limit**: 60 req/min on `POST /messages` — enforced in
  `test_message_send_rate_limit` which re-enables the limiter and asserts
  a 429 after the threshold.

---

## 6. Retention / purge review

- `message_retention_days` DB default **90**, minimum **7**, enforced by:
  - a `CHECK` constraint in migration 0003,
  - the `PATCH` endpoint's Pydantic validator (422 on <7),
  - and the service layer.
- `purge_old_messages` is a single `DELETE ... WHERE sent_at < now() -
  interval`. It is only accessible via `POST /admin/jobs/purge-messages`
  guarded by `require_admin`. Future: move to a scheduled job once Phase 12
  scheduler lands (`start_purge_scheduler()` is already wired for opt-in).

---

## 7. Findings & recommendations

### Passing (no action required)

- Ciphertext-only invariant holds end-to-end (unit tests + live DB scan).
- No plaintext field name is accepted by any endpoint.
- Conversation existence is never leaked (uniform 404).
- Key rotation is concurrency-safe (FOR UPDATE + partial unique index).
- WS handshake rejects at 4401 before accepting any client frames.

### Follow-ups (Phase 12 or later)

1. **Redis pub/sub for WS fanout.** The in-process registry breaks across
   replicas. Phase 12 should switch `_registry` to a Redis-backed
   pub/sub so horizontally-scaled API pods deliver each other's
   broadcasts. Mitigation until then: single-replica deploy for the WS
   process, or sticky-session load balancer keyed on user_id.

2. **Signed WS subprotocol for token rotation.** Today's `?token=<jwt>`
   burns the token in the URL (potentially logged by reverse proxies).
   Phase 12: switch to a `Sec-WebSocket-Protocol` subprotocol carrying a
   short-lived signed handshake token minted by a REST endpoint.

3. **Key-pinning UX.** Clients should pin a peer's key on first use and
   surface a warning if `GET /keys/{user_id}` returns a different key.
   Today the server trusts each user's current `active` key; trust on
   first use is the client's responsibility. Recommend adding a key
   fingerprint (SHA-256 truncated to 8 bytes) to the response for users.

4. **Message length ceiling.** `ciphertext_b64url` is currently unbounded
   above 32 bytes minimum. A 1 MiB cap at the schema layer would be
   prudent — prevents DoS via giant ciphertexts and matches the protocol
   intent (chat messages, not file transfer).

5. **Purge audit log.** `purge_old_messages` returns `purged_count` but
   does not write an audit row. Phase 12 should emit to an `admin_audit`
   table so retention-policy changes and purges are attributable.

6. **Key-id FK on messages is nullable.** `recipient_key_id` can be NULL
   (client didn't supply). For strict multi-device scenarios (Phase 13)
   this should become required so clients can decrypt deterministically
   against the exact key that was active at send time.

7. **Disable the rate limiter globally in tests.** We do this in the
   session-autouse fixture — individual rate-limit tests re-enable it.
   The alternative of relying on per-IP counters under the httpx
   `testserver` hostname was brittle.

### Not findings (by-design)

- Metadata (who talked to whom, when, message lengths, which key was
  recipient) IS visible to operators. ADR-0013 explicitly scopes this out.
- Admin-to-anyone eligibility is intentional — admins need a channel to
  contact any user for support (ADR-0013).
- Messages are mutable via server-side deletion (retention). E2E integrity
  is per-message AEAD; chain integrity (ratchet) is out of scope.

---

## 8. Tests added

| File | Tests | Role |
|---|---|---|
| `tests/_crypto_helpers.py` | — | X25519 / HKDF / AES-GCM utilities for the tests |
| `tests/test_keys.py` | 7 | key registration, rotation, list, revoke, 404 on non-owner |
| `tests/test_conversations.py` | 9 | canonical ordering, idempotent create, eligibility 404 |
| `tests/test_messages_rest.py` | 6 | send / list / read / rate limit / cursor / stranger 404 |
| `tests/test_messaging_ciphertext_only.py` | 3 | **adversarial**: DB scan for plaintext, static audit, schema field audit |
| `tests/test_websocket.py` | 6 | 4401 / 4403 / subscribe+broadcast / ping-pong / typing |
| `tests/test_admin_message_retention.py` | 4 | GET/PATCH retention, 7-day minimum, non-admin 403, purge semantics |

All Phase-5 tests (141) continue to pass — full suite: **177 green**.
