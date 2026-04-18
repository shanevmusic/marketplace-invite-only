# Frontend Spec — Phase 10 Messaging

**Phase:** 10 — UI/UX Designer deliverable (Frontend C).
**Audience:** Frontend Engineer implementing E2E-encrypted 1:1 messaging.
**Scope:** conversation list, conversation detail, ChatBubble state machine, typing indicator, composer, attachments policy (deferred), keyboard handling, client-side X25519/AES-GCM crypto UX, key rotation UX, "Verify identity" / safety numbers (minimal v1).

This doc extends `phase-10-overview.md`. Read that first — the principles (§1), invariants (§4), and WebSocket lifecycle (delegated to `phase-10-realtime.md`) apply here.

Every plaintext message is derived on-device. The server stores and transmits ciphertext only (ADR-0009, ADR-0013). The widget tree never accepts ciphertext.

---

## 0. Backend contract recap (messaging endpoints)

Per Phase 6 shipped:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/keys` | Register or rotate caller's X25519 public key. Body `{public_key, key_version}`. Server marks prior active key `rotated`. Returns new `{id, public_key, key_version, status, created_at}`. |
| `GET /api/v1/keys/me` | Caller's own keys (all statuses, for local recovery). |
| `GET /api/v1/keys/{user_id}` | Peer's **current active** key. Eligibility-gated: 404 if caller cannot start a conversation with target (ADR-0013 §3). |
| `DELETE /api/v1/keys/{key_id}` | Soft-revoke. Sets `status = revoked`. |
| `POST /api/v1/conversations` | Create-or-return. Body `{participant_id}`. 201 with existing id if one exists (idempotent). Errors: `SELF_CONVERSATION`, `CONVERSATION_NOT_ELIGIBLE` (mapped to 404 per ADR-0007). |
| `GET /api/v1/conversations` | Paginated list of caller's conversations. |
| `GET /api/v1/conversations/{id}` | Detail. 404 if caller not a participant. |
| `GET /api/v1/conversations/{id}/messages?cursor&limit&direction=desc` | Cursor-paginated ciphertext history. |
| `POST /api/v1/conversations/{id}/messages` | Send. Body `{ciphertext, nonce, ephemeral_public_key, recipient_key_id}` (all base64). Server stores opaquely; broadcasts `message.new`. |
| `POST /api/v1/conversations/{id}/messages/{message_id}/read` | Mark read. Server broadcasts `message.read`. |
| `/ws?token=<jwt>` | Single WS gateway. Subscribe with `{type:"subscribe", conversation_id:"..."}`. See `phase-10-realtime.md`. |

**Deviation from api-contract.md:** the contract shows `POST /api/v1/keys/register` and a single-key model; backend ships `POST /api/v1/keys` with a multi-key registry. Use backend paths verbatim.

---

## 1. Screen inventory

| Route | Screen | Component file |
|---|---|---|
| `/home/customer/messages` | ConversationsListScreen | `lib/features/messaging/screens/conversations_list_screen.dart` |
| `/home/customer/messages/:conversationId` | ConversationDetailScreen | `lib/features/messaging/screens/conversation_detail_screen.dart` |
| `/home/customer/profile/security` | SecuritySettingsScreen | `lib/features/messaging/screens/security_settings_screen.dart` |
| `/home/customer/profile/security/verify/:peerId` | VerifyIdentityScreen | `lib/features/messaging/screens/verify_identity_screen.dart` |
| `/home/seller/messages` | ConversationsListScreen (same widget, different shell guard) | — |
| `/home/seller/messages/:conversationId` | ConversationDetailScreen | — |

---

## 2. ConversationsListScreen — `/home/{customer,seller}/messages`

**Purpose:** inbox of 1:1 conversations. Customer sees their referring-seller conversation (plus admin support, if any). Seller sees every conversation with a customer they referred.

### 2.1 Layout — State B (data)

```
AppTopBar(title: "Messages", trailing: [Icons.lock_outline → brief tooltip "Messages are end-to-end encrypted"])
Body:
  [if ReconnectingBanner should show] → 32dp banner above list
  ListView.separated:
    ConversationPreview tile per conversation:
      leading: AppAvatar(md, peer)
      title: peer.display_name (titleMedium)
      subtitle: last-message preview (bodyMedium, maxLines=1, ellipsized)
              — for own message: "You: …", for peer: "…"
              — if last message is not yet decrypted (missing key): "🔒 Encrypted message"
      trailing column:
        relativeTime(last_message_at) (bodySmall, onSurfaceVariant)
        if unread_count > 0: TabBadge(count: unread_count) pill
      onTap → /home/{role}/messages/:id
