# Frontend Spec — 02 Component Library

**Audience:** Frontend Engineer building shared widgets under `lib/shared/widgets/`.

Every component entry includes: **purpose**, **variants**, **states**, **props**, and a Flutter widget suggestion. All components consume design tokens from `01-design-tokens.md`; none hard-code colors, font sizes, or spacing.

**Phase 8 implements:** Button, Input, Form Field Wrapper, Snackbar, Dialog, Empty State, Skeleton Loader, App Bar, Avatar + Badge.
**Specified now for Phase 9–11:** Card, List Tile, Chat Bubble, Map View (customer + internal), Bottom Nav Bar, FAB.

---

## 1. Button — `AppButton`

**Purpose:** primary action control, consistent across auth, forms, and CTAs.

**Variants**

| Variant | Background | Foreground | When |
|---|---|---|---|
| `primary` | `colorScheme.primary` | `onPrimary` | One per screen: the screen's main action |
| `secondary` | `colorScheme.surfaceVariant` | `onSurfaceVariant` | Non-primary action ("Cancel" in a pair) |
| `text` | transparent | `colorScheme.primary` | Inline actions, low emphasis |
| `destructive` | `colorScheme.error` | `onError` | Confirm delete, revoke, sign out from detail view |

**Sizes:** `sm` (h=36, `labelMedium`, horizontal padding 12), `md` (h=48, `labelLarge`, horizontal padding 16 — **default**), `lg` (h=56, `titleMedium`, horizontal padding 24). Full-width via `expand: true`.

**States table**

| State | Visual |
|---|---|
| default | As above |
| hover (web/desktop future) | 4% overlay of foreground on background |
| pressed | 10% overlay of foreground on background |
| focused (keyboard) | 2dp outline in `colorScheme.primary`, 2dp offset |
| disabled | 38% opacity, no ripple, `onPressed: null` |
| loading | Label hidden; `CircularProgressIndicator` (20dp, 2dp stroke) centered; button remains its current width; `onPressed: null` |

**Props**
```
variant: ButtonVariant (primary/secondary/text/destructive)
size: ButtonSize (sm/md/lg, default md)
label: String (required)
leadingIcon: IconData?
trailingIcon: IconData?
onPressed: VoidCallback?   // null = disabled
isLoading: bool = false
expand: bool = false        // full-width
semanticsLabel: String?     // falls back to label
```

**Flutter widget:** `ElevatedButton` / `FilledButton` / `TextButton` composed into one `StatelessWidget` that dispatches by variant. All use `Theme.of(context).buttonTheme` but override via the variant selector.

**Sketch**
```
[  leadingIcon   Label text   trailingIcon  ]
^-- primary filled                     ^-- secondary tonal
```

---

## 2. Input — `AppTextField`

**Purpose:** single-line text input for forms.

**Variants (by `keyboardType` / behavior):** `text`, `email` (auto-lowercase on commit, `emailAddress` keyboard, `autocorrect: false`), `password` (obscured with a suffix eye toggle), `numeric` (digits only; for postal/phone in later phases).

**States**

| State | Visual |
|---|---|
| default | 1dp `outline` border, `surface` bg, `onSurface` text |
| focused | 2dp `primary` border, caret `primary` |
| filled (non-empty, unfocused) | 1dp `outline` border, text at full opacity |
| disabled | 38% opacity, `surfaceVariant` bg, no caret |
| error | 2dp `error` border; error message announced and rendered below in form wrapper |
| loading (async validation, future) | trailing spinner replacing suffix icon |

**Props**
```
controller: TextEditingController
label: String                  // floating label
hint: String?
helperText: String?
errorText: String?             // drives error visual and Semantics
obscureText: bool = false      // password variant flips this via toggle
leadingIcon: IconData?
trailingIcon: Widget?
keyboardType: TextInputType
textInputAction: TextInputAction
autofillHints: List<String>?   // e.g. [AutofillHints.email]
onChanged / onSubmitted
semanticsLabel: String?
```

**Flutter widget:** wraps `TextField` with `InputDecoration` built from tokens. Password variant owns its `obscureText` state internally and exposes a `bool initiallyObscured = true`.

**Accessibility note:** `label` is the accessible name unless `semanticsLabel` is passed; error text is placed inside a `Semantics(liveRegion: true)` so VoiceOver/TalkBack announces it on appearance.

---

## 3. Form Field Wrapper — `AppFormField`

**Purpose:** consistent structure — label above, field in middle, helper/error below — so forms have stable spacing without every call-site re-doing `Column` + `Text` plumbing.

**Layout (top → bottom):**
```
Label (labelMedium, onSurfaceVariant) + optional "*" in error color
 [ 4dp gap ]
Input (AppTextField or any field widget via child slot)
 [ 4dp gap ]
Helper / error text (bodySmall, onSurfaceVariant OR error)
```

