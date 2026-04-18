# Frontend Spec — Phase 10 Realtime (WebSocket Client)

**Phase:** 10 — UI/UX Designer deliverable.
**Audience:** Frontend Engineer implementing `lib/core/realtime/**`.
**Depends on:** `phase-10-overview.md`, `phase-10-messaging.md`, `phase-10-tracking.md`; ADR-0013, ADR-0014; `docs/phase-6-notes.md`, `docs/phase-7-notes.md`.

This document specifies the single WebSocket gateway the app uses to replace the Phase 9 polling strategy. One socket multiplexes messaging + tracking; a thin dispatcher fans events into feature providers.

---

## 1. One socket, many channels

**Endpoint:** `GET /ws?token=<jwt>` (upgrade to WebSocket). Single path — the stale `api-contract.md` references to `/ws/v1/messaging` and `/ws/v1/delivery/{id}` are superseded (see overview §C-G1). Backend is authoritative.

**Lifecycle owner:** `RealtimeController` — a `Riverpod` `AsyncNotifier` kept alive for the lifetime of an authenticated session. It is **not** per-screen; screens subscribe to topics and unsubscribe on dispose.

**Why a single socket:**
- Fewer TLS handshakes, one token lifecycle, one reconnection backoff.
- Matches the backend subscriber registry (one client ↔ many channels).
- Simpler heartbeat bookkeeping.

---

## 2. Connection lifecycle

### 2.1 States

```
disconnected → connecting → connected → (disconnecting → disconnected)
                     ↑_______________|
                     backoff-reconnect
```

Exposed as `RealtimeStatus { disconnected, connecting, connected, reconnecting, unauthorized }`. UI banners (see §7) read this provider.

### 2.2 Open

Triggered on app foreground with a valid session. Steps:

1. Read token from `AuthRepository.currentToken()`. If null → remain `disconnected`.
2. Open `WebSocket(uri = wss://<host>/ws?token=<jwt>)`. Dart: `package:web_socket_channel`.
3. Start a **30s application-level heartbeat**: client sends `{"type":"ping"}`; server replies `{"type":"pong"}`. Miss 2 consecutive pongs → treat as dead, close local, schedule reconnect.
4. On open, re-send the subscription set the controller holds in memory (see §3). Survives reconnects without the feature layer knowing.

### 2.3 Close codes (server-initiated)

| Code | Meaning | Client action |
|---|---|---|
| 1000 | Normal closure | No action; reconnect only if app still foreground. |
| 1001 | Going away | Reconnect with standard backoff. |
| 4001 | `auth.expired` | Call `AuthRepository.refresh()`. On success, reconnect with fresh token. On failure, `unauthorized` status → prompt re-login. |
| 4401 | `auth.invalid` | Token rejected. Clear session, route to `/login`. Do not reconnect. |
| 4403 | `channel.forbidden` | Subscription rejected (non-participant). Drop the offending sub from local state; keep socket alive. See §3.3. |
| 1006 | Abnormal (network) | Reconnect with backoff. |

### 2.4 Reconnection backoff

Exponential with full jitter. Sequence (seconds): **1, 2, 4, 8, 16, 30, 60** — then hold at 60.

```dart
Duration nextDelay(int attempt) {
  const steps = [1, 2, 4, 8, 16, 30, 60];
  final s = steps[attempt.clamp(0, steps.length - 1)];
  return Duration(milliseconds: Random().nextInt(s * 1000) + s * 500);
}
```

Reset counter on each successful `connected` transition. When the device regains connectivity (`connectivity_plus` stream), reset the counter and retry immediately.

### 2.5 Dispose

On logout or app backgrounding > 60s (iOS) / app termination: send `{"type":"close"}` if socket open, then `close(1000)`. Clear the in-memory subscription set.

---

## 3. Subscription model

Channels follow `{resource}:{id}` naming. Phase 10 uses two:
- `conversation:{conversationId}` — inbound messaging events for that conversation.
- `delivery:{deliveryOrderId}` — inbound tracking events for that delivery. **Participants only** — the server enforces role checks per ADR-0014.