```

### 2.2 Layouts by state

| State | UI |
|---|---|
| loading | 6× `AppSkeleton.SkeletonTile()` matching the tile layout |
| empty (customer, referred, no convos yet) | `AppEmptyState(icon: Icons.chat_bubble_outline, headline: "No messages yet", subhead: "Tap the chat icon on a store or order to start a conversation.", ctaLabel: null)` |
| empty (customer, **unreferred** — ADR-0007) | `AppEmptyState(icon: Icons.lock_outline, headline: "You need a seller invite", subhead: "Messages unlock when a seller invites you.", ctaLabel: "How invites work")` — **no API call fired** |
| empty (seller) | `AppEmptyState(icon: Icons.chat_bubble_outline, headline: "No customer conversations yet", subhead: "When a customer messages you, it will appear here.")` |
| data | §2.1 |
| network error | `AppEmptyState(icon: wifi_off, headline: "Can't load messages", ctaLabel: "Retry")` |
| 401 | handled globally via `TokenInterceptor` |

### 2.3 API calls

1. `AuthController` session already has `user.referring_seller_id` / `user.role`.
2. If customer **and** `referring_seller_id == null` → render unreferred empty state, **skip** `GET /conversations`. WS not subscribed.
3. Else: `GET /api/v1/conversations?limit=50`.
4. On mount: ensure `WsClient` is connected (idempotent); the `connected` ack enumerates conversation ids the server auto-subscribed the socket to. Listen for `message.new` and `message.read` — apply as a list diff (re-sort by `last_message_at`, increment `unread_count`).

### 2.4 Realtime updates

A `message.new` event from a conversation already in the list:
- Update the tile's preview + timestamp.
- If the user is not currently on that conversation's detail screen AND the message is not from the current user → increment `unread_count`.
- Re-sort the list so the updated tile moves to the top.

A `message.new` for a conversation NOT in the list (first message in a newly-created conversation created by the peer):
- Fire a lightweight `GET /api/v1/conversations/{id}` to fetch the participants (the event payload has `conversation_id` and `sender_id`; fetching gets us the peer's `display_name` and avatar).
- Prepend the tile.

### 2.5 Accessibility

- Each tile: `Semantics(button: true, label: "Conversation with ${peer.display_name}, last message ${preview}, ${unread_count > 0 ? '${unread_count} unread' : 'all read'}, ${relativeTime}")`.
- Unread badge: `labelSmall`, but semantics label on the tile subsumes it (don't double-announce).
- Encryption tooltip (the `Icons.lock_outline` in the app bar) is behind a long-press; `Semantics(tooltip: "Messages are end-to-end encrypted")`.

---

## 3. ConversationDetailScreen — `/home/{role}/messages/:conversationId`

**Purpose:** the chat. Inverted list of messages, composer pinned to bottom, typing indicator above composer.

### 3.1 Layout

```
AppTopBar(variant: default,
  title: peer.display_name,
  subtitle (bodySmall): "End-to-end encrypted" with Icons.lock_outline,
  trailing: [Icons.info_outline → conversation info bottom sheet])

[if ReconnectingBanner should show] → 32dp banner directly below app bar

Body (Scaffold body):
  ListView.builder(reverse: true, padding: EdgeInsets.symmetric(horizontal: space4, vertical: space3)):
    messages rendered from most-recent at bottom to oldest at top
    — each entry: Padding(vertical: space1) + ChatBubble(...)
    — date divider chip every 24h gap ("Today", "Yesterday", "Apr 18")
  (implicit pull-up at top triggers cursor pagination — loads 50 older messages)
  Typing indicator (§5) rendered as a sticky row below the last bubble when peer is typing
  [MessageComposer] sticky at bottom