**Props**
```
label: String
required: bool = false   // renders "*" in error color after label
helperText: String?
errorText: String?       // takes priority over helperText
child: Widget            // usually AppTextField
```

**Note:** `errorText` passed here overrides `AppTextField.errorText`. Keep error state in one place (usually form-level `Notifier`), pass down.

---

## 4. Card — `AppCard`

**Purpose:** grouped content container. Used for product previews (Phase 9), order summary (Phase 9), conversation preview (Phase 10).

**Variants**

| Variant | Description |
|---|---|
| `default` | Static container. No ripple. |
| `interactive` | Tappable. InkWell ripple. Subtle elevation lift on press. |
| `selected` | Border 2dp `primary`, bg `primaryContainer` at 40% opacity. |

**Tokens:** elevation `elev1`, radius `radiusMd` (12), padding `space4` (16), bg `colorScheme.surface`.

**Props**
```
variant: CardVariant (default/interactive/selected)
onTap: VoidCallback?    // required if interactive
padding: EdgeInsets?    // defaults to space4
child: Widget
semanticsLabel: String? // for interactive
```

**Flutter:** `Material` + `InkWell` + `Padding`. Don't use raw `Card` — we want token-driven radius, not the Material default.

---

## 5. List Tile — `AppListTile`

**Purpose:** row in a vertical list. Dominant pattern for orders list, conversations list, admin user list, driver queue.

**Slots:** `leading` (avatar or icon, 40dp target), `title` (`titleMedium`), `subtitle` (`bodyMedium`, `onSurfaceVariant`, optional), `trailing` (badge, chevron, or timestamp).

**Variants**

| Variant | Visual |
|---|---|
| `default` | Row, 16dp side padding, 12dp vertical padding, optional bottom divider |
| `interactive` | Adds ripple and chevron trailing by default |
| `dense` | Reduced vertical padding to 8dp — for admin lists |

**States:** idle, pressed (4% overlay), disabled (38% opacity, no ripple).

**Props**
```
leading: Widget?
title: String
subtitle: String?
trailing: Widget?
onTap: VoidCallback?
showDivider: bool = true
dense: bool = false
badge: Widget?         // shortcut: place a Badge in trailing slot
semanticsLabel: String?
```

**Sketch**
```
[avatar]  Title text                              [•]
          Subtitle text · meta                    >
─────────────────────────────────────────
```

---

## 6. Chat Bubble — `ChatBubble` (Phase 10)

**Purpose:** render a single E2E message. **Input is decrypted plaintext** (decryption happens in the messaging feature before the widget is built). The widget never sees, logs, or exports ciphertext or plaintext outside its own render tree.

**Variants**

| Variant | Alignment | Color |
|---|---|---|
| `mine` | Right | bg `primary`, fg `onPrimary` |
| `theirs` | Left | bg `surfaceVariant`, fg `onSurfaceVariant` |

**States**

| State | Visual |
|---|---|
| sending | 60% opacity, small clock icon trailing |
| sent | full opacity, single check icon |
| read | full opacity, double-check icon in `primary` (mine) / hidden (theirs) |
| failed | red exclamation icon, tap to retry |

**Tokens:** radius `radiusMd` with one asymmetric corner (bottom-right 4dp for `mine`, bottom-left 4dp for `theirs`), max width 72% of container, padding 12/16.

**Props**
```
text: String                    // already decrypted
isMine: bool
sentAt: DateTime
status: MessageStatus (sending/sent/read/failed)
onRetry: VoidCallback?          // only used when status=failed
```

**Hard rule:** the widget must **not** accept a `ciphertext` field. The contract is: messaging feature decrypts, then builds bubbles. This is a design-time guardrail to make accidental ciphertext display impossible.

---

## 7. Map View — **TWO distinct components** (Phase 10, ADR-0014)

> **Invariant:** the asymmetric-visibility rule (ADR-0014) is enforced at the widget level as two separate widgets, NOT one widget with a `role` flag. A Flutter developer working on the customer flow should be unable to import the internal widget by accident, and vice versa. Place them in separate files under separate feature folders so linting / code review surfaces any cross-import.

### 7.1 `CustomerDeliveryView` — customer-facing

**Location:** `lib/features/tracking/customer/widgets/customer_delivery_view.dart`

**Purpose:** show the customer the **status** and **ETA** of their delivery without ever rendering location data.

**What it renders:**
- A **static** map pin at the customer's own drop-off address (destination only).
- A large status chip above the map: `OUT FOR DELIVERY` / `DELIVERED` / `PREPARING`.
- An ETA badge: "Arriving in ~12 min" (from `delivery.eta` event, `CustomerDeliveryView` schema `current_eta_seconds`).
- A subtle last-updated timestamp ("updated just now").

