# Frontend Spec — Phase 10 Overview (Messaging & Tracking)

**Phase:** 10 — UI/UX Designer deliverable (Frontend C).
**Audience:** Frontend Engineer implementing messaging + live delivery tracking on top of the Phase 8 scaffold and the Phase 9 core flows.
**Scope:** E2E-encrypted 1:1 messaging UI (list + detail + compose), delivery tracking UI for all three roles (customer coord-free view, driver/seller internal map view), WebSocket lifecycle shared between the two features, and the crypto UX for X25519/AES-256-GCM.

This document is the table-of-contents for four sibling files. Read them in this order:

1. `phase-10-overview.md` — **this doc**: scope, principles, cross-cutting decisions.
2. `phase-10-messaging.md` — conversation list, conversation detail, ChatBubble states, crypto UX.
3. `phase-10-tracking.md` — customer tracking view (coord-free) + driver/seller tracking view (map); import-boundary rule.
4. `phase-10-realtime.md` — WebSocket lifecycle, auth handshake, subscription model, event schemas, polling → WS migration.

Phase 10 does **not** touch auth (Phase 8), discovery / products / orders / cart / checkout / dashboard (Phase 9), admin (Phase 11), or notifications (deferred D5 to Phase 12). It slots three feature trees into the Phase 9 app:

```
lib/features/
  messaging/              (new in Phase 10)
    application/          controllers, crypto service, WS subscriptions
    data/                 REST + WS DTOs, repositories
    domain/               Conversation, Message, Key models
    crypto/               X25519 keypair, HKDF, AES-GCM — client-only
    widgets/              ChatBubble (already scaffolded in Phase 8), TypingIndicator, MessageComposer
    screens/              ConversationsListScreen, ConversationDetailScreen
  tracking/               (new in Phase 10)
    customer/             customer-facing coord-free widget tree
      application/
      widgets/            CustomerTrackingView (status + ETA only; NO map)
      screens/            CustomerTrackingScreen
    driver/               driver-facing map widget tree
      application/
      widgets/            DriverMapView (Mapbox)
      screens/            DriverTrackingScreen
    seller/               seller-facing map widget tree (self-deliver)
      application/
      widgets/            SellerMapView (Mapbox, reuses driver internals)
      screens/            SellerTrackingScreen
    shared/               ONLY role-agnostic types; no coord code.
  realtime/               (new in Phase 10)
    ws_client.dart        the sole WebSocket client used by both features
    subscriptions.dart    channel model + reconnection state
```

The `lib/features/tracking/customer/**` subtree is the subject of ADR-0014's grep-test invariant (see §3).

---

## 0. Backend contract — gaps & deviations (Phase 10)

These drive the spec. As in Phase 9, backend behavior wins over `docs/api-contract.md` where they disagree.

