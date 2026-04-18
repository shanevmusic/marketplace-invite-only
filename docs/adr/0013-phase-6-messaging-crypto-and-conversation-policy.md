# 13. Phase 6 messaging — ephemeral ECDH, key rotation, conversation eligibility

- Status: accepted
- Date: 2026-04-18
- Phase: 6 (Backend Engineer + Security Engineer)

## Context

ADR-0009 picked X25519 + AES-256-GCM as the v1 E2E scheme but left three
implementation details open that Phase 6 must nail down:

1. **Static vs ephemeral sender key.** With long-term-static ECDH on both
   sides, a recipient compromise retroactively decrypts all past messages.
   With an *ephemeral* sender key per message, a sender compromise doesn't
   retro-decrypt past outgoing messages; and recipient compromise still
   retro-decrypts but we at least buy "sender-side forward secrecy" at
   ~zero cost.
2. **Key rotation model.** ADR-0009 said "rotated on explicit user action"
   but didn't describe how historical messages stay decryptable after
   rotation. We need a per-key identifier on each ciphertext so the
   recipient picks the right private key, and we need a non-destructive
   rotation (old key remains `rotated` so historical messages still
   decrypt on the recipient device).
3. **Who may converse with whom.** ADR-0008 froze "two-participant, either
   can initiate" but didn't define the eligibility policy. An open
   "anyone-can-message-anyone" policy invites abuse; we need a concrete
   rule that respects the referral-scoped visibility model (ADR-0007).

## Decision

### 1. Per-message sender ephemeral X25519 keypair

- For each message the sender generates a fresh X25519 keypair in-memory.
- The shared secret is `ECDH(sender_ephemeral_priv, recipient_current_pub)`.
- HKDF-SHA256 derives a 32-byte AES-256 key from the shared secret with a
  fixed `info` of `b"marketplace-e2e-v1"` (no salt).
- AES-256-GCM with a random 12-byte nonce produces ciphertext + 16-byte
  tag (tag appended to ciphertext by `cryptography`'s AESGCM API).
- The sender's ephemeral private key is discarded after encryption.

### 2. Multi-key registry with ACTIVE/rotated/revoked states

`user_public_keys` carries:

| Column | Purpose |
|---|---|
| `id` (uuid PK) | referenced by each ciphertext as `recipient_key_id` |
| `user_id` | owner |
| `public_key` (bytea, 32 B) | X25519 public key |
| `key_version` (int) | client-declared monotonic version; informational |
| `status` (`active` \| `rotated` \| `revoked`) | lifecycle |
| `created_at`, `rotated_at`, `revoked_at` | audit timestamps |

Invariant (enforced at service layer + partial unique index): at most
**one** row per `user_id` with `status = 'active'` at any time. Registering
a new key atomically marks any prior active key as `rotated`. Rotation is
additive — old rows are preserved so clients can still decrypt ciphertexts
bound to prior `recipient_key_id`s.

Deletion is soft: `DELETE /keys/{id}` sets `status = 'revoked'`.
Never hard-deleted — the server cannot read ciphertext anyway, so there is
nothing to purge, and historical decryption on the client depends on the
key_id → public_key mapping being stable.

### 3. Conversation eligibility — referral-linked pairs only

For MVP, a conversation may exist **only** between a customer and a
seller where a referral link exists in either direction:

- A **customer** may open a conversation with the seller that referred
  them (`customer.referring_seller_id == seller.id`).
- A **seller** may open a conversation with any customer that carries
  their `referring_seller_id`.

Admins can message any user (support). All other pairings — customer↔customer,
seller↔seller, anyone↔driver — are rejected with `404 NOT_FOUND` (no
existence leak per ADR-0007).

`GET /keys/{user_id}` applies the same eligibility check: if the caller
cannot start a conversation with the target, the key endpoint also returns
`404 NOT_FOUND`. This prevents a user-enumeration oracle via key lookups.

### 4. Replay defense is client-side

The server stores each (ciphertext, nonce, ephemeral_public_key,
recipient_key_id) tuple opaquely. GCM makes each ciphertext/nonce pair
self-authenticating, but the server cannot tell a replay from a legitimate
retransmit. Recipient clients dedupe by message `id` (server-assigned UUID).
Idempotency at the REST layer is client's responsibility (Phase 12 may add
an `Idempotency-Key` header).

### 5. Message retention

`platform_settings.message_retention_days` (int, default 90, CHECK >= 7).
Admin-configurable via `PATCH /admin/settings/message-retention`. A purge
job (`POST /admin/jobs/purge-messages`) hard-deletes messages where
`sent_at < now() - retention_days`. Conversation rows are preserved (they
carry no plaintext and are cheap). Snapshot analogue is unnecessary — there
is no message analytics.

## Consequences

- Server storage grows by one 32-byte ephemeral pubkey per message. Trivial.
- Per-message ECDH cost on the client (~0.1 ms on a phone). Fine.
- Key-rotation UX: client generates a new X25519 keypair, posts the pubkey,
  server atomically demotes the old active key, and the client keeps its
  old **private** key so historical messages still decrypt. The client
  must never discard old private keys unless it also discards the
  corresponding ciphertexts.
- Conversation eligibility is tight for MVP. Sellers cannot cold-message
  arbitrary customers; this mirrors ADR-0007's visibility model and the
  abuse concern noted in ADR-0008.
- No forward secrecy beyond sender-ephemeral. Recipient long-term compromise
  still retro-decrypts. Double-ratchet upgrade reserved for post-GA.

## Alternatives considered

- **Static-static ECDH (no ephemeral):** simpler but worse threat model.
  Rejected.
- **X3DH (Signal's asynchronous handshake):** adds one-time prekeys and
  signed prekeys — significantly more client state and server endpoints.
  Out of scope for v1; reconsider with double-ratchet.
- **Open messaging policy (anyone↔anyone):** rejected — incompatible with
  the referral-visibility model and invites abuse at the marketplace scale.
- **Hard-deleting rotated keys:** rejected — it destroys the ability to
  decrypt historical messages on device reinstalls when the key was fetched
  by `id`.
