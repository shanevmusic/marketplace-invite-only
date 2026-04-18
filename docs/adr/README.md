# Architecture Decision Records

This directory holds the locked architectural decisions for the project.
Each ADR captures context, the decision, and its consequences so future
contributors can understand *why* something is the way it is. ADRs are
append-only; to change a decision, add a new ADR that supersedes the old
one.

Format follows [MADR](https://adr.github.io/madr/) lite: Context →
Decision → Consequences.

## Index

| #    | Title                                                      | One-line summary |
|------|------------------------------------------------------------|------------------|
| 0001 | [Record architecture decisions](0001-record-architecture-decisions.md) | Why and how we write ADRs. |
| 0002 | [Referral token cardinality (multi-use)](0002-referral-token-cardinality-multi-use.md) | Seller referral links are multi-use, admin invites are single-use. |
| 0003 | [Out-for-delivery trigger actors](0003-out-for-delivery-trigger-actors.md) | Only seller or assigned driver may flip an order to `out_for_delivery`. |
| 0004 | [Server-side cart persistence](0004-server-side-cart-persistence.md) | Carts live on the server keyed by customer, not local storage. |
| 0005 | [Single platform currency](0005-single-platform-currency.md) | USD only in v1; multi-currency is a post-v1 problem. |
| 0006 | [Server-side refresh tokens](0006-server-side-refresh-tokens.md) | Refresh tokens rotated server-side with revocation list, not opaque JWTs. |
| 0007 | [Referral chain depth one](0007-referral-chain-depth-one.md) | We only track the direct inviter, not a full referral graph. |
| 0008 | [Conversations two-participants](0008-conversations-two-participants.md) | All conversations are 1:1; no group chat in v1. |
| 0009 | [E2E scheme X25519 + AES-GCM](0009-e2e-scheme-x25519-aes-gcm.md) | ECDH over X25519 + per-message AES-256-GCM; server stores ciphertext only. |
| 0010 | [Phase 4 store city + dashboard source](0010-phase-4-store-city-and-dashboard-source.md) | Store `city` is canonical; dashboard analytics read from snapshot columns. |
| 0011 | [seller_id == user_id invariant](0011-seller-id-equals-user-id-invariant.md) | Sellers are users; `seller_id` equals `user_id` everywhere. |
| 0012 | [Order state machine + retention](0012-order-state-machine-and-retention.md) | Closed set of statuses, admin-set retention floor, lifetime-sales snapshot. |
| 0013 | [Phase 6 messaging crypto + conversation policy](0013-phase-6-messaging-crypto-and-conversation-policy.md) | Applies ADR 0009 to messaging; open-conversation policy by invite. |
| 0014 | [Delivery tracking asymmetric visibility](0014-delivery-tracking-asymmetric-visibility.md) | Seller/driver see customer coords; customer sees only status + ETA. |
| 0015 | [Frontend API client](0015-frontend-api-client.md) | Dio + code-gen repositories; one client per feature module. |

## Adding a new ADR

1. `cp 0001-record-architecture-decisions.md NNNN-short-slug.md`.
2. Bump `NNNN` to the next sequence number.
3. Fill in *Context*, *Decision*, *Consequences* (and *Status* if not
   `Accepted`).
4. Add a row to the table above.
5. Open a PR; merge once reviewers agree the decision belongs in the
   locked set.