**What it never renders:**
- Driver or seller coordinates.
- Any breadcrumb polyline.
- Driver avatar live position.

**Props (strict):**
```
status: DeliveryStatus     // from CustomerDeliveryView DTO
etaSeconds: int?           // null → "ETA not available"
lastUpdatedAt: DateTime
destinationLabel: String   // customer's address, for map pin caption
```

**NOT in the prop set** (and enforced by the DTO being `extra="forbid"` server-side per Phase 7): `driverLat`, `driverLng`, `sellerLat`, `sellerLng`, `breadcrumbTrail`, `driverId`.

### 7.2 `InternalDeliveryView` — driver / seller / admin only

**Location:** `lib/features/tracking/internal/widgets/internal_delivery_view.dart`

**Purpose:** show the delivery operator the customer's drop-off location and the live driver breadcrumb.

**What it renders:**
- Interactive map centered on the driver's current position.
- Customer drop-off pin at destination.
- Live breadcrumb polyline (driver's historical `delivery.location` events).
- Driver current position as a moving marker.
- Action bar: "Mark delivered" button (driver role), distance and duration counters.

**Props:**
```
orderId: UUID
customerDropOff: LatLng
driverCurrent: LatLng?           // from delivery.location events
breadcrumbs: List<LatLng>
durationSoFar: Duration?
distanceMeters: int?
onMarkDelivered: VoidCallback?   // driver-only; seller/admin = null
```

**Guardrail:** the build-time check is a `barrel` export pattern — `features/tracking/customer/index.dart` and `features/tracking/internal/index.dart` are the only exports. The customer shell imports from `customer/index.dart` and has no route that imports from `internal/`. Code review rule: any PR that imports `internal/` into a `customer/` file is rejected.

### 7.3 Provider choice (D4, open)

Placeholder — pick in Phase 10. Candidates: `flutter_map` (OSM, free, offline-friendly) vs `google_maps_flutter` (better native feel, Google ToS, requires API key). The two view widgets are written against an abstract `MapProvider` interface so the concrete pick is a single file swap.

---

## 8. Snackbar / Toast — `AppSnackbar`

**Purpose:** transient feedback at the bottom of the screen, 4 seconds default.

**Variants**

| Variant | Icon | Bg | Fg |
|---|---|---|---|
| `info` | `Icons.info_outline` | `inverseSurface` | `onInverseSurface` |
| `success` | `Icons.check_circle` | `success` ext | `onSuccess` ext |
| `error` | `Icons.error_outline` | `error` | `onError` |

**Props**
```
variant: SnackbarVariant
message: String
actionLabel: String?   // optional "Retry" / "Undo"
onAction: VoidCallback?
duration: Duration = 4s
```

Expose as `context.showAppSnackbar(...)` extension that wraps `ScaffoldMessenger.of(context).showSnackBar`. Never show more than one concurrently (dismiss-on-new).

---

## 9. Dialog / Modal

Two primitives:

### 9.1 `AppDialog` — centered modal

Used for confirmations, errors with retry, short forms.

**Structure:** title (`titleLarge`), body (`bodyMedium`), 1–2 action buttons right-aligned. Radius `radiusMd`, elevation `elev4`, scrim 40% black.

**Props**
```
title: String
body: Widget              // allow rich content (e.g. list)
primaryAction: (String label, VoidCallback onPressed, {bool destructive})
secondaryAction: (String label, VoidCallback onPressed)?
dismissible: bool = true
```

### 9.2 `AppBottomSheet` — bottom-anchored sheet

Used for longer forms, multi-step disclosures (e.g. signup role chooser, later: order detail drawer).

**Variants:** `fullScreen` (near-fullscreen on mobile, dragging down dismisses) vs `partial` (takes ~60% height, expandable).

**Structure:** top handle (4dp × 32dp outlineVariant bar), title row, scrollable content, action row sticky at bottom.

**Props**
```
title: String?
content: Widget
actions: Widget?
dragDismissible: bool = true
expandToFullScreen: bool = false
```

---

## 10. Empty State — `AppEmptyState`

**Purpose:** first-class surface for "no data yet" OR "you don't have access to see data" (referral-scoped visibility — see §10.1 below).

**Structure (vertical center):**
```
[  Icon (32dp, onSurfaceVariant)  ]
[ 16dp gap ]
[ Headline (headlineMedium)       ]
[ 8dp gap ]
[ Subhead (bodyMedium, onSurfaceVariant, max 320dp width) ]
[ 24dp gap ]
[ Optional CTA button (AppButton primary) ]
```

**Props**
```
icon: IconData
headline: String
subhead: String?
ctaLabel: String?
onCtaPressed: VoidCallback?
```

### 10.1 Referral-scoped visibility empty state (ADR-0007)

For the unreferred customer on the Discover tab (Phase 9 wires it; Phase 8 placeholder already uses it):

```
icon:      Icons.lock_outline
headline:  "You need a seller invite"
subhead:   "This marketplace is invite-only. Ask a seller for their referral
            link, then open it to unlock their store."
ctaLabel:  "How invites work"   → opens info bottom sheet
```

**Explicitly NOT:** "No products found" / "Nothing here yet" / a search-zero-results layout. The copy must convey access gating, not absence of inventory.

---

## 11. Skeleton Loader — `AppSkeleton`

**Purpose:** placeholder shape during async load. Used on list screens to avoid spinner-flash on fast networks.

**Primitives:** `SkeletonBox(width, height, radius)`, `SkeletonLine(width)`, `SkeletonTile()` (a list-tile-shaped skeleton).

**Animation:** a diagonal shimmer from `surfaceVariant` base to `surface` highlight, 1.2s loop. Disabled under `disableAnimations`.

**Props on `SkeletonBox`**
```
width: double?       // null = double.infinity
height: double
radius: double = radiusSm
```

Usage: lists render 5 `SkeletonTile`s while the `AsyncValue` is `loading`. Replace in-place on `data`.

---

## 12. Avatar + Badge

### 12.1 `AppAvatar`

Circular (`radiusPill`), sizes `sm` (32dp), `md` (40dp — default), `lg` (64dp — profile screen).

**Props**
```
imageUrl: String?         // null → initials fallback
initials: String          // "AB" derived from name
size: AvatarSize = md
role: UserRole?           // if present, renders RoleBadge as overlay bottom-right
```

**Fallback:** when `imageUrl` is null or fails, render initials on `primaryContainer` bg with `onPrimaryContainer` text.

### 12.2 `RoleBadge`

Small pill, `radiusPill`, height 20dp, horizontal padding 8dp, `labelSmall` text, background/foreground from the `RoleBadgeColors` theme extension.

**Props**
```
role: UserRole (admin/seller/driver/customer)
size: BadgeSize = sm (default) | md (for profile header)
```

Never show a `customer` badge in customer-facing UI (it's redundant and clutters); use it in admin screens only. `admin`, `seller`, `driver` badges are always safe to show.

---

## 13. App Bar — `AppTopBar`

**Purpose:** screen header. Used on every non-root route and on role home shells (with the role's title).

**Structure:** leading (back or menu), title (`titleLarge`, single line ellipsized), trailing (up to 2 icon buttons or one overflow menu).

**Variants**

| Variant | Behavior |
|---|---|
| `default` | Flush with content, elevation `elev0` at scroll offset 0, rises to `elev2` at scroll > 4dp |
| `large` | Double-height with large title (`headlineSmall`) that collapses on scroll — Phase 11 admin screens |
| `modal` | Leading is a close "X", not a back arrow — used inside bottom sheets and full-screen dialogs |

**Props**
```
title: String
leading: Widget?              // overrides default back/close
trailing: List<Widget> = []   // max 2 widgets
variant: TopBarVariant = default
onBack: VoidCallback?         // defaults to Navigator.maybePop
scrollController: ScrollController?  // for default elevation rise
```

---

## 14. Bottom Nav Bar — `AppBottomNav` (Phase 9)

**Purpose:** primary navigation within a role shell.

**Layout:** 3–4 tabs, 56dp tall, `surface` bg with top hairline `outlineVariant`. Active tab = filled icon + label in `primary`; inactive = outline icon + label in `onSurfaceVariant`.

**Props**
```
currentIndex: int
items: List<AppBottomNavItem>   // icon (outline + filled), label, semanticsLabel
onTap: ValueChanged<int>
```

**Role-specific item sets:** defined in `03-role-shells.md`.

**Note:** `NavigationBar` (Material 3) is the Flutter base; wrap to consume our tokens and to enforce 44×44 minimum target.

---

## 15. FAB — `AppFab`

**Purpose:** a single primary role action per shell (compose message, add product, etc.).

**Variants:** `regular` (56dp), `extended` (pill with label + icon, for primary actions that benefit from a label).

**Props**
```
icon: IconData
label: String?          // only for extended
onPressed: VoidCallback?
heroTag: Object?        // disambiguate when multiple shells in memory
```

**Placement:** bottom-right, 16dp inset. When a `AppBottomNav` is present, FAB floats above nav by 16dp.

---

## 16. Cross-cutting rules

- No component accepts a raw color `int` or hex `String` — only `Color` derived from theme or a `ThemeExtension`.
- No component accepts a raw `Duration` for animation — use `AppMotion.quick / standard`.
- Every interactive component accepts an optional `semanticsLabel` and uses `label` as fallback.
- Loading state is a component property (`isLoading`, `SkeletonBox`), never a sibling widget swapped in by screens — keeps accessibility announcements colocated.
- Destructive variants require a confirmation `AppDialog` before dispatch, without exception.
