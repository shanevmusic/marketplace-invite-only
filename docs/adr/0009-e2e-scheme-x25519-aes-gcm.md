# 9. E2E messaging scheme — X25519 + AES-256-GCM (v1)

- Status: accepted
- Date: 2026-04-18
- Phase: 1 (resolves open decision D2 from PROJECT.md §7)

## Context

PROJECT.md §7 listed the E2E scheme as open: simple X25519+AES-GCM vs. Signal-style double ratchet. Double ratchet provides forward secrecy and post-compromise security but requires significantly more client logic, per-conversation state, and testing.

## Decision

v1 uses **X25519 ECDH** for per-message ephemeral key derivation with **AES-256-GCM** for authenticated encryption. Each message carries its own ephemeral sender public key; the receiver derives the shared secret with their long-term X25519 private key. This provides end-to-end confidentiality and integrity; it does NOT provide forward secrecy across all messages (compromise of a recipient's long-term key exposes past messages to a network adversary with stored ciphertext).

Schema already reserves a `ratchet_state jsonb` column on `messages` so a future upgrade to the double ratchet is a non-breaking migration.

## Consequences

- Simple, implementable in Phase 6 without a crypto expert.
- Clients register a single long-term X25519 public key; rotated on explicit user action.
- Documented limitation: no forward secrecy. Revisit before GA.
- The server stores only `ciphertext`, `nonce`, `ephemeral_public_key`, and metadata — never plaintext. Security Engineer will audit in Phases 6 and 12.

## Alternatives considered

- **Signal double ratchet:** deferred; revisit post-GA if threat model requires forward secrecy.
- **Plaintext + TLS-only:** rejected; does not meet PROJECT.md E2E requirement.
