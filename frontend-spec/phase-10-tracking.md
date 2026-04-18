# Frontend Spec — Phase 10 Delivery Tracking

**Phase:** 10 — UI/UX Designer deliverable (Frontend C).
**Audience:** Frontend Engineer implementing delivery tracking UI for customer, driver, and seller (self-deliver) roles.
**Scope:** two **distinct** widget trees per ADR-0014. Customer view is coord-free status + ETA only. Driver/seller view is an internal map with live driver position, route, breadcrumbs, and delivered-action.

This doc extends `phase-10-overview.md`. The WebSocket lifecycle is specified in `phase-10-realtime.md`; this doc treats the WS client as a dependency.

**D4 decision:** **Mapbox** (per C-G9 in overview). Driver/seller views use `mapbox_maps_flutter`. The customer view does not import any map SDK.

---

## 0. Backend contract recap (tracking endpoints)

Per Phase 7 shipped (see `docs/phase-7-notes.md`):

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/deliveries/{order_id}/location` | driver / seller / admin write lat/lng/eta/distance. Only while order is `out_for_delivery`. Before OFD or after `delivered` → `409 DELIVERY_NOT_ACTIVE`. Customer → 403. Stranger → 404. Rate limit 600/min. |
| `GET /api/v1/deliveries/{order_id}/track` | Returns `InternalDeliveryView` (driver/seller/admin) with coords, or `CustomerDeliveryView` (customer) without coords. Non-participant → 404. |
| `PATCH /api/v1/admin/deliveries/{order_id}` | Admin reassign driver / override metrics. Phase 11. |
| `/ws?token=<jwt>` + `{type:"subscribe", delivery_order_id}` | Subscribe to delivery events. Role bucket drives which events get delivered. |

**Event types** (shipped in Phase 7):

| Event | Payload | To |
|---|---|---|
| `delivery.location` | `{order_id, lat, lng, at}` | internal bucket only (driver, seller, admin) |
| `delivery.eta` | `{order_id, eta_seconds, eta_updated_at}` | internal + customer |
| `delivery.status` | `{order_id, status, started_at?, delivered_at?}` | internal + customer |

`CustomerDeliveryView` payload shape (exactly these fields, Pydantic `extra="forbid"`):
```
order_id, status, eta_seconds?, eta_updated_at?, started_at?, delivered_at?, delivery_address
```

`InternalDeliveryView` adds: `driver_id?, seller_id, last_known_lat?, last_known_lng?, last_known_at?, distance_meters?, duration_seconds?`.

---

## 1. Screen inventory

| Route | Screen | Widget tree |
|---|---|---|
| `/home/customer/orders/:orderId/tracking` | CustomerTrackingScreen | `lib/features/tracking/customer/**` |
| `/home/seller/orders/:orderId/tracking` | SellerTrackingScreen | `lib/features/tracking/seller/**` |
| `/home/driver/orders/:orderId/tracking` | DriverTrackingScreen (Phase 11 shell; widget tree built now) | `lib/features/tracking/driver/**` |

Plus the Phase 9 customer order detail **already** contains a `CustomerDeliveryStatusWidget` (see `phase-9-components-diff.md` §9) that Phase 10 promotes to a `CustomerTrackingView` (the full-screen version). The inline widget on the order detail remains; tapping it opens the full tracking screen.

---

## 2. Customer Tracking — `/home/customer/orders/:orderId/tracking`

**Purpose:** give the customer everything they're entitled to see — status, ETA, destination, delivery timeline — and not one byte more.

**NO MAP. NO COORDINATES. NO Mapbox.**

### 2.1 Layout

```
AppTopBar(title: "Tracking", leading: back, trailing: [chat_bubble_outline → conversation with seller])

Body (scrollable, single column, padding space4):
  [big status tile]
    AppCard(default, padding: space5):
      Row(align: center, gap: space4):
        Icon (48dp, status-specific — see table below)
        Column:
          Text(statusHumanLabel, headlineSmall)
          Text(subhead, bodyMedium, onSurfaceVariant)
      if status == out_for_delivery:
        [space4]
        Container(radiusPill, tertiaryContainer bg, padding 10/16):
          Row: Icons.schedule + Text(etaCopy, titleMedium onTertiaryContainer)
        // "Arriving in ~12 min" OR "Arrival time not available yet"
      Text("Last updated {relativeTime}", bodySmall onSurfaceVariant)

  [space5]

  [timeline]
    OrderStatusTimeline(  // reused from Phase 9
      currentStatus: order.status,
      placedAt: order.placed_at,
      acceptedAt: ..., preparingAt: ..., outForDeliveryAt: ..., deliveredAt: ..., completedAt: ...,
    )

  [space5]

  [destination card]
    AppCard(default):
      Row: Icons.place_outlined + Text("Delivery address", labelMedium)
      [space2]
      Text(formattedAddress, bodyMedium)
      // the CUSTOMER's own address, from order.delivery_address

  [space5]

  [seller block]
    AppCard(default):
      AppListTile(
        leading: AppAvatar(md, seller),
        title: seller.display_name,
        subtitle: store.name,
        trailing: Icons.chat_bubble_outline → conversation,
      )
```

No map tiles. No driver avatar. No distance counter. No breadcrumbs. No "call driver" CTA.

### 2.2 Status → copy

| Status | Icon | Headline | Subhead |
|---|---|---|---|
| `pending` | `receipt_long_outlined` | "Waiting for seller" | "Your order is placed and waiting for the seller to accept." |
| `accepted` | `check_circle_outline` | "Order accepted" | "The seller will start preparing soon." |
| `preparing` | `inventory_2_outlined` | "Preparing your order" | "The seller is getting your order ready." |
| `out_for_delivery` | `local_shipping_outlined` | "Out for delivery" | "Your order is on the way." |
| `delivered` | `task_alt` | "Delivered" | "Your order was delivered at {formatDateTime(delivered_at)}." |
| `completed` | `verified_outlined` | "Completed" | "Thanks for confirming receipt." |
| `cancelled` | `cancel_outlined` | "Cancelled" | "This order was cancelled." |

### 2.3 ETA copy

- `eta_seconds` null: "Arrival time not available yet".
- `eta_seconds <= 60`: "Arriving any minute".
- `60 < eta_seconds < 60*60`: "Arriving in ~{minutes} min".
- `eta_seconds >= 60*60`: "Arriving in ~{hours} h {minutes} min".

### 2.4 Last-updated copy

- Fallback to `eta_updated_at` when present; else `updated_at` of the order.
- "just now" (< 60 s), "1 min ago", "5 min ago", "12 min ago", "about an hour ago", else `formatDateTime()`.

Updated in real-time: the screen ticks every 30 s to refresh relative strings (local UI-only timer, NOT a REST poll).

### 2.5 States

| State | Visual |
|---|---|
| loading | `SkeletonBox(h=120)` header + `SkeletonBox(h=180)` timeline + `SkeletonTile` destination + `SkeletonTile` seller |
| data | §2.1 |
| 404 (order not found / not own) | `AppEmptyState(icon: error_outline, headline: "Order not found", ctaLabel: "Back to orders")` |
| network error | `AppEmptyState(icon: wifi_off, ctaLabel: "Retry")` |
| WS disconnected | `ReconnectingBanner` above the body |
| not-yet-OFD (status in `{pending, accepted, preparing}`) | Body renders exactly as §2.1, minus the ETA badge. The `GET /deliveries/{id}/track` still works and may return a `CustomerDeliveryView` with no ETA. |
| cancelled | Status tile + timeline show cancelled; destination and seller blocks still visible. No ETA. |
| post-delivered / completed | Status tile shows delivered time; ETA badge hidden; destination and seller blocks visible; an inline **"Rate this delivery"** hint (disabled, "Reviews coming soon" — per Phase 9 B-G2). |

### 2.6 API + WS

On mount:
1. `GET /api/v1/orders/{order_id}` — baseline order info (items, totals, delivery_address). Treated as source of truth for address and seller identity.
2. `GET /api/v1/deliveries/{order_id}/track` — `CustomerDeliveryView`. Drives ETA and timeline timestamps.
3. `wsClient.subscribe(deliveryChannel(order_id))`. Listens for:
   - `delivery.status` → update local status, re-render status tile and timeline. If status crosses into `delivered` or `completed`, refetch `/orders/{id}` once to get final timestamps.
   - `delivery.eta` → update ETA copy and last-updated.
   - **NOT** `delivery.location` — not subscribed for customer bucket; even if received, controller must not render. See §5.
4. On unmount: unsubscribe.

### 2.7 Screen navigation interplay

- Back button → `/home/customer/orders/{order_id}` (the Phase 9 order detail).
- Entry points: (a) inline `CustomerDeliveryStatusWidget` tap on order detail, (b) direct deep-link (future push notification handler Phase 12).

### 2.8 `CustomerTrackingView` widget (the reusable piece)

**Location:** `lib/features/tracking/customer/widgets/customer_tracking_view.dart`.

**Props (MANDATORY SHAPE — extends `CustomerOrderDeliveryProps` from Phase 9 with timeline fields):**

```dart
class CustomerTrackingProps {
  final String orderId;
  final DeliveryStatus status;
  final int? etaSeconds;
  final DateTime? etaUpdatedAt;
  final DateTime? startedAt;          // OFD started
  final DateTime? deliveredAt;
  final DateTime? placedAt;
  final DateTime? acceptedAt;
  final DateTime? preparingAt;
  final DateTime? completedAt;
  final DateTime? cancelledAt;
  final String destinationLabel;      // customer's own formatted address
  final SellerPreview seller;         // {id, display_name, avatar_url?, store_name}

  // HARD INVARIANT (ADR-0014):
  // no driverLat, driverLng, sellerLat, sellerLng
  // no breadcrumbs, distanceMeters, driverId
  // no geo-anything. Verified by grep test.

  const CustomerTrackingProps({...});
}
```

Implementation uses only Flutter core + Phase 9 components. Build-time check:

```dart
// lib/features/tracking/customer/widgets/customer_tracking_view.dart
// ADR-0014: this file and all siblings under customer/ must not reference
// coordinates or any map SDK. See test/adr_0014_tracking_isolation_test.dart.
```

### 2.9 Accessibility

- Status tile: `Semantics(liveRegion: true, label: "${statusLabel}, ${etaLabel ?? ''}, last updated ${relativeTime}")`.
- Timeline: reused Phase 9 widget's semantics.
- Destination card: `Semantics(label: "Delivery address: ${formattedAddress}")`.
- Seller tile: inherits `AppListTile` semantics; adds "Open conversation" hint on trailing.

### 2.10 Edge cases

| Case | Behavior |
|---|---|
| `delivery.status` event for `delivered` arrives before the REST `/track` returns the `delivered_at` | Optimistic UI: flip status immediately using event's `delivered_at`. Background refetch `/orders/{id}` for final authority. |
| ETA jumps backward then forward (driver app glitch) | Render whatever the latest event says. No smoothing. |
| Status transitions to `cancelled` while customer is on the screen | Status tile flips to cancelled copy. ETA and last-updated hidden. |
| Customer navigates to tracking for an order that is still `pending` | `/track` returns a `CustomerDeliveryView` with status=pending, no ETA. Screen renders minimal state. |
| Customer is not the order owner (route injected via deep link from wrong context) | `GET /orders/{id}` returns 404. `AppEmptyState` "Order not found". |
| `delivery.location` event somehow hits a customer-side handler | **Controller must drop it silently.** Tested by `adr_0014_tracking_isolation_test.dart` — unit test injects a `delivery.location` event into `CustomerTrackingController` and asserts state is unchanged. |

---

## 3. Internal Tracking — `/home/seller/orders/:orderId/tracking` and `/home/driver/orders/:orderId/tracking`

**Purpose:** give the driver (or self-delivering seller) a live map to navigate, mark the delivery as delivered, and see distance/duration counters.

**Map provider:** Mapbox. SDK: `mapbox_maps_flutter` (>= 2.0). Access token loaded from `--dart-define=MAPBOX_ACCESS_TOKEN=...` at build time and read via `lib/features/tracking/_shared/mapbox_config.dart` (this file is the sole point of SDK access; any other file that imports Mapbox is rejected in PR review).

**Widget tree location:**
- `lib/features/tracking/driver/widgets/driver_map_view.dart`
- `lib/features/tracking/seller/widgets/seller_map_view.dart`
- shared inner widgets (e.g., `MapboxDeliveryMap`) under `lib/features/tracking/_internal_shared/` — note **`_internal_shared`**, with a leading underscore to distinguish from the **customer-safe shared types** in `lib/features/tracking/shared/`. The underscore-prefixed folder is tracked by the grep invariant: it may contain coords, and customer files must not import from it.

### 3.1 Layout

```
AppTopBar(title: "Delivery for Order #${id.substring(0,8)}", trailing: [chat → seller↔customer conversation])

Body: Stack (fullscreen map + overlays)
  MapboxMap (full-screen):
    style: mapbox/streets-v12 (or dark variant on dark theme)
    camera: fit bounds of {driverCurrent, customerDropOff}, padding 16% top, 40% bottom, 10% sides
    pins:
      - destination pin (Icons.place, secondaryContainer color) at order.delivery_address geocoded
      - driver pin (custom marker: filled circle primary, white inner dot) at driverCurrent
    polyline:
      - breadcrumb trail from accumulated delivery.location events (local, NOT persisted server-side)
      - stroke primary at 60% opacity, width 4dp
      - max 50 most recent points; older trimmed
    userLocation: disabled (driver app does this itself — but tracking UI shouldn't duplicate)
  
  [top sheet: order summary]
    Positioned(top: 16, left: 16, right: 16):
      AppCard(default, padding: space3):
        Row:
          AppAvatar(sm, customer)
          Column: customer.display_name + bodySmall(order.total_minor formatted)
          Spacer
          OrderStatusChip(out_for_delivery, size: md)
  
  [bottom action sheet: delivery controls]
    Positioned(bottom: 0, left: 0, right: 0):
      Container(surface, elevation elev4, radiusLg top, padding space4):
        Row (metrics):
          MetricTile("Distance", formatKmOrM(distanceMeters))
          MetricTile("Duration", formatDuration(durationSoFar))
          MetricTile("ETA", formatEta(etaSeconds))
        [space4]
        AppButton(primary, expand, size: lg, label: "Mark delivered", onPressed: _confirmDeliver)
        [space2]
        AppButton(secondary, expand, label: "Open navigation", onPressed: _openNativeMaps)   // uses url_launcher
        [if driver, not seller]
          [space2]
          AppButton(text, expand, label: "Report issue", onPressed: ...)   // Phase 12; disabled in Phase 10
```

### 3.2 States

| State | Visual |
|---|---|
| loading (first fetch) | Static map placeholder `Container(surfaceVariant)` with centered `CircularProgressIndicator`; top/bottom sheets show skeletons |
| data, awaiting first location event | Map shows only destination pin; bottom sheet "Waiting for driver location…" |
| data, live | §3.1 |
| 404 / 403 | `AppEmptyState(icon: error_outline, headline: "Not your delivery", ctaLabel: "Back")` — no copy that leaks ownership |
| 409 on `Mark delivered` (already delivered) | Swallow silently per ADR-0003; refetch `/track`, snackbar `info` "Already marked delivered" (optional — the refetch will flip UI to delivered copy) |
| WS disconnected | `ReconnectingBanner` above the top sheet; map continues to render last-known state |
| delivered | Entire bottom sheet replaced with a "Delivered at {formatDateTime}" confirmation card + "Back to order" button |
| cancelled | Entire screen replaced with `AppEmptyState(icon: cancel_outlined, "Delivery cancelled", ctaLabel: "Back")` |

### 3.3 API + WS

On mount:
1. `GET /api/v1/orders/{order_id}` — validate participant, get order + address.
2. `GET /api/v1/deliveries/{order_id}/track` — `InternalDeliveryView` → seeds map position (if `last_known_lat/lng` present), metrics, ETA.
3. Geocode the `delivery_address` to a LatLng via Mapbox Geocoding API (cached in-memory). If geocoding fails, fall back to `last_known_lat/lng` only.
4. `wsClient.subscribe(deliveryChannel(order_id))`. Listens for:
   - `delivery.location` → append to breadcrumb, move driver pin (animated over `motionStandard`), update `distanceMeters` from payload if server sends it (Phase 7 MVP uses running-max; client ignores).
   - `delivery.eta` → update ETA metric.
   - `delivery.status` → if `delivered`, flip to delivered layout and stop listening for location.
5. Unmount: unsubscribe.

**Driver: writing location.** The driver's own device streams its GPS at 1 Hz (foreground) to `POST /api/v1/deliveries/{order_id}/location`. That is a platform-integration job (foreground-service on Android, `CLLocationManager` on iOS) spec'd separately in `phase-10-realtime.md` §7 and implemented in the driver app shell. The tracking widget consumes the server broadcasts just like the seller/admin does; it does **not** write to the POST endpoint from the widget itself (that's the driver-location-service's job).

**Self-deliver seller: writing location.** Same path, same POST. Seller shell includes the location-stream service behind a "Start sharing my location" affordance. No silent background tracking.

### 3.4 "Mark delivered" flow

1. Tap `Mark delivered` → `AppDialog`:
   - Title: "Mark this order as delivered?"
   - Body: "The customer will be notified. You can't undo this."
   - Primary (destructive flavor only for color; label is "Mark delivered"): fires POST.
   - Secondary: "Cancel".
2. `POST /api/v1/orders/{order_id}/delivered`.
3. On 200: flip UI to delivered state. WS `delivery.status` will also arrive — dedupe.
4. On 409 (`DELIVERY_ALREADY_STARTED` or any idempotent re-hit): swallow, refetch `/track`, UI converges. Per ADR-0003.
5. On 403 / 404: `AppDialog` error, pop.
6. On network error: retain the confirm modal open with a `AppButton.isLoading=true`; auto-retry once.

### 3.5 Mapbox integration details

- **Style URLs:** `mapbox://styles/mapbox/streets-v12` (light), `mapbox://styles/mapbox/dark-v11` (dark). Switched by `Theme.of(context).brightness`.
- **Camera animation:** `motionStandard = 250 ms easeOutCubic` for repositioning; no animation when `MediaQuery.disableAnimations == true`.
- **Attribution:** Mapbox ToS requires attribution. Place in bottom-left, small; align with our `bodySmall` onSurfaceVariant.
- **Offline:** if Mapbox can't load tiles (no connectivity), the pins and polyline render on a `surfaceVariant` fallback with a centered caption "Map unavailable offline. Driver position and breadcrumbs still update."
- **Marker icons:** custom Flutter widgets serialized to bitmap via `mapbox_maps_flutter`'s `PointAnnotationOptions.image`. Use:
  - Destination: 32px circle with `Icons.place` filled `secondaryContainer` bg, `onSecondaryContainer` fg.
  - Driver: 36px circle with `primary` bg, 12px inner white dot, 8px white ring.
- **Route line:** polyline from breadcrumb list; no routing API (we're not computing turn-by-turn). If the driver app wants turn-by-turn, they open native maps via §3.1 "Open navigation" → `url_launcher` with `maps:` or `geo:` URI.

### 3.6 Geocoding of `delivery_address`

- Use Mapbox Geocoding API: `GET https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded-address}.json?access_token=...`.
- Cache results keyed on the address string in memory for the life of the session.
- If geocoding returns no result: show the destination pin at the map center with a caption "Approximate location"; rely on the driver reading the text address in the top sheet.

**Important:** the customer's address is visible to the driver/seller. This is fine — it's how delivery works. What the customer is protected from is seeing the *driver's* location, not vice versa.

### 3.7 Metrics

- **Distance**: server-provided `distance_meters` (Phase 7 MVP uses running max; acceptable for UI). Formatted `formatKmOrM(m)` → "1.2 km" / "340 m".
- **Duration**: computed client-side from `started_at` (from `delivery.status` event or `/track` payload) to `now()`. Updates every second.
- **ETA**: server-provided `eta_seconds`. Formatted per §2.3.

### 3.8 Accessibility

- The Mapbox map is **not** directly accessible via screen reader (it's a canvas).
- The top sheet + bottom sheet provide a full text-equivalent: "Delivery to ${customer}, total ${money}. Out for delivery. Driver position updated ${relativeTime}. Distance ${distance}. Duration ${duration}. ETA ${eta}."
- `Mark delivered` button: `Semantics(button: true, label: "Mark delivered, final action")`.
- `Open navigation` button: `Semantics(button: true, label: "Open in native maps")`.

### 3.9 Props

```dart
class DriverMapView extends StatelessWidget {
  final InternalDeliveryView delivery;           // from /track
  final OrderSummary order;                      // from /orders/:id
  final LatLng? destination;                     // geocoded
  final LatLng? driverCurrent;                   // from last delivery.location
  final List<LatLng> breadcrumbs;                // rolling max 50
  final Duration? durationSoFar;
  final int? etaSeconds;
  final int? distanceMeters;
  final VoidCallback? onMarkDelivered;           // null = disabled (e.g., seller admin view, delivered)
}
```

`SellerMapView` is literally `DriverMapView(onMarkDelivered: ...)` — same widget, different role gating on the `Mark delivered` path (seller can mark delivered only when self-delivering, i.e., `deliveries.driver_id == seller_id`). The seller shell provides the gating.

---

## 4. Component specs added in Phase 10 (tracking)

### 4.1 `CustomerTrackingView` — see §2.8.

### 4.2 `DriverMapView` / `SellerMapView` — see §3.9.

### 4.3 `MapboxDeliveryMap` (internal shared)

**Location:** `lib/features/tracking/_internal_shared/mapbox_delivery_map.dart`.

The low-level Mapbox wrapper that draws destination pin + driver pin + polyline, animates on prop change, and handles dark/light style switching. Used by both `DriverMapView` and `SellerMapView`. **Not** imported by anything under `customer/`.

```dart
class MapboxDeliveryMap extends StatefulWidget {
  final LatLng? driver;
  final LatLng? destination;
  final List<LatLng> breadcrumbs;
  final MapStyle style;
  final ValueChanged<MapboxMapController>? onMapCreated;
}
```

### 4.4 `MetricTile` (internal shared)

Small tile for the bottom sheet: label + value, vertical layout, no card. `labelSmall` onSurfaceVariant + `titleMedium` onSurface.

---

## 5. ADR-0014 enforcement (widget-level)

This section is the authoritative spec for the Phase 10 tracking invariant tests.

### 5.1 Folder rule

```
lib/features/tracking/
  customer/             ← customer-visible; NO coords, NO Mapbox
  driver/               ← internal; Mapbox OK
  seller/               ← internal; Mapbox OK
  _internal_shared/     ← internal; Mapbox OK (shared by driver + seller)
  shared/               ← role-agnostic, NO coords (e.g., status enum, human-label fns)
```

### 5.2 Grep test — `test/adr_0014_tracking_isolation_test.dart`

Reads every `*.dart` file under `lib/features/tracking/customer/` and asserts it contains **none** of the following tokens (case-insensitive):

```
lat
lng
latitude
longitude
mapbox
maplibre
google_maps_flutter
LatLng
Position       (the Mapbox Position class)
breadcrumb
driver_location
driverLat
driverLng
sellerLat
sellerLng
distance_meters
distanceMeters
package:mapbox_maps_flutter
package:flutter_map
package:google_maps_flutter
```

**Exception list** (Dart words that are legitimate):
- `translate`, `translation`, `latency` — none contain `lat` as a full token, so a word-boundary regex `\blat\b` is used.
- The test uses regex word boundaries: `\blat\b`, `\blng\b`, `\blatitude\b`, `\blongitude\b`, `\bLatLng\b`, etc.
- `mapbox` / `maplibre` / `google_maps_flutter` are matched as substrings — they have no valid reason to appear in `customer/`.

### 5.3 Import-boundary test — same test file

Parses each `*.dart` file's `import` directives and asserts:

- No file under `lib/features/tracking/customer/` imports from:
  - `lib/features/tracking/driver/`
  - `lib/features/tracking/seller/`
  - `lib/features/tracking/_internal_shared/`
  - any `package:mapbox_maps_flutter` or alternative map SDK
- No file under `lib/features/tracking/driver/` or `lib/features/tracking/seller/` imports from `lib/features/tracking/customer/` (for symmetry; also prevents internal files reusing customer copy they shouldn't).
- `lib/features/tracking/shared/` may be imported by either side; the file itself is subject to the grep rule (no coords).

### 5.4 Controller-level defense-in-depth test

In `test/adr_0014_tracking_isolation_test.dart`, a unit test instantiates `CustomerTrackingController`, feeds it a synthetic WS event payload with `type: "delivery.location"` and a lat/lng, and asserts:

1. The controller's state is unchanged (location event is silently dropped).
2. No screen widget displays any string matching `r'\d{1,3}\.\d{4,}'` (decimal coordinate pattern).
3. No field of type `LatLng` is reachable via `runtimeType` reflection in the state graph.

### 5.5 Analysis-options custom lint (Phase 12)

A custom lint `ensure_tracking_customer_has_no_coords` is proposed for `analysis_options.yaml` in Phase 12. Until then, the three tests above are the gate. The lint (Phase 12) would enforce at `dart analyze` time for local dev loops.

---

## 6. States summary across both view trees

| Fact | Customer view | Internal view (driver/seller) |
|---|---|---|
| Delivery status | ✓ | ✓ |
| ETA seconds | ✓ | ✓ |
| Status timeline | ✓ | ✓ |
| Own delivery address | ✓ | ✓ |
| Driver current location | **✗** | ✓ |
| Breadcrumb polyline | **✗** | ✓ |
| Interactive map | **✗** | ✓ |
| Driver identity (name / avatar) | **✗** | (admin only in Phase 11) |
| Distance counter | **✗** | ✓ |
| Duration counter | **✗** | ✓ (computed client-side) |
| Mark delivered action | **✗** | ✓ (driver or self-delivering seller) |
| Open navigation action | **✗** | ✓ |
| Call driver action | **✗** (no) | ✗ (not in Phase 10 even internally; Phase 12) |

---

## 7. Copy / strings

```
tracking.title = "Tracking"
tracking.customer.last_updated = "Last updated {rel}"
tracking.customer.eta.none = "Arrival time not available yet"
tracking.customer.eta.any_minute = "Arriving any minute"
tracking.customer.eta.minutes = "Arriving in ~{m} min"
tracking.customer.eta.hours = "Arriving in ~{h} h {m} min"
tracking.customer.delivered = "Delivered at {datetime}"

tracking.internal.title = "Delivery for Order #{short}"
tracking.internal.metric.distance = "Distance"
tracking.internal.metric.duration = "Duration"
tracking.internal.metric.eta = "ETA"
tracking.internal.waiting_for_location = "Waiting for driver location…"
tracking.internal.confirm_delivered.title = "Mark this order as delivered?"
tracking.internal.confirm_delivered.body = "The customer will be notified. You can't undo this."
tracking.internal.confirm_delivered.primary = "Mark delivered"
tracking.internal.offline_map = "Map unavailable offline. Driver position and breadcrumbs still update."
```

---

## 8. Edge cases table (cross-role)

| Case | Customer view | Internal view |
|---|---|---|
| Order has no delivery yet (pre-OFD) | Status tile + timeline only; no ETA badge | `/track` returns 409 `DELIVERY_NOT_ACTIVE` — screen renders `AppEmptyState("Delivery hasn't started yet.")` with a refresh button |
| Order cancelled mid-delivery | Status tile flips to cancelled copy | Full-screen `AppEmptyState("Delivery cancelled")` |
| Driver reassigned by admin | No visible change | WS delivered a `delivery.status` or `driver_reassigned` (Phase 11) event — refetch `/track` |
| GPS jitter on internal map | Polyline auto-trims; driver marker smooths over `motionStandard` | — |
| Map tile fetch blocked (enterprise network) | N/A (no map) | Fallback caption; pins on `surfaceVariant` background |
| Duplicate `delivery.status=delivered` event after REST POST | Dedupe by `{status, started_at ?? delivered_at}` tuple | Same |
| Customer app receives a `delivery.location` event (shouldn't happen) | Controller drops silently; test gate | — |
| Seller opens tracking for a driver-assigned (not self-delivered) order | Route is still `/home/seller/orders/:id/tracking` — seller is internal; sees coords. `Mark delivered` disabled (only driver can). | — |

---

## 9. Acceptance criteria (Phase 10 Frontend Engineer — tracking)

1. **Customer tracking screen** renders status tile, ETA badge, timeline, destination, seller card, and nothing else. Grep test for `lat`/`lng`/`mapbox` under `lib/features/tracking/customer/` passes with zero matches.
2. **Customer controller** drops `delivery.location` events silently (unit test asserts state unchanged).
3. **Internal tracking screen** renders Mapbox map with destination pin, driver pin, breadcrumb polyline. `delivery.location` events animate the driver pin and append to breadcrumbs (cap 50).
4. **Mark delivered** flow: dialog confirm → POST → UI flips. 409 swallowed per ADR-0003.
5. **Offline map fallback** displays pins on a surfaceVariant fallback when Mapbox tiles fail.
6. **Import-boundary** tests pass: customer/ does not import driver/, seller/, _internal_shared/, or any map SDK.
7. **ETA copy** matches §2.3 for all four ranges.
8. **Accessibility** — both views meet §2.9 / §3.8 specs. The internal view provides a screen-reader-first text panel mirroring the map state.
9. **Polling retirement** — customer order detail no longer polls `/orders/:id` every 30 s; `delivery.status` subscription drives it. `test/no_polling_test.dart` passes.
10. **`flutter analyze` → 0 errors** on Phase 10 impl branch. All new widget tests green.