```

### 3.2 States

| State | UI |
|---|---|
| loading (first fetch) | 5× message-shaped `SkeletonBox` alternating left/right 72%-max widths |
| data | §3.1 |
| empty (no messages yet — new conversation) | Centered `AppEmptyState(icon: Icons.lock_outline, headline: "Say hello", subhead: "Messages in this conversation are end-to-end encrypted.", ctaLabel: null)` above the composer |
| keys missing (peer has never opened app) | Composer disabled; inline banner above composer "${peer.display_name} hasn't set up encryption yet. They need to open the app at least once." |
| keys missing (local — this device has no private key) | Full-screen cover: `AppDialog` (non-dismissible) "Can't decrypt messages on this device. Your encryption keys live on the device you first signed up on. Generate a new key? Old messages will not be readable here." → CTA "Generate new key" + "Cancel" (pops back) |
| decryption error (single message) | That bubble renders as a "failed to decrypt" placeholder — see §4 |
| network error (history fetch) | Inline retry banner at top of list |
| 404 (not a participant) | pop back to `/home/{role}/messages` with snackbar "Conversation unavailable" |

### 3.3 API + WS on mount

1. `GET /api/v1/conversations/{id}` → confirm participant, fetch peer's `user_id` and `display_name`.
2. `GET /api/v1/keys/{peer_user_id}` → peer's current active pubkey. Cache by `peer_user_id` + `key_id`. **This is the encryption target.** If 404 → keys-missing state.
3. `GET /api/v1/conversations/{id}/messages?limit=50&direction=desc` → 50 newest ciphertext envelopes.
4. For each envelope: look up `recipient_key_id` in local key store; decrypt → plaintext. If the envelope references a `recipient_key_id` we no longer hold (key was revoked locally, impossible if rotation flow was followed) → surface as decryption-error bubble.
5. `wsClient.subscribe(conversationChannel(id))`. On `message.new` events: decrypt and append. On `message.read` with `read_by != me`: update the corresponding bubble to `read` state.
6. On screen leave: `wsClient.unsubscribe(conversationChannel(id))`. Socket stays open.

### 3.4 Reading behavior

When a `message.new` event arrives AND the user is scrolled to the bottom (within 32dp) AND the screen is visible:
- Mark-as-read after 500 ms dwell: `POST /api/v1/conversations/:id/messages/:message_id/read`.
- Server fans out `message.read`; mine bubbles on the peer's client flip to `read`.

When the user scrolls up above the latest message: no auto-read; a "new" chip appears at the bottom when additional messages arrive ("3 new ↓"). Tap scrolls to bottom, triggers read.

### 3.5 Sending a message

The composer (§4) emits a `String plaintext`. The controller:

1. Push an optimistic `MessageViewModel(id: client_tmp, plaintext, status: sending, isMine: true, sentAt: now)` to the list.
2. Persist to `flutter_secure_storage` under `messages.pending.v1/{conversation_id}/{tmp_id}` (survives app kill).
3. Encrypt: `crypto.encryptFor(peerKey, plaintext)` → `{ciphertext, nonce, ephemeralPublicKey}`.
4. `POST /api/v1/conversations/:id/messages` with that payload + `recipient_key_id = peerKey.id`.
5. On 201: replace the optimistic VM with the server message (keep the `sending → sent` animation). Remove from secure-storage pending.
6. On network error / timeout: flip status to `failed`. The bubble's retry icon is wired to re-send (same ephemeral pubkey is regenerated on retry — the ECDH is ephemeral per attempt).
7. On 403/404 (conversation disappeared): `AppDialog` "This conversation is no longer available" → pop. Remove the pending message.

Message ids: server-assigned UUIDs. Deduplicate in the list by `id` (once 201 returns, the tmp id is replaced; WS may still fire `message.new` for the same id — the set guard drops the duplicate).

### 3.6 Keyboard handling

- Composer uses `TextField.onSubmitted` with action `TextInputAction.send`.
- iOS keyboard: "send" button visible; tapping sends (does not insert newline).
- Android: same. For multi-line mode (shift-enter / long-press), expose a small "multiline" toggle in the composer overflow (Phase 12 nice-to-have; Phase 10 ships single-line).
- Keyboard-aware scrolling: `MediaQuery.viewInsets.bottom` is consumed by the composer; list auto-scrolls to bottom on keyboard open if user was already at bottom.
- Dismiss keyboard on scroll up (iOS feel) — `ScrollController` listener.

### 3.7 Date dividers

Every 24 h gap between adjacent messages inserts a `Center(Chip(label: "Today" | "Yesterday" | "Apr 18"))`. Computed locally from `sentAt`. On inverted list, the chip sits **above** the older group.

### 3.8 Accessibility

- ChatBubble: see §4.
- Typing indicator: `Semantics(liveRegion: true, label: "${peer.display_name} is typing")`.
- Date divider: `Semantics(label: "Messages from {date}")`.
- Composer: `Semantics(textField: true, label: "Message to ${peer.display_name}, end-to-end encrypted")`.

---

## 4. ChatBubble — state machine (extends Phase 8 `ChatBubble`)

Phase 8 declared `sending | sent | read | failed` (see `02-component-library.md` §6). Phase 10 adds two more states and formalizes the visual and semantics for each.

### 4.1 States (final)

| # | State | Trigger | Visual | Icon (trailing) | Tap |
|---|---|---|---|---|---|
| 1 | `pending` | Queued while offline or WS disconnected | 60% opacity bubble, italics caption "Will send when online" below timestamp | `Icons.schedule` 12px onPrimary@60% | — |
| 2 | `sending` | REST POST in flight | 70% opacity bubble | `Icons.access_time` 12px | — |
| 3 | `sent` | REST 201 received (server has the ciphertext) | full opacity | `Icons.check` 12px | — |
| 4 | `delivered` | WS `message.new` fanout confirmed arrived at peer socket | full opacity | `Icons.done_all` 12px onPrimary@60% | — |
| 5 | `read` | `message.read` fanout from peer | full opacity | `Icons.done_all` 12px in `tertiary` color | — |
| 6 | `failed` | REST error / network timeout | full opacity, small red border left (2dp) | `Icons.error_outline` 12px in `error` | **tap to retry** (re-encrypt, re-POST) |
| 7 | `decryptionError` | local decrypt threw (missing key, corrupted ciphertext, GCM tag failed) | `surfaceVariant` bg, italic text "🔒 Couldn't decrypt this message", 80% opacity | `Icons.lock_outline` 12px | long-press → "Show details" bottom sheet with `recipient_key_id`, `sent_at`, a "Try again" button that re-runs decrypt (e.g., after a key-store refresh) |

**Note on `delivered` vs `sent`:** Phase 6 backend does not emit a per-recipient delivery ack. The client infers `delivered` from its own echo of `message.new`: when the sender's socket receives the `message.new` for their own message id, we know the server broadcast it (i.e., it's now in the conversation fanout). This is a weak signal — a truly offline peer still shows as `delivered` from the sender's perspective. This matches common UX and is acceptable. `read` is a hard ack.

### 4.2 Visual spec (final)

All reuse tokens from `01-design-tokens.md`:

- Radius: `radiusMd = 12` with asymmetric 4dp corner (bottom-right for mine, bottom-left for theirs).
- Max width: 72% of list viewport width.
- Padding: `space3 = 12` horizontal, `10` vertical (not a token — round nicely).
- Text: `bodyMedium`.
- Timestamp: `bodySmall` `onPrimary@70%` (mine) / `onSurfaceVariant@70%` (theirs), trailing the bubble outside.
- Status icon: right of timestamp for mine; not rendered for theirs.
- Gap between consecutive mine or theirs bubbles: `space1 = 4`. Gap on role switch: `space3 = 12`.

### 4.3 Props (Phase 10, final — extends Phase 8 signature)

```dart
class ChatBubble extends StatelessWidget {
  final String text;                    // already decrypted plaintext
  final bool isMine;
  final DateTime sentAt;
  final MessageStatus status;           // enum: pending/sending/sent/delivered/read/failed/decryptionError
  final VoidCallback? onRetry;          // status=failed → tap; decryptionError → long-press details
  final VoidCallback? onLongPress;      // for decryptionError details and (Phase 12) copy/quote
  final String? senderDisplayName;      // optional; only used in future group UX, null for 1:1
  const ChatBubble(...);
}
```

**Hard rule (from Phase 8):** no `ciphertext` / `nonce` / `ephemeralPublicKey` props. Widget accepts plaintext only. Grep test rejects any such identifier under `features/messaging/widgets/`.

### 4.4 Semantics

`Semantics(label: _composedLabel)` where:

```
_composedLabel = (isMine ? "You said" : "${peer.displayName} said") + ": " + text
  + ". Sent ${relativeOrAbsolute(sentAt)}."
  + switch(status) {
      pending: " Pending — will send when online.",
      sending: " Sending.",
      sent: " Sent.",
      delivered: " Delivered.",
      read: " Read.",
      failed: " Failed. Double-tap to retry.",
      decryptionError: " Could not be decrypted.",
    }
