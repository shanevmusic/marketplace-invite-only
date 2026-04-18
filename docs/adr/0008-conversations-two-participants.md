# 8. Conversations are two-participant only (v1)

- Status: accepted
- Date: 2026-04-18
- Phase: 1 (Orchestrator resolution of architecture Q-A3, er-diagram Q-E4, api-contract Q-C2)

## Context

The X25519 + AES-GCM E2E scheme works naturally for 1:1 conversations. Group chats require either group-key exchange (e.g. sender-keys) or per-pair encryption with N-way fanout — both are significantly more complex.

## Decision

Conversations in v1 are strictly **two-participant** (currently customer ↔ seller). Enforcement:

- Application-layer invariant (service-layer check); no DB-level check constraint so a future migration to N participants is simpler.
- Either participant (customer or seller) may initiate a conversation. No directionality restriction in v1.
- Schema preserves an extension seam: if group messaging is added later, introduce `conversation_participants` join table and migrate data.

Driver ↔ customer messaging is **out of scope** for v1.

## Consequences

- Simple crypto, simple UI, simple routing.
- A DB-level uniqueness constraint on `(user_a_id, user_b_id)` prevents duplicate conversations between the same pair.
- Abuse potential (seller cold-messaging customers) is acknowledged; revisit if observed in beta.

## Alternatives considered

- **Group conversations in v1:** rejected as out-of-scope.
- **Customer-initiated only:** rejected — sellers need to respond to order questions proactively (e.g. "your item is ready early").