### 3.1 Subscribe

Client → server:
```json
{"type": "subscribe", "channel": "conversation:abc123"}
{"type": "subscribe", "channel": "delivery:xyz789"}
```

Server → client (ack, optional but expected):
```json
{"type": "subscribed", "channel": "conversation:abc123"}
```

Controller stores the desired set in memory. Any subscribe requested while socket is not `connected` is queued and replayed on the next successful connect.

### 3.2 Unsubscribe

```json
{"type": "unsubscribe", "channel": "conversation:abc123"}
```

Called from `onDispose` of the feature provider (e.g., conversation detail controller). If the socket is already closed, drop from local set silently.

### 3.3 Forbidden subscription handling

If server sends `{"type":"error","code":"channel.forbidden","channel":"delivery:xyz789"}`:
- Remove channel from local set (do not auto-retry).
- Emit a single `TrackingDeniedEvent` to the feature controller — UI falls back to polling or shows empty state, never a crash.
- Do NOT close the socket.

---

## 4. Inbound event schemas

All events are JSON envelopes: `{"type": "<event>", "channel": "<channel>", "data": {...}}`. Unknown types are dropped with a `debugPrint` and **never propagated** — this is the ADR-0014 defense-in-depth line (see §6).

### 4.1 Messaging

| Type | Payload fields (data) | Consumed by |
|---|---|---|
| `message.new` | `message_id, conversation_id, sender_id, sender_pubkey_id, ciphertext, nonce, ephemeral_pubkey, sent_at` | ConversationDetailController — decrypt, append to bubble list. |
| `message.read` | `message_id, conversation_id, reader_id, read_at` | ConversationDetailController — flip ChatBubble to `read` state. |
| `typing` | `conversation_id, user_id, is_typing` | ConversationDetailController — show TypingIndicator for ≤5s. |

### 4.2 Tracking — **internal subscribers only** (driver, seller)

| Type | Payload fields (data) | Consumed by |
|---|---|---|
| `delivery.status` | `delivery_order_id, status, changed_at, changed_by` | Shared — both customer and internal views. |
| `delivery.eta` | `delivery_order_id, eta_iso, source` | Shared. |
| `delivery.location` | `delivery_order_id, lat, lng, heading, speed_mps, recorded_at` | **Internal ONLY.** Customer controller drops on receipt (§6). |

### 4.3 Customer tracking — what the customer may receive

Per ADR-0014, the customer's `delivery:{id}` channel emits only `delivery.status` and `delivery.eta`. If the client observes a `delivery.location` event on a customer subscription, that is a backend bug — the client silently drops it and logs once to Sentry with tag `adr0014_client_violation`. Never render it.

---

## 5. Outbound events

Messaging send is HTTP (`POST /messages`), not WS. The socket is **receive-only** for application payloads; outbound writes are limited to control frames (ping, subscribe, unsubscribe, typing).

### 5.1 Typing indicator

```json
{"type": "typing", "conversation_id": "abc123", "is_typing": true}
```

Client emits on first keystroke after 3s idle; re-emits every 3s while typing; emits `is_typing:false` when composer empty or focus lost. Debounce in the composer — do not send per keystroke.

### 5.2 Driver location publish

Drivers publish coordinates via `POST /delivery-orders/{id}/location` (HTTP), not WS. Reason: HTTP gives us retry + auth failure handling for free, and the server fans out to internal subscribers. See `phase-10-tracking.md` §3.4.

---

## 6. ADR-0014 defense-in-depth (client side)

The backend partitions events by role; the client assumes it will be correct and adds three guards:

1. **Type allow-list per controller.** `CustomerTrackingController` has a switch statement that handles only `delivery.status` and `delivery.eta`. The default case drops the event — no pass-through to view state.
2. **Schema `extra=forbid` analog.** Decoding into `CustomerTrackingEvent` uses a sealed factory that rejects any payload containing `lat`, `lng`, `latitude`, `longitude`, `heading`, or `speed_mps`. Log + drop; do not throw into UI.
3. **Unit test.** A test in `test/realtime/customer_tracking_controller_test.dart` asserts that feeding a raw `delivery.location` envelope leaves view state unchanged. Required PR gate.