```

Screen readers traverse newest-first (inverted list order).

---

## 5. TypingIndicator

**Purpose:** show the peer is composing. Ephemeral.

**Location:** `lib/features/messaging/widgets/typing_indicator.dart`.

**Trigger:** WS `typing` event with `typing: true` from the peer. Auto-clears after 5 s of no new `typing:true` or upon receiving `typing: false` (C-G5).

**Client → Server:** when the user types (debounced at 1 s), emit `{type:"typing", conversation_id, typing:true}`. On composer empty, emit `{type:"typing", conversation_id, typing:false}`.

**Layout:**
```
Padding(horizontal: space4, vertical: space2):
  Align(left):
    Container(radiusMd, surfaceVariant, padding: 10/12):
      Row(mainAxisSize: min):
        AnimatedDot(...) × 3 — staggered 0, 200ms, 400ms, opacity 0.4 ↔ 1.0
```

**Semantics:** `Semantics(liveRegion: true, label: "${peer.displayName} is typing")`.

**Motion:** respects `MediaQuery.disableAnimations == true` → dots render static at 70% opacity.

---

## 6. Crypto UX

### 6.1 Key lifecycle — local

Local store: `flutter_secure_storage`, key prefix `keys.v1`.

| Key | Contents |
|---|---|
| `keys.v1.active` | JSON `{keyId, publicKey, privateKey, createdAt}` — current active keypair |
| `keys.v1.rotated.{keyId}` | JSON of each past-active keypair, preserved so historical messages still decrypt |
| `keys.v1.device_salt` | 32-byte random, used in safety-number derivation (§6.3) |

Private keys are stored in the secure-storage flavor for each platform:
- iOS: Keychain (`kSecAttrAccessibleAfterFirstUnlock`, not `ThisDeviceOnly` — we want iCloud keychain sync off by default per `kSecAttrSynchronizable=false`).
- Android: EncryptedSharedPreferences.

On **app uninstall**: keys vanish. On **fresh install** on a new device: local store empty → keys-missing flow (§3.2).

### 6.2 Onboarding flows

**First-ever sign-up (Phase 8):** after `AuthController` resolves the session, a deferred action generates the keypair and POSTs the pubkey in the background. UI shows no modal; the first time the user opens Messages, keys are already live.

Detailed steps:
1. `crypto.generateKeypair()` → `{publicKey, privateKey}` (X25519 via `cryptography` package or `libsodium_dart`).
2. `POST /api/v1/keys` with `{public_key: base64(publicKey), key_version: 1}`.
3. Server returns `{id, key_version, status, created_at}`.
4. Save to `keys.v1.active`.
5. If step 2 or 3 fails, retry on next app foreground. Until success, `POST /conversations` and `POST /messages` are blocked at the feature level — a synthetic state.

**Login on a new device (no local keys):**
- On first open of the Messages tab OR first attempt to send a message:
- Show `AppDialog` non-dismissible:
  ```
  Title:    Set up encryption on this device
  Body:     Your messages are end-to-end encrypted. To read new messages on this device, we need to generate a new encryption key.
            Old messages from other devices won't be readable here.
  Primary:  "Generate new key"  → runs §6.2 steps 1–4 (replaces server's active key; ADR-0013 demotes old one to `rotated`)
  Secondary: "Cancel"           → closes the dialog, pops to previous screen. User can try later.
  ```
- After generation, also pull `GET /keys/me` to repopulate `keys.v1.rotated.*` entries for old keys (public only; private keys are lost — any ciphertext bound to them is unreadable on this device; surface as `decryptionError` bubbles).

### 6.3 "Verify identity" / safety numbers (minimal v1)

**Route:** `/home/{role}/profile/security/verify/:peerId` (also linked from conversation info bottom sheet).

**Screen:** `VerifyIdentityScreen`.

**Layout:**
```
AppTopBar(title: "Verify identity", variant: modal)
Body (centered, space6 padding):
  AppAvatar(lg, peer)
  [space4]
  Text(peer.display_name, headlineSmall)
  [space6]
  Label bodyMedium onSurfaceVariant: "Safety number"
  [space2]
  Text(safetyNumber, titleLarge, fontFamily: monospace)  // "A93C  F1B8  72DE"
  [space1]
  Caption bodySmall: "Compare this with the number ${peer.display_name} sees on their device."
  [space6]
  Button(secondary, expand: true, "Copy") → copies to clipboard, snackbar
  Button(text, "How verification works") → explainer bottom sheet
```

**Safety number derivation:**
```
safetyNumber = hex(SHA256("marketplace-v1" || sort(my_pub, peer_pub)))[0..12].chunk(4, " ")
```
- 12 hex chars, 48 bits — enough for a manual compare, not cryptographically authenticating in the Signal sense.
- Canonical ordering (`min(my_pub, peer_pub)` first) so both sides compute the same value.
- Deterministic across launches; updates when either side rotates keys.

**Change-of-key warning:** when the controller detects that the peer's `GET /keys/{id}.key_version` increased since last open of this conversation, prepend a system bubble:
```
AppCard(variant: default, tertiaryContainer bg, padding: space3):
  Row: Icons.security + Text("${peer.display_name}'s encryption key has changed. Verify their identity to confirm this is expected.", bodySmall)
  Trailing: TextButton "Verify" → /verify/:peerId
```

Dismissible per-conversation. Re-shown on next key change.

### 6.4 Reset keys flow (key rotation, user-initiated)

**Route:** `/home/{role}/profile/security` → tile "Reset encryption keys".

**Flow:**
1. `AppDialog`:
   - Title: "Reset encryption keys?"
   - Body: "This generates a new key for all future messages on this device. Messages you've already received will still be readable here. Other people will see a ‘key changed' notice the next time you message them."
   - Primary (destructive flavor, but with neutral copy): "Reset"
   - Secondary: "Cancel"
2. On confirm:
   - Move current `keys.v1.active` → `keys.v1.rotated.{keyId}`.
   - Generate new keypair.
   - `POST /api/v1/keys` with new pubkey.
   - Save new keypair as `keys.v1.active`.
   - Snackbar success "Encryption keys reset. Your next message will use the new key."
3. On error: restore old `active`, snackbar error.

No automatic rotation schedule in v1.

### 6.5 Encryption affordance — where the "🔒" shows

| Surface | Affordance |
|---|---|
| Conversations list app bar | Single `Icons.lock_outline` in trailing; long-press tooltip "Messages are end-to-end encrypted" |
| Conversation detail app bar subtitle | bodySmall "End-to-end encrypted" + 12px `Icons.lock_outline` |
| Empty chat state | `Icons.lock_outline` 32dp + copy |
| Message composer hint text | e.g., "Message ${peer.first_name}…" — no crypto copy (avoids scare) |
| Decryption-error bubble | `Icons.lock_outline` 12px + italic copy |

Do **not** render a padlock on every single bubble (clutter). Do **not** show cryptographic terms like "AES-256-GCM" in the user-facing UI (only in `docs/security/messaging-readme.md` linked from security settings).

---

## 7. Composer

**Location:** `lib/features/messaging/widgets/message_composer.dart`.

### 7.1 Layout

```
Container(surface bg, border top 1dp outlineVariant, padding: space2 horizontal, space2 vertical):
  Row:
    IconButton(Icons.attach_file, disabled, tooltip: "Attachments coming soon")  // C-G6
    Expanded: AppTextField(
      hint: "Message ${peer.first_name}…",
      keyboardType: multiline,
      textInputAction: send,
      maxLines: 5, minLines: 1,
      autocorrect: true,
      maxLength: null,          // no client-side cap in Phase 10; server will reject > 1MB ciphertext
    )
    IconButton(Icons.send, onPressed: text.isNotEmpty ? _send : null,
               tooltip: "Send")
```

- Disabled state: whole composer at 38% opacity, text field read-only, send button inactive (e.g., peer has no key).
- Pending-message queue indicator: if there are queued `pending` messages, a small chip above the composer "1 queued · Sending when online" with Icons.schedule.

### 7.2 Props

```dart
class MessageComposer extends StatefulWidget {
  final void Function(String plaintext) onSend;
  final void Function(bool typing) onTypingChanged;
  final bool enabled;
  final String peerFirstName;
  final int queuedCount;
}
```

### 7.3 Accessibility

- Text field: `Semantics(textField: true, label: "Message to ${peer.displayName}, end-to-end encrypted")`.
- Send button: `Semantics(button: true, label: "Send", enabled: text.isNotEmpty)`.
- Attachment button: `Semantics(button: true, label: "Attach file, coming soon", enabled: false)`.

### 7.4 Attachments policy (v1)

**Disabled.** Icon present to establish UX affordance. Tooltip and semantics label both say "coming soon". Phase 12 will:
- Add a bottom sheet with options (photo from camera / photo from library / file).
- Use a to-be-built `/api/v1/attachments/upload-url` endpoint.
- Encrypt the file bytes with the same X25519/AES-GCM scheme (one fresh ephemeral key per attachment), upload ciphertext, post a message whose plaintext is a JSON stub `{type:"attachment", storage_key, mime, size, name}`.

---

## 8. Component specs added in Phase 10

### 8.1 `ConversationPreview`

```dart
class ConversationPreview extends StatelessWidget {
  final String conversationId;
  final String peerDisplayName;
  final String? peerAvatarUrl;
  final String? lastMessagePreview;   // null = "No messages yet", "🔒 Encrypted message" if decrypt failed
  final DateTime? lastMessageAt;
  final int unreadCount;
  final bool peerHasKey;              // if false, append faint " · not yet set up" in subtitle
  final VoidCallback onTap;
}
```

Composed from `AppListTile(interactive)` + `AppAvatar(md)` + `TabBadge`.

### 8.2 `EncryptionStatusBadge`

```dart
class EncryptionStatusBadge extends StatelessWidget {
  final EncryptionStatus status;   // active | missingLocal | missingRemote | rotated
  final double iconSize;           // 12 | 14 | 16
}
```

Renders an `Icons.lock_outline` + optional micro-copy. States:

- `active`: padlock + nothing.
- `missingLocal`: padlock with warning dot + "Set up encryption" (link in security settings).
- `missingRemote`: padlock at 40% opacity + "Peer hasn't set up encryption".
- `rotated`: padlock with a rotation arrow overlay + "Key changed".

### 8.3 `SafetyNumberView`

```dart
class SafetyNumberView extends StatelessWidget {
  final String safetyNumber;     // "A93C F1B8 72DE" (pre-chunked)
  final bool peerOnline;         // informational only
}
```

Renders the monospaced 12-hex group centered, with copy button. No interactive verification — this is informational in v1.

---

## 9. Edge cases table

| Case | Behavior |
|---|---|
| Peer rotates keys mid-conversation | Next `GET /keys/{peer}` returns new `{id, public_key}`. Controller updates peer-key cache. Future messages encrypted to the new key. Prior messages decrypt using stored private keys for whichever `recipient_key_id` they reference. System bubble inserted (§6.3). |
| User rotates own keys mid-conversation | New outgoing messages use new pubkey as `recipient_key_id` for peer-side decrypt — NO, that's backwards. `recipient_key_id` is the **peer's** active key id at send-time. Own key rotation only affects: (a) future peer-to-me messages (they'll encrypt to the new key), (b) local store (active moves to rotated). |
| WS reconnect during conversation open | ReconnectingBanner shown ≥ 3 attempts. History is already fetched; we miss no `message.new` during the gap because on re-subscribe + resume, we refetch messages since `max(message.sent_at)` via `GET /messages?cursor=<last_seen>&direction=asc`. Phase 10 MVP: simpler — on reconnect of a subscribed conversation, fire a small "catch up" REST call for any missed messages. |
| Composing while offline | Enter → optimistic bubble with `pending` status. Secure-store the plaintext in `messages.pending.v1`. On reconnect, controller flushes queue. Order preserved. |
| Send fails permanently (e.g., conversation deleted mid-send) | Bubble `failed`. `AppDialog` once per session "This conversation is no longer available." Remove from pending. |
| Peer blocks / deletes account | Backend: `GET /conversations/{id}` still works (conversation row preserved); `GET /keys/{peer}` returns 404 (no active key). UI: keys-missing state; allow reading history. |
| Very long message (> 5000 chars plaintext) | Composer still accepts; ciphertext is < 10 KB typically. No cap. |
| Message with emoji / RTL / CJK | `bodyMedium` renders natively; bubble width flexes. Grapheme clustering via default Flutter TextSpan. No special case. |
| Decryption of a message whose `recipient_key_id` is not locally present | `decryptionError` bubble. Long-press → "Show details" reveals the key id. Never reveals ciphertext or tries to send it to a server. |
| Duplicate message.new for a message already in list | Ignored — list is a set keyed on `id`. |
| User taps a pending bubble to retry | No-op; retry only on `failed`. Design: pending bubbles are waiting on reconnect, not user action. |
| Session expires while on conversation screen | `sessionExpired` → `WsClient.dispose()` → route to `/login`. On re-login, screen mount fresh via go_router. |

---

## 10. Copy / strings (English baseline)

Put under `lib/l10n/intl_en.arb` (Phase 8 infra already supports).

```
messages.title = "Messages"
messages.empty.unreferred.headline = "You need a seller invite"
messages.empty.unreferred.subhead = "Messages unlock when a seller invites you."
messages.empty.customer.headline = "No messages yet"
messages.empty.customer.subhead = "Tap the chat icon on a store or order to start a conversation."
messages.empty.seller.headline = "No customer conversations yet"
messages.empty.seller.subhead = "When a customer messages you, it will appear here."
conversation.encrypted = "End-to-end encrypted"
conversation.hello.headline = "Say hello"
conversation.hello.subhead = "Messages in this conversation are end-to-end encrypted."
conversation.no_peer_key.banner = "{name} hasn't set up encryption yet. They need to open the app at least once."
conversation.composer.hint = "Message {first_name}…"
conversation.send_failed.retry = "Tap to retry"
conversation.queued.caption = "{n} queued · Sending when online"
conversation.decrypt_failed.inline = "🔒 Couldn't decrypt this message"
conversation.typing = "{name} is typing"
conversation.key_changed.body = "{name}'s encryption key has changed. Verify their identity to confirm this is expected."
conversation.key_changed.cta = "Verify"
security.reset.title = "Reset encryption keys?"
security.reset.body = "This generates a new key for all future messages on this device. Messages you've already received will still be readable here. Other people will see a 'key changed' notice the next time you message them."
security.reset.primary = "Reset"
security.reset.success = "Encryption keys reset. Your next message will use the new key."
security.verify.title = "Verify identity"
security.verify.instr = "Compare this with the number {name} sees on their device."
security.verify.copy = "Copy"
security.verify.explainer.cta = "How verification works"
reconnecting.banner = "Reconnecting…"
reconnecting.banner.offline = "You're offline. Messages will send when you're back."
```

---

## 11. Controller & provider shape

Riverpod `AsyncNotifier`s mirror Phase 9 patterns.

```dart
// conversations_controller.dart
class ConversationsController extends AsyncNotifier<List<ConversationView>> {
  Future<List<ConversationView>> build() async { /* GET /conversations; subscribe via wsClient; listen to message.new */ }
  Future<ConversationView> openOrCreate(String peerId) { /* POST /conversations */ }
  void handleMessageNew(MessageEvent e) { /* update/insert */ }
  void handleMessageRead(MessageReadEvent e) { /* increment read ack */ }
}

// conversation_controller.dart (scoped by conversationId)
class ConversationController extends FamilyAsyncNotifier<ConversationScreenState, String> {
  Future<ConversationScreenState> build(String id) async {
    /* GET /conversations/:id, GET /keys/peer, GET /messages?limit=50, decrypt, subscribe */
  }
  Future<void> send(String plaintext) { /* optimistic insert, encrypt, POST */ }
  void retry(String tmpMessageId) { /* re-send a failed */ }
  void setTyping(bool typing) { /* debounce + emit WS typing */ }
  Future<void> loadOlder() { /* cursor pagination */ }
}
```

The WS event handlers are wired at controller construction; `ref.onDispose` unsubscribes. Both controllers are `AutoDispose` with a 30 s keep-alive so quick back-and-forth navigation between the list and a conversation doesn't thrash.

---

## 12. Acceptance criteria (Phase 10 Frontend Engineer — messaging)

1. **ConversationsListScreen**
   - [ ] Loads `GET /conversations` on mount, subscribes to WS conversation channels automatically via `/ws` connect.
   - [ ] Renders `ConversationPreview` tiles in descending `last_message_at` order.
   - [ ] Unread count updates live on `message.new`.
   - [ ] Unreferred customer shows ADR-0007 empty state with **zero API calls** (assert via test).

2. **ConversationDetailScreen**
   - [ ] Fetches peer key, history, decrypts, renders inverted list.
   - [ ] Cursor pagination on scroll-up (load-older) with a subtle loader.
   - [ ] Sending a message shows optimistic bubble, transitions `sending → sent → delivered → read` as acks arrive.
   - [ ] Failed sends show `failed` status; tap bubble retries.
   - [ ] Typing indicator appears on `typing:true`, auto-clears after 5 s.
   - [ ] Date dividers render on 24 h gaps.
   - [ ] Keys-missing-local flow shows the modal once; after generating, screen resumes.
   - [ ] Key-change banner appears when peer's `key_version` increments.

3. **ChatBubble**
   - [ ] Supports all 7 states (§4.1) with correct icon and visual.
   - [ ] Widget file contains zero `ciphertext`/`nonce`/`ephemeralPublicKey` identifiers (grep test).
   - [ ] Semantics label composes `isMine ? 'You said' : '${peer} said' + text + timestamp + status`.

4. **Crypto service**
   - [ ] Round-trip test: `encryptFor(peerPub) → decryptWith(peerPriv)` returns original plaintext.
   - [ ] Rotation preserves old private keys under `keys.v1.rotated.{id}`.
   - [ ] Safety number deterministic across launches (given stable keys).
   - [ ] GCM tag failure → `decryptionError`, never crashes.

5. **Offline / queue**
   - [ ] Messages sent while offline persist to `flutter_secure_storage` and flush on reconnect in FIFO order.
   - [ ] A reboot between send and reconnect preserves queued messages.

6. **Verify identity**
   - [ ] Screen renders 12-hex safety number, copy button works, explainer bottom sheet opens.

7. **No ciphertext, anywhere**
   - [ ] Widget tests passing the REST `MessageEnvelope` JSON directly into any widget build → compile error (type mismatch). Only the crypto service may construct `String plaintext`.

8. **Accessibility**
   - [ ] All interactive widgets have semantics labels per §2.6 / §3.8.
   - [ ] Typing indicator, reconnecting banner, and status chip are `liveRegion: true`.

9. **Analytics hooks (Phase 12 placeholder)**
   - [ ] Call sites for `analytics.track('message_sent', {conversation_id})` etc. are present as no-op stubs; the analytics package is Phase 12.