| # | Area | Status | Disposition |
|---|---|---|---|
| C-G1 | **WS path is `/ws`, not `/ws/v1/messaging` or `/ws/v1/delivery/{id}`.** Phase 6 and Phase 7 both ship a single gateway at `/ws?token=<jwt>` that multiplexes conversation and delivery subscriptions via client-sent `subscribe` messages (`conversation_id` or `delivery_order_id`). `docs/api-contract.md` §13 shows per-feature paths that were never implemented. | deviation — backend wins | One `WsClient` in `lib/features/realtime/`. Feature features call `wsClient.subscribe(channel)`; single socket. |
| C-G2 | **WS close codes:** `4401` = missing/invalid token, `4403` = non-participant subscribe, `4001` = `auth.expired` (not yet emitted — Phase 6 code only sends `4401` on initial handshake). The client treats `4401` / `4001` / `4003` alike: clear local WS state, trigger a silent token refresh, reconnect. `4403` is terminal for that specific subscription but not the socket. | confirmed | See `phase-10-realtime.md` §3. |
| C-G3 | **`delivery.location` is never sent to customers.** ADR-0014 places customer sockets in a separate bucket; the server has no code path that reaches a customer socket with `delivery.location`. The customer UI must STILL be built so that even if a malicious backend injected a `delivery.location` event into a customer socket, the customer widget tree has no import / no type / no map that could render it. See §3 and `phase-10-tracking.md` §5. | **invariant** | Grep-test + widget-type invariant. |
| C-G4 | **`message.read` ack is both client-sent and server-sent.** Client emits `message.read` with `{message_id}` to tell the server the user has seen a message; server fans `message.read` (with `read_by`, `read_at`) to the other participant. The client must not double-count its own ack as a "they read it" update. | confirmed | Filter by `read_by != self.userId` before updating UI. |
| C-G5 | **`typing` events are ephemeral.** Server fans out but does not persist; dropped on reconnect. UI must auto-clear typing indicators after 5 s of silence even without an explicit `typing:false` from the peer. | by design | Timeout in controller. |
| C-G6 | **Message body cap, attachments.** No backend limit is enforced in Phase 6; practically, encrypted ciphertext fits in a single HTTPS POST body (< 1 MB). **Phase 10 MVP: text only, no attachments.** Attachment UX is deferred to Phase 12 with a dedicated `/attachments/upload-url` endpoint (not yet spec'd). The composer shows an attach icon that is disabled + tooltipped "Attachments coming soon." | backend gap (soft) | Documented in messaging spec §4. |
| C-G7 | **Key rotation UX is user-initiated.** ADR-0013 keeps old keys queryable so historical ciphertexts still decrypt. A "Reset keys" affordance is needed in Profile → Security; cross-phase, we spec it here because it composes with messaging. Rotation = generate new keypair, persist old private key locally under `keys.v1.rotated.{oldKeyId}`, `POST /keys` with new pubkey; server atomically demotes the old row. | confirmed | `phase-10-messaging.md` §6.4. |
| C-G8 | **`delivery.status` for OFD and delivered comes from the orders router**, not from the tracking handler. So moving the customer order-detail off 30-s polling onto `delivery.status` via WS is how we kill the poll from Phase 9 §6. | confirmed | `phase-10-realtime.md` §5. |
| C-G9 | **D4 resolved: Mapbox.** Driver/seller map uses `mapbox_maps_flutter`. A secret `MAPBOX_ACCESS_TOKEN` is read from environment via `--dart-define` at build time and surfaced only inside `lib/features/tracking/driver/` and `lib/features/tracking/seller/`. The customer subtree must not import the Mapbox SDK. | decided | Enforced by grep test + CODEOWNERS-style PR rule. |

---

## 1. Principles (Phase 10)

1. **Two widget trees, not one flag.** Same reasoning as ADR-0014 for tracking: the customer UI and the internal UI are different components, imported from different folders, with different props. A `role` flag on a single widget is rejected. Messaging has only one widget tree (there is no asymmetric visibility in chat), but the crypto UX applies the same principle at the data layer: decrypted plaintext never leaves the device, and no widget ever accepts ciphertext.

2. **Server never sees plaintext; UI never sees ciphertext.** Two immutable boundaries. The messaging feature has a crypto service that converts `ciphertext + nonce + ephemeral_public_key + recipient_key_id` → `String plaintext` (and the reverse on send). Everything above it is plaintext-only; everything below it is ciphertext-only. ChatBubble's prop type is `String text` with no ciphertext counterpart. The REST DTO `MessageEnvelope` has no plaintext field — attempting to add one fails Pydantic `extra="forbid"` on the server.

3. **Customer tracking widgets live in `lib/features/tracking/customer/**` and contain zero map code, zero coordinate fields, zero Mapbox imports.** A grep test in `test/adr_0014_invariants_test.dart` fails the build if any of `lat`, `lng`, `latitude`, `longitude`, `mapbox`, `maplibre`, `google_maps_flutter`, or `LatLng` appears in any Dart file under that subtree.

4. **WebSocket is the transport for real-time; REST is the source of truth for history.** Open a conversation: fetch the last N messages via REST, then subscribe to the conversation WS channel for `message.new` / `message.read` / `typing`. Open a tracking screen: fetch `/deliveries/{order_id}/track` via REST for the current state, then subscribe to the delivery channel for live updates. No reliance on replay-on-subscribe — the backend does not replay. A small gap between REST fetch and WS subscribe is tolerable for MVP; sequence numbers are Phase 12.

5. **Reconnection is silent until it isn't.** Transparent exponential backoff for up to 60 s; after that, a non-intrusive banner "Reconnecting…" appears on the messaging and tracking screens. Users can keep composing messages (queued as `pending`) and can still see the last-known tracking state.

6. **30-s order polling dies in Phase 10.** The Phase 9 fallback in `customer_order_detail_screen.dart` that polls `GET /orders/:id` every 30 s is replaced with a `delivery.status` subscription. Polling code is deleted, not feature-flagged off. See `phase-10-realtime.md` §5.

7. **No DoD-grade forward secrecy UX.** Per ADR-0013 we explicitly ship per-message ephemeral ECDH without a double ratchet. The UI acknowledges encryption in a tasteful "🔒 Encrypted" affordance but does not claim Signal-level properties. A `docs/security/messaging-readme.md` pointer is surfaced from the Security section in the profile for users who ask.

---

## 2. Cross-cutting decisions

### 2.1 One WebSocket connection per app session

A single `WsClient` singleton multiplexes all channels. Subscribing twice to the same channel is idempotent. Unsubscribing from every channel does NOT close the socket — it stays alive so re-entering a conversation / tracking screen is instant. The socket is torn down only on:

- app backgrounded > 60 s (iOS / Android lifecycle);
- user logs out (`AuthController.signOut` fires `WsClient.dispose`);
- token refresh that produces a 4001/4401 on reconnect attempt → retry with new token.

### 2.2 Subscription model

Two channel types, both mapped to the same `/ws?token=<jwt>` path:

- `conversation:{conversation_id}` — subscribes via `{type: "subscribe", conversation_id: "..."}`. Receives `message.new`, `message.read`, `typing`.
- `delivery:{order_id}` — subscribes via `{type: "subscribe", delivery_order_id: "..."}`. Receives `delivery.status`, `delivery.eta`, and (internal only) `delivery.location`.

The role bucket on the server determines which events the socket gets. **Customer clients never send a subscription that asks for `delivery.location`** — the event filter is structurally enforced on the server; our client does not even try. See `phase-10-realtime.md` §4 for the event-schema contract.

### 2.3 Crypto UX posture

- **On signup** (Phase 8 flow): silently generate X25519 keypair, POST public key. No user-facing step. (Phase 8 scaffolded `features/messaging/` as empty; Phase 10 fills it.)
- **On login from a new device**: detect `no local private key` on first messaging open → show a bottom sheet explaining that previous messages cannot be decrypted, offering to generate a fresh key. See `phase-10-messaging.md` §6.2.
- **On key rotation**: explicit user action under Profile → Security → "Reset encryption keys". Confirmation dialog with non-scary copy.
- **Key-fetch failures**: If `GET /keys/{peer_id}` returns 404 (peer never registered), the composer is locked with "This person hasn't set up encryption yet. They need to open the app at least once." No retry loop.
- **Safety numbers (v1 minimal):** a "Verify identity" screen in conversation settings shows a 12-hex-char fingerprint derived from the peer's current public key. Copy-paste + compare out-of-band. No QR scanner in v1 (Phase 12). See `phase-10-messaging.md` §6.3.

### 2.4 Money formatting (still) goes through `formatMoney`

Messaging UI may quote prices inline (e.g., "Is the $19.99 widget still available?"). Any amount the UI composes (not user-typed) must go through `lib/shared/format/money.dart::formatMoney(int minorUnits)`. User-typed text is free-form and not parsed.

### 2.5 Tokens reused

No new colors, spacings, radii, or motion values. Reuse `01-design-tokens.md`:

- Chat bubble colors: `primary`/`onPrimary` (mine), `surfaceVariant`/`onSurfaceVariant` (theirs).
- Typing indicator dots: `onSurfaceVariant` at 60% opacity.
- ETA badge: `tertiaryContainer`/`onTertiaryContainer` (reuses delivery status color).
- Map pin (internal): `primary` for driver, `secondary` for drop-off destination.
- Encryption padlock icon: `onSurfaceVariant` at 72% opacity, `Icons.lock_outline` 14px.
- Reconnecting banner: `surfaceVariant` / `onSurfaceVariant` / 32dp tall.

### 2.6 Accessibility

- ChatBubble: semanticsLabel `"{mine ? 'You' : peerName} said: {plaintext}. {timestamp}. {statusLabel}"`. Failed-to-send bubbles include `"Tap to retry"`.
- Typing indicator: `Semantics(liveRegion: true, label: "{peerName} is typing")`.
- Tracking status chip: `Semantics(liveRegion: true, label: statusHumanLabel)`; on ETA change also announces "ETA X minutes".
- Map views (internal only): the map is not accessible via screen reader by default; we provide a parallel text panel above showing driver address descriptor ("Driver near Main St · 3 minutes away") that IS screen-reader-first.

### 2.7 Offline behavior

- Messaging: queued outgoing messages stay in `pending` state, persisted via `flutter_secure_storage` under `messages.pending.v1`. On reconnect, the oldest pending message is re-sent first. No timestamps shift.
- Tracking: the last-known `CustomerDeliveryView` / `InternalDeliveryView` is cached in memory only (no secure-storage spill — coordinates are not persisted on customer devices, period). The UI shows `"Offline · last updated Xm ago"` banner; the map (internal) stays on the last driver position with a subdued overlay.

### 2.8 401 / session-expiry handling

Identical to Phase 8: `TokenInterceptor` + `AuthController.sessionExpired`. Messaging/tracking controllers listen for `sessionExpired` and `WsClient.dispose()` themselves; routing returns to `/login`. No feature-level duplication.

---

## 3. How Phase 10 composes with Phase 9

### 3.1 Entry points

| From | Goes to |
|---|---|
| Customer Discover — `chat_bubble_outline` in AppTopBar | `/home/customer/messages/:conversationId` (Phase 10) — opens or creates a conversation with the referring seller |
| Customer order detail — `chat_bubble_outline` in AppTopBar | same; `:conversationId` is the customer↔seller conversation for that order |
| Customer order detail — `CustomerDeliveryStatusWidget` tap | `/home/customer/orders/:orderId/tracking` (Phase 10) — a larger read-only coord-free screen. Phase 9 kept the widget inline; Phase 10 promotes a full-screen tracking view. |
| Customer messages tab — `/home/customer/messages` | conversations list (Phase 10). Replaces the Phase 9 placeholder. |
| Seller order detail — chat icon | `/home/seller/messages/:conversationId` — same conversation, seller side. |
| Seller order detail — "Start tracking" when OFD | `/home/seller/orders/:orderId/tracking` — internal map (self-deliver). |
| Driver (in Phase 11 admin-assigns work) | `/home/driver/orders/:orderId/tracking` — internal map, `onMarkDelivered` enabled. (Driver shell itself is Phase 11; spec'd here so the tracking widget is drop-in.) |

All routes above are new in Phase 10 except the two Phase 9 routes they augment (`/home/customer/orders/:orderId`, `/home/seller/orders/:orderId`).

### 3.2 Navigation table (delta)

| Path | Screen | Phase | Role guard |
|---|---|---|---|
| `/home/customer/messages` | ConversationsListScreen | **10** | customer |
| `/home/customer/messages/:conversationId` | ConversationDetailScreen | **10** | customer |
| `/home/customer/orders/:orderId/tracking` | CustomerTrackingScreen (coord-free) | **10** | customer |
| `/home/customer/profile/security/verify/:peerId` | VerifyIdentityScreen | **10** | customer |
| `/home/seller/messages` | ConversationsListScreen (seller variant of same widget) | **10** | seller |
| `/home/seller/messages/:conversationId` | ConversationDetailScreen | **10** | seller |
| `/home/seller/orders/:orderId/tracking` | SellerTrackingScreen (internal map) | **10** | seller |
| `/home/driver/orders/:orderId/tracking` | DriverTrackingScreen (internal map) | **10** *(driver shell is Phase 11 — route reserved)* | driver |

The Messages tab (bottom nav index 2 for customer per `phase-9-navigation-additions.md` §1.1) gets its real body here. The `ConversationsListScreen` widget is role-agnostic — same screen backs both the customer Messages tab and the seller Messages tab (new in Phase 10; see §3.3 for seller shell delta).

### 3.3 Seller shell delta (Messages tab)

Phase 9 gave the seller shell four tabs: Dashboard / Products / Orders / Store. Phase 10 adds a **Messages** tab at index 3, pushing Store to index 4 — **or** (preferred) reuses the existing four-tab layout by adding a persistent chat icon to the Orders list app bar that routes to `/home/seller/messages`. Recommendation is the chat-icon-in-app-bar approach because:

- Sellers interact with messaging in context of an order; few will browse a separate inbox.
- Pushing Store to index 4 breaks the 4-tab tidiness locked in Phase 8.
- The Orders list is already the seller's "work queue"; threading messages through it keeps a single mental model.

The seller Profile tab (`/home/seller/profile` → StoreDetailScreen per Phase 9) also gets a "Messages" list tile that opens the inbox.

### 3.4 Phase 9 polling retirement

`phase-9-customer-flows.md` §6 specified a 30-s poll on `GET /orders/:id` while the customer is on the order detail with `status == out_for_delivery`. Phase 10 replaces that:

- On screen mount: subscribe to `delivery:{order_id}`.
- Receive `delivery.status` → update local order state, trigger a single REST refetch of `/orders/:id` (the status change may affect fields outside the delivery payload).
- Receive `delivery.eta` → update the ETA in the widget only; no REST refetch.
- On unmount: unsubscribe from `delivery:{order_id}`. The socket stays open for other channels.

Polling code in `features/orders/customer/application/` is deleted. A grep test asserts no `Timer.periodic` remains under that directory.

---

## 4. Invariants (PR-review gates, enforced at widget & test level)

Any PR violating one of these must be rejected. These are inherited from prior ADRs and extended for Phase 10.

1. **ADR-0007 — unreferred customers see no data.** The messaging screens do not call any endpoint on a customer whose `referring_seller_id == null`. The Messages tab in that case shows the same access-gated empty state as Discover (`AppEmptyState` "You need a seller invite" copy). No API call, no WS subscribe.

2. **ADR-0009 / ADR-0013 — plaintext never leaves the device as ciphertext receivables; ciphertext never reaches widgets.**
   - `MessageEnvelope` (REST/WS DTO) has `ciphertext`, `nonce`, `ephemeral_public_key`, `recipient_key_id`, `sender_id`, `sent_at`, `message_id`, `read_at`. No `body`/`text`/`plaintext`/`content` fields. Dart mirror of server `extra="forbid"`: freezed union with named fields; unknown JSON keys logged and dropped.
   - `ChatBubble` prop type is `String text` (plaintext). The crypto service is the only place plaintext is produced from an envelope, and the only place a ciphertext is produced from plaintext.
   - Grep test `test/adr_0013_crypto_boundary_test.dart` fails on any `ciphertext` / `nonce` / `ephemeral_public_key` appearing in any widget file under `features/messaging/widgets/` or `features/messaging/screens/`.

3. **ADR-0014 — customer tracking is coord-free by construction.**
   - Two separate widget trees under `lib/features/tracking/customer/` and `lib/features/tracking/{driver,seller}/`. Barrel files `customer/index.dart` and `driver/index.dart` are the sole exports.
   - Grep test `test/adr_0014_tracking_isolation_test.dart` fails if any of `lat`, `lng`, `latitude`, `longitude`, `mapbox`, `maplibre`, `google_maps_flutter`, `LatLng`, `Position`, or `package:mapbox` appears under `lib/features/tracking/customer/`.
   - Import-boundary test: no file under `lib/features/tracking/customer/` may import from `lib/features/tracking/driver/` or `lib/features/tracking/seller/`; reciprocal also forbidden.
   - `CustomerTrackingView` and `CustomerOrderDeliveryProps` (Phase 9) remain the authoritative shape. Adding a coordinate field there is a type-system change and a PR conversation, not a silent edit.

4. **ADR-0003 — `409 DELIVERY_ALREADY_STARTED` is not a user-facing error.** The internal tracking screen's "Mark delivered" button must swallow a 409 silently and refresh the delivery payload. Matches the Phase 9 seller `OrderStateActionPanel` contract.

5. **`delivery.location` must never be rendered in a customer widget.** Even if the event somehow arrives on a customer socket (it won't — server filter), the customer widget tree has no code to render it. This is belt-and-suspenders.

6. **No `Timer.periodic` on order or delivery screens.** WS replaces polling. Grep test in `test/no_polling_test.dart`.

7. **Every amount through `formatMoney`.** Inherited from Phase 9.

---

## 5. Component additions (summary)

Detailed specs live in `phase-10-messaging.md` §8 and `phase-10-tracking.md` §6. Preview:

| # | Name | Scope | Location |
|---|---|---|---|
| 1 | `ConversationPreview` | shared primitive | `lib/shared/widgets/conversation_preview.dart` |
| 2 | `MessageComposer` | feature (messaging) | `lib/features/messaging/widgets/message_composer.dart` |
| 3 | `TypingIndicator` | feature (messaging) | `lib/features/messaging/widgets/typing_indicator.dart` |
| 4 | `EncryptionStatusBadge` | shared primitive | `lib/shared/widgets/encryption_status_badge.dart` |
| 5 | `ChatBubble` (extended — 4 new states) | shared primitive | `lib/shared/widgets/chat_bubble.dart` (Phase 8 scaffold, extended) |
| 6 | `CustomerTrackingView` | feature (tracking customer) | `lib/features/tracking/customer/widgets/customer_tracking_view.dart` |
| 7 | `DriverMapView` / `SellerMapView` | feature (tracking driver/seller) | `lib/features/tracking/driver/widgets/driver_map_view.dart`, `seller/widgets/seller_map_view.dart` |
| 8 | `DeliveryStatusTimeline` (reused from Phase 9 `OrderStatusTimeline` — aliased for clarity) | shared primitive | Phase 9 component |
| 9 | `ReconnectingBanner` | shared primitive | `lib/shared/widgets/reconnecting_banner.dart` |
| 10 | `SafetyNumberView` | feature (messaging) | `lib/features/messaging/widgets/safety_number_view.dart` |

No new design tokens. All components consume `01-design-tokens.md`.

---

## 6. Feature ownership & test gates

| Feature | Owner file under `test/` | Gate |
|---|---|---|
| Messaging | `test/messaging_controller_test.dart`, `test/chat_bubble_test.dart`, `test/adr_0013_crypto_boundary_test.dart` | must pass before Phase 10 merge |
| Tracking | `test/tracking_customer_test.dart`, `test/tracking_internal_test.dart`, `test/adr_0014_tracking_isolation_test.dart` | must pass before Phase 10 merge |
| Realtime | `test/ws_client_test.dart`, `test/ws_reconnection_test.dart`, `test/no_polling_test.dart` | must pass before Phase 10 merge |
| Crypto | `test/crypto_service_test.dart` — round-trip encrypt/decrypt, key rotation, safety-number determinism | must pass before Phase 10 merge |

CI must run `flutter analyze` → 0 errors, and `flutter test` → all green, on the `phase-10-design` (spec) and subsequent `phase-10-impl` branches.

---

## 7. Acceptance criteria (for Phase 10 Frontend Engineer)

The Frontend Engineer implementing Phase 10 MUST deliver all of the following. Each criterion maps to a test or an observable behavior.

1. **Messages list** loads conversations via REST, subscribes to the WS conversation channels the user is a participant of (auto-subscribed server-side at socket open per C-G1), and renders the `ConversationPreview` tiles with last-message preview, unread count, timestamp. Empty state uses `AppEmptyState`.
2. **Conversation detail** fetches the last 50 messages, decrypts them client-side, renders `ChatBubble` list, subscribes to `conversation:{id}` for real-time updates. Sent messages appear immediately in `sending` state; transition to `sent` on REST 201 and to `read` on `message.read` fanout.
3. **Key rotation** UX works: old private keys retained locally under `keys.v1.rotated.{oldKeyId}`; historical messages still decrypt; new messages use the new active key.
4. **Unreferred customer** on the Messages tab shows the ADR-0007 `AppEmptyState`, makes zero API calls, opens zero WS subscriptions.
5. **Customer tracking** screen shows status chip, ETA badge, timeline, destination address, last-updated caption. No map. No lat/lng. No Mapbox import anywhere in the subtree.
6. **Driver/seller tracking** screen shows Mapbox map with driver marker + destination pin + breadcrumb polyline; receives `delivery.location` events and updates the marker; `Mark delivered` button fires `POST /orders/{id}/delivered` and handles 409 idempotently.
7. **Realtime client** opens one `/ws?token=` socket per session, survives backgrounding up to 60 s, reconnects with exponential backoff (1, 2, 4, 8, 16, 30, 60 s capped), re-subscribes active channels on reconnect, shows `ReconnectingBanner` after 3 failed attempts.
8. **No 30-s polling** remains on the customer order detail. `delivery.status` subscription drives the status chip. `no_polling_test.dart` passes.
9. **Grep invariants** pass:
   - `adr_0013_crypto_boundary_test.dart` — no ciphertext tokens in widget files.
   - `adr_0014_tracking_isolation_test.dart` — no coord tokens in `lib/features/tracking/customer/`.
   - `test/no_polling_test.dart` — no `Timer.periodic` on order/delivery screens.
10. **Accessibility** — ChatBubble, typing indicator, tracking status chip, reconnecting banner all have semantics labels and live regions as specified in §2.6.
11. **Offline behavior** — queued outgoing messages persist across app restart and send on reconnect; tracking shows "Offline · last updated Xm ago" banner; internal map freezes on last driver position.
12. **Safety number** — "Verify identity" screen renders a deterministic 12-hex-char fingerprint from the peer's current public key; the same key produces the same fingerprint across launches.
13. **`flutter analyze` → 0 errors** on the Phase 10 impl branch. **`flutter test` → all existing Phase 9 tests still green + new Phase 10 tests green.**

---

## 8. Out of scope for Phase 10

- Group chats (ADR-0008 locked 1:1 for v1).
- Attachments (C-G6; Phase 12).
- Voice / video calls.
- Message search.
- Message forwarding or quoted replies.
- Admin messaging UX (Phase 11 admin).
- Push notifications (D5 → Phase 12).
- QR-code safety-number scanner.
- Historical breadcrumb replay on driver rejoin (only latest position from REST; live stream from WS onward).
- Geospatial ETA computation — driver app supplies ETA.
- Signal double-ratchet upgrade (post-GA, per ADR-0009).

---

## 9. Reading order for implementation

1. `phase-10-realtime.md` first — build `WsClient` and the subscription model; verify against backend with a dev-mode ping.
2. `phase-10-messaging.md` next — crypto service + conversation screens. Reuse `WsClient`.
3. `phase-10-tracking.md` last — customer-side widget is a 1-hour build (no map); driver/seller side is the Mapbox integration. Reuse `WsClient`.

Each of the three sibling documents ends with its own acceptance criteria block that this overview's §7 consolidates.