Together with the grep test from `phase-10-tracking.md` §5, this makes an accidental coordinate leak observable at: CI grep, type system, runtime guard, unit test, and Sentry tag.

---

## 7. UI surfacing of socket state

The ConnectivityBanner (Phase 9 component) is reused with two new states:

| Status | Banner copy | Style |
|---|---|---|
| `connected` | (hidden) | — |
| `connecting` (cold start <2s) | (hidden — avoid flicker) | — |
| `reconnecting` | "Reconnecting…" | Neutral; no dismiss. |
| `unauthorized` | "Session expired. Log in again." | Error tone; tapping routes to `/login`. |
| `offline` (device) | "You're offline. Messages will send when you're back." | Neutral. |

Debounce transitions: show `reconnecting` only if we've been in that state >1.5s (prevents flicker on fast recoveries).

---

## 8. Polling retirement

Phase 9 used 30s polling on the customer order detail screen to refresh delivery status. Phase 10 replaces this entirely:

| Surface | Phase 9 | Phase 10 |
|---|---|---|
| Customer order detail | 30s poll `GET /orders/:id` | Subscribe `delivery:{id}`; apply `delivery.status` + `delivery.eta` in place. Fallback poll every 120s only if socket `disconnected` >30s. |
| Seller/driver tracking | 30s poll location | Subscribe `delivery:{id}`; apply all three event types. No polling. |
| Conversation list | 30s poll unread counts | Subscribe to each conversation opened in the last 7 days (bounded to 50). Beyond that, poll on list-screen open only. |

**Fallback:** if the socket has been `reconnecting` for >30s, features may re-enable a minimum poll cadence (120s) until the socket returns to `connected`. This is a last-mile safety net — not the default.

---

## 9. Dispatcher contract

```dart
class RealtimeDispatcher {
  Stream<MessagingEvent> messagingEvents(String conversationId);
  Stream<TrackingEvent> trackingEvents(String deliveryOrderId); // customer-safe subset
  Stream<InternalTrackingEvent> internalTrackingEvents(String deliveryOrderId); // includes .location

  Future<void> subscribeConversation(String id);
  Future<void> unsubscribeConversation(String id);
  Future<void> subscribeDelivery(String id, {required bool internalRole});
  Future<void> unsubscribeDelivery(String id);

  void sendTyping(String conversationId, bool isTyping);
  Stream<RealtimeStatus> status;
}
```

`internalTrackingEvents` is **not exported** from the `customer/**` feature folder — same import-boundary rule as ADR-0014. A feature that tries to import it fails the boundary test.

---

## 10. Acceptance criteria

1. Single WS connection at `/ws?token=<jwt>` per session — verified via network inspector.
2. Close code 4001 triggers a silent token refresh + reconnect; 4401 routes to login.
3. Reconnect backoff sequence is `[1,2,4,8,16,30,60]s` with jitter; counter resets on success.
4. Heartbeat `{"type":"ping"}` sent every 30s; 2 missed pongs force local close + reconnect.
5. Subscriptions are replayed after reconnect without feature-layer involvement.
6. `channel.forbidden` drops the offending subscription; socket remains open.
7. `delivery.location` received on a customer subscription is dropped and logged to Sentry with tag `adr0014_client_violation`; UI state unchanged.
8. Unit test in `test/realtime/customer_tracking_controller_test.dart` passes — required PR gate.
9. Phase 9 30s polling on customer order detail is removed in favor of `delivery:{id}` subscription; fallback poll only engages after 30s of disconnect.
10. Typing events debounced to 1 per 3s while typing; `is_typing:false` sent on composer empty or blur.
11. ConnectivityBanner reflects `reconnecting` after 1.5s dwell and `unauthorized` on 4401/4001-refresh-failure; no flicker on fast reconnects.
12. Import-boundary test: `lib/features/tracking/customer/**` cannot import `InternalTrackingEvent` — CI enforced.
