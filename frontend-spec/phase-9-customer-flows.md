# Frontend Spec — Phase 9 Customer Flows

**Phase:** 9 — UI/UX Designer deliverable (Frontend B).
**Audience:** Frontend Engineer implementing customer screens on top of the Phase 8 scaffold.
**Scope:** discovery (referral-scoped), seller/store detail, product detail, cart, checkout, order list, order detail with status timeline. Messaging (Phase 10), live delivery map (Phase 10), reviews UI (Phase 9 if review backend ships; otherwise deferred).

This spec extends `00-overview.md`, `02-component-library.md`, `03-role-shells.md`, `04-navigation-map.md`, and complements `phase-9-seller-flows.md`. Read the seller flows doc first — gaps table (§0) and cross-cutting loading/error patterns (§5) apply to the customer side identically unless noted.

---

## 0. Backend contract — gaps & deviations (customer-specific)

See `phase-9-seller-flows.md` §0 for the shared list. Customer-only items:

| # | Area | Status | Disposition |
|---|---|---|---|
| B-G2 | **Reviews endpoints** — `POST /orders/{id}/review`, `GET /reviews` — **not implemented**. The route `/home/customer/orders/:orderId/review` is reserved in `04-navigation-map.md` §1.3. | **BACKEND GAP** | Ship the nav entry disabled in Phase 9: when user opens a delivered/completed order, show a note "Reviews coming soon" in place of the CTA. Do NOT wire a form. |
| B-G3 | **Cart persistence** — no server-side cart. Cart is **client-only**, held by a Riverpod `CartNotifier` and persisted to `flutter_secure_storage` under key `cart.v1` so it survives cold start. One `cart.<sellerId>` bucket per seller (since each order is per-seller). | by design | Documented in §4.1. |
| B-G4 | **`GET /sellers/{id}/page`** (api-contract §5) **is not implemented**. The backend offers `GET /sellers/{id}` (SellerPublicResponse with display_name, bio, city) + `GET /stores/{id}` + `GET /products?store_id=` — use these three together. | deviation | §2 layout composes the store page from the three calls. |
| B-G5 | **Store discovery for a customer** — the backend does not expose a "list my referred sellers" endpoint. The customer knows their referring seller only via `/auth/me` and the `referring_seller_id` on the user record. | backend gap (soft) | **ADR-0007 depth=1** means customer has **exactly one** referred seller (or zero if admin-invited). The Discover tab shows that one seller — no list needed. Flagged for the Orchestrator: if depth > 1 ever becomes a product requirement, a `GET /customers/me/sellers` endpoint is needed. |
| B-D7 | `/auth/me` response **does not include `referring_seller_id`** today (check on implementation). If missing, **backend must add it** — otherwise the Discover tab has no way to find the customer's seller. | **BACKEND GAP** | Flag: Orchestrator to confirm `UserResponse` contains `referring_seller_id: UUID?`. If not, add it before Phase 9 cuts the Discover tab. |

---

## 1. Referral-scoped Discover — `/home/customer/discover` (tab)

**Purpose:** Customer's single-seller storefront. ADR-0007 (depth=1) means the customer sees **one** seller: their referrer. If the customer is unreferred (admin-invited, `referring_seller_id` null), they see the **access-gated empty state** — NEVER a 404 page, NEVER an empty-list "no products" layout.

### 1.1 Layouts by state

**State A — Unreferred customer (`referring_seller_id == null`):**

```
AppTopBar(title: "Discover")  // no back button; this is a root tab
Body:
  AppEmptyState (see 02-component-library.md §10.1 — ADR-0007):
    icon:     Icons.lock_outline
    headline: "You need a seller invite"
    subhead:  "This marketplace is invite-only. Ask a seller for their referral link, then open it to unlock their store."
    ctaLabel: "How invites work"  → AppBottomSheet with a 3-step explainer
```

**Hard rule:** this branch MUST be structurally distinguishable from state B. The widget check is `user.referringSellerId == null` — not "products list is empty". A product-list-empty state must NEVER render here (ADR-0007 invariant: the customer must not be able to infer that sellers exist).

**State B — Referred customer with a seller that has products:**

```
AppTopBar(title: store.name, trailing: [chat_bubble_outline → /home/customer/messages/:conversationId])
Sticky header (Collapse on scroll):
  AppCard(variant: default):
    Row: AppAvatar(lg, seller) + Column: display_name (titleLarge), city (bodySmall), bio?
    AppListTile(dense, leading: storefront, title: store.name, subtitle: city)
Body: Product grid
  SliverGrid 2-column (crossAxisSpacing 12, mainAxisSpacing 12, childAspectRatio 0.72):
    ProductTile (new component — §components-diff):
      image (square, radiusSm), name, formatMoney(price_minor),
      if stock_quantity == 0: "Out of stock" overlay
      onTap: → /home/customer/products/:productId
FAB: none; "View cart" is the sticky bottom bar when cart is non-empty (see §4.3).
```

**State C — Referred customer, seller has no products yet:**

```
AppEmptyState:
  icon:     Icons.storefront_outlined
  headline: "${seller.display_name} hasn't added products yet"
  subhead:  "Check back soon, or message them directly."
  ctaLabel: "Message ${seller.display_name}"  → /home/customer/messages/:conversationId
```

### 1.2 API calls

1. `GET /api/v1/auth/me` — already fetched in the session controller. Read `user.role == 'customer'` and `user.referring_seller_id`.
2. If `referring_seller_id == null` → State A. Do not call any other endpoint.
3. Else in parallel:
   - `GET /api/v1/sellers/{referring_seller_id}` → `SellerPublicResponse` (display_name, bio, city). 404 if not visible (shouldn't happen).
   - `GET /api/v1/products?seller_id={referring_seller_id}&limit=50` → list. Empty list → State C.
   - (Optional) `GET /api/v1/stores/{store_id}` when the products response includes `store_id` — fetch once per session, cached.

### 1.3 States summary

| State | Trigger | UI |
|---|---|---|
| loading | `AsyncValue.loading` for seller or products | 1 header SkeletonBox + 4 `SkeletonBox(w=double, h=180)` grid tiles |
| A (unreferred) | user.referring_seller_id == null | ADR-0007 empty state |
| B (data) | seller + products | Header + grid |
| C (no products) | seller ok, products empty | Seller-specific empty state |
| seller visibility 404 | edge | Generic `AppEmptyState(icon: error_outline, "Store unavailable")` — do not expose that the seller exists/doesn't |
| error network | connectivity | Retry empty state |

### 1.4 ADR-0007 enforcement checklist (widget-level)

- [ ] `DiscoverScreen` accepts a `CustomerDiscoverState` sealed class with explicit variants: `Unreferred`, `SellerProfileMissing`, `NoProducts`, `Ready(seller, products)`, `Loading`, `Error`. There is **no** `products.isEmpty` branch that falls through to a generic empty layout.
- [ ] The `Unreferred` variant is rendered by a `const` widget that has no dependency on any products provider — it cannot be triggered by a failed products fetch.
- [ ] A widget test asserts that an unreferred customer never causes `GET /products` to be called.
- [ ] A widget test asserts that when products list is empty the screen shows the seller-specific copy (state C), not a generic "No products" layout.

---

## 2. Seller / Store Detail — `/home/customer/sellers/:sellerId`

**Note:** under depth=1, this route exists for completeness but is effectively the same content as Discover when `sellerId == user.referring_seller_id`. Allow it so future depth changes don't require a rewrite; today it simply reuses the Discover widget with a back button.

**API:** same three calls as §1.2 but keyed off `:sellerId` path param.

**404:** for any `sellerId` not in the customer's referral chain, the backend returns 404 (ADR-0007). UI: generic `AppEmptyState(icon: error_outline, headline: "Not found", ctaLabel: "Back")`. Do not include "seller" in the copy — no existence leak.

---

## 3. Product Detail — `/home/customer/products/:productId`

**Purpose:** Full product page with image gallery and Add-to-cart action.

**Layout:**

```
AppTopBar(title: "", trailing: [chat_bubble_outline], leading: back)
SliverAppBar-like scroll:
  ImageGallery (new component — §components-diff):
    horizontally-swipeable PageView, page indicator dots below, 16:9 aspect
    tap → fullscreen gallery (out-of-scope for Phase 9 MVP; add later)
Body:
  Padding(all: space5):
    name (headlineSmall)
    formatMoney(price_minor) (titleLarge, primary color)
    stock badge: "In stock" | "Only N left" (N <= 5) | "Out of stock" (0)
    [space4]
    description (bodyMedium)
Sticky bottom:
  QuantityStepper (default 1, bounds [1, min(stock, 99)]) + AppButton(primary, expand, label: "Add to cart — ${formatMoney(price_minor * qty)}")
```

**States:**

| State | Visual |
|---|---|
| loading | SkeletonBox(16:9) + 3 SkeletonLine |
| data | Above |
| not-found (404) | `AppEmptyState(icon: error_outline, "Product unavailable", ctaLabel: "Back")` |
| out-of-stock | Button disabled + label "Out of stock" |
| add-to-cart success | Snackbar info "Added to cart" with action "View cart" |
| add-to-cart error (stock changed) | snackbar error + refetch |

**API:** `GET /api/v1/products/{id}` → `ProductResponse` (with `images` list). 404 for non-visible / deleted. No server call on "Add to cart" — cart is local (§B-G3).

**Image handling:**
- If `ProductResponse.images` is empty → show a single placeholder tile (`Icons.image_not_supported_outlined` on surfaceVariant).
- For each image, the app receives `s3_key`. The engineer's job: resolve to a public URL. **BACKEND DEPENDENCY:** the backend must expose either (a) public bucket URLs or (b) a signed-GET endpoint `GET /products/{id}/images/{image_id}/url`. The Phase 4 spec mentions "signed GET URL if image uploaded" — confirm with the Orchestrator before implementation. Flag as **B-G6** if not ready.

---

## 4. Cart + Checkout

### 4.1 Cart model (client-side)

Cart lives in `features/cart/application/cart_controller.dart` (Riverpod `AsyncNotifier`), backed by `flutter_secure_storage` key `cart.v1`.

Shape:
```dart
class CartState {
  final Map<String, SellerCart> bySeller;  // seller_id → lines
}
class SellerCart {
  final String sellerId;
  final String sellerDisplayName;
  final String storeId;
  final List<CartLine> lines;
}
class CartLine {
  final String productId;
  final String name;          // snapshot at add-time
  final int unitPriceMinor;   // snapshot
  final String currencyCode;
  final int quantity;
  final String? thumbS3Key;
}
```

**Why per-seller buckets:** each order is scoped to one store/seller (see backend `CreateOrderRequest`). We do not mix sellers in a single cart submission.

**Reconciliation on checkout:** re-fetch each product before placing order; if price or stock changed, show a diff dialog and let the user accept.

### 4.2 Cart screen — `/home/customer/cart`

Route is new. Entry points: bottom cart-bar pill (when non-empty), or a cart icon in the Discover app bar.

**Layout:**

```
AppTopBar(title: "Cart")
Body:
  if cart empty:
    AppEmptyState(icon: shopping_cart_outlined, headline: "Your cart is empty", subhead: "Add items from a store to see them here.")
  else: (typically single seller in Phase 9 due to depth=1)
    For each SellerCart:
      Header: AppListTile(dense, leading: AppAvatar(sm), title: seller display_name, trailing: "Remove all" text button)
      Items:
        CartLineItem (new component §components-diff):
          thumb (48dp), name, formatMoney(unitPriceMinor),
          QuantityStepper (bounded),
          trailing: remove (X) icon
      Summary block:
        Row("Subtotal", formatMoney(sum(line.unitPriceMinor * line.qty)))
        bodySmall caption "Delivery address entered at checkout"
      AppButton(primary, expand, size=lg, label: "Checkout with ${seller.display_name}") → /home/customer/cart/checkout?seller=<id>
```

**Actions:**
- `+` / `-` on QuantityStepper updates local state; a debounced re-validation against `/products/{id}` (stock, price) runs every 500 ms.
- Remove = immediate local removal; undo snackbar.

**A11y:** QuantityStepper buttons have semantic labels "Increase quantity" / "Decrease quantity". Live region announces "Quantity 3" after change.

### 4.3 Sticky cart bar (cross-screen)

When cart is non-empty and the user is on Discover or ProductDetail, render a sticky bar:
```
[ N items · formatMoney(subtotal) ][ View cart > ]
```
56dp tall, `surface` bg, elevation `elev2`. Hidden in checkout and order screens.

### 4.4 Checkout — `/home/customer/cart/checkout`

**Layout:**

```
AppTopBar(variant: modal, title: "Checkout")
Stepper/segmented progress (optional visual): Address → Review → Place
Body (single scroll view):
  Section "Delivery address" (structured form per backend Address schema):
    AppFormField("Address line 1", required) → AppTextField
    AppFormField("Address line 2") → AppTextField
    AppFormField("City", required) → AppTextField
    AppFormField("Region / state") → AppTextField
    AppFormField("Postal code") → AppTextField
    AppFormField("Country", required) → AppTextField (ISO2 or picker; Phase 9 accept free text len==2)
    AppFormField("Delivery notes") → AppTextField(maxLines: 3)
  Section "Order summary":
    For each CartLine: CartLineItem (read-only)
    Divider
    Row("Subtotal", formatMoney)
    Row("Total",    formatMoney, emphasis: titleMedium)
  [space6]
  AppButton(primary, expand, size=lg, label: "Place order", isLoading: ...)
  Privacy caption: bodySmall "Your coordinates are not shared with the seller. They see only your delivery address." (reinforces ADR-0014 invariant in UX copy — helpful, not legally required.)
```

**States:**

| State | Behavior |
|---|---|
| idle | form |
| submitting | button loading; form disabled |
| success | Clear that seller's cart bucket; navigate to `/home/customer/orders/:orderId` with replace. Snackbar info "Order placed". |
| error 400 `INSUFFICIENT_STOCK` | `AppDialog(title: "Stock changed", body: "'${productName}' only has X left. Update quantity?")` → adjust in cart + reload checkout |
| error 400 `STORE_NOT_IN_REFERRAL_CHAIN` / 403 / 404 | Unusual — data stale. `AppDialog` "This store is no longer available." → clear seller cart, back to Discover |
| error 422 | Inline field errors |
| error network / 500 | Snackbar retry |

**API:** `POST /api/v1/orders` body:
```json
{
  "items": [{"product_id": "uuid", "quantity": 2}],
  "delivery_address": { "line1": "...", "line2": "...", "city": "...", "region": "...", "postal": "...", "country": "US", "notes": "..." }
}
```
(Backend infers `store_id` from product ids — confirm; api-contract §7 shows `store_id` in request but backend schema `CreateOrderRequest` does not. **Deviation D8:** Frontend Engineer should test both; the spec-accurate call here follows `backend/app/schemas/orders.py`, which omits `store_id`. If backend rejects without `store_id`, include it — the cart knows the storeId.)

→ 201 `OrderResponse`.

---

## 5. Orders

### 5.1 Order List — `/home/customer/orders` (tab)

Mirror of `phase-9-seller-flows.md` §3.1 with customer copy:

```
AppTopBar(title: "Orders", trailing: [filter])
TabBar: [ Active ] [ Completed ] [ Cancelled ]
List: AppListTile per order:
  leading: icon per status
  title: "Order #${id.substring(0,8)} · ${formatMoney(total_minor)}"
  subtitle: "${seller.display_name} · ${relativeTime(placed_at)}"
  trailing: OrderStatusChip(status)
  onTap: → /home/customer/orders/:orderId
```

Empty:
```
AppEmptyState(icon: receipt_long_outlined, headline: "No orders yet", subhead: "When you place an order, it'll appear here.")
```

**API:** `GET /api/v1/orders?status=...&limit=50` (backend returns caller's own orders).

### 5.2 Order Detail — `/home/customer/orders/:orderId`

**Purpose:** Status timeline + items + limited delivery visibility per ADR-0014.

**Layout:**

```
AppTopBar(title: "Order #${id.substring(0,8)}", trailing: [chat_bubble_outline → /home/customer/messages/:conversationId])
Body:
  [CustomerDeliveryStatusWidget] (new component — components-diff §CustomerDeliveryStatusWidget)
    — Renders CustomerDeliveryView fields ONLY. No map in Phase 9 (the live map is Phase 10's CustomerDeliveryView widget).
    — Shows: big status chip, ETA badge if status=out_for_delivery, "Last updated N min ago".
  [OrderStatusTimeline] (shared with seller)
    placed → accepted → preparing → out_for_delivery → delivered → completed
  AppCard (seller block):
    AppListTile(leading: AppAvatar, title: seller.display_name, subtitle: store.name, trailing: chat)
  AppCard (items block):
    CartLineItem rows (read-only)
    Divider + Row("Total", formatMoney(total_minor), emphasis)
  AppCard (delivery block):
    title: "Delivered to"
    Formatted Address
    (No driver/seller coordinates shown — see §6)
  [if status == delivered or completed]
    AppButton(text, label: "Leave review") — DISABLED + tooltip "Reviews coming soon" until B-G2 resolves
  [if status == pending]
    AppButton(destructive text, expand, label: "Cancel order") → confirm AppDialog
```

**States:** same conventions as seller order detail (§3.2 in seller doc).

**API:**
- `GET /api/v1/orders/:id` → `OrderResponse` with customer-scoped delivery (customer.delivery_address is always the customer's own — no coordinate leak).
- `GET /api/v1/deliveries/:orderId/track` — returns `CustomerDeliveryView` (no coordinate fields; see Phase 7 spec). Called when `status in {out_for_delivery, delivered}`.
- `POST /api/v1/orders/:id/cancel` — customer cancel (pending only).
- `POST /api/v1/orders/:id/complete` — customer confirms receipt (after delivered). Moves to `completed`.

### 5.3 Delivery status in the customer order detail — ADR-0014 enforcement

**Invariant:** the `CustomerDeliveryStatusWidget` type **must not contain any coordinate fields** (lat, lng, driver_location, breadcrumbs, driver_id, seller_id, distance_meters). This is enforced at compile time via Dart:

```dart
// Widget-layer DTO: forbids coordinate fields by construction.
class CustomerOrderDeliveryProps {
  final DeliveryStatus status;
  final int? etaSeconds;           // from CustomerDeliveryView.eta_seconds
  final DateTime? etaUpdatedAt;
  final DateTime? startedAt;
  final DateTime? deliveredAt;
  final String destinationLabel;   // the customer's own address, formatted

  const CustomerOrderDeliveryProps({
    required this.status,
    required this.destinationLabel,
    this.etaSeconds,
    this.etaUpdatedAt,
    this.startedAt,
    this.deliveredAt,
  });
  // NO driverLat, driverLng, sellerLat, sellerLng, breadcrumbs, distanceMeters, driverId, sellerId.
}
```

**Required tests (before merging Phase 9):**
- Unit: `CustomerOrderDeliveryProps` class has **zero** fields matching the regex `(lat|lng|coord|driver_id|seller_id|breadcrumb|distance|location)`. A `dart:mirrors`-free reflection check isn't available; instead a **static analysis test** greps the file at test time and fails if any forbidden token appears.
- Widget: rendering the widget with a server-payload cast of the full `InternalDeliveryView` JSON is **not possible** (compile error on missing required fields / extra rejected fields).

**Widget file location:** `lib/features/orders/customer/widgets/customer_order_delivery_status.dart`. Do not place it under `lib/features/tracking/` — the Phase 10 live map customer widget lives there and composes this Phase 9 widget.

### 5.4 What the customer NEVER sees on the order detail

- No driver name, no driver avatar, no driver's live coordinates.
- No seller coordinates or seller address (only store city and name).
- No distance counter, no breadcrumb trail.
- No map tiles in Phase 9. Phase 10 adds the static destination-only pin.
- No "Call driver" / "Message driver" CTAs.

Only shown: status, ETA (if provided by backend `CustomerDeliveryView.eta_seconds`), timestamps (started_at, delivered_at), the customer's **own** delivery address.

---

## 6. Customer notifications (deferred — D5)

**D5 resolution:** FCM + APNs direct (no OneSignal). Implementation Phase 12.

**Customer-side triggers (spec for Phase 12; Phase 9 in-app equivalents):**

| Trigger | Payload | In-app in Phase 9 |
|---|---|---|
| `order.status_changed` | `{type, order_id, status}` | On the order detail, the status chip + timeline auto-advance when the app is in the foreground (poll `/orders/:id` every 30 s when on this screen; in Phase 10 switch to WS delivery.status events). |
| `order.out_for_delivery` | `{type, order_id, eta_seconds?}` | Snackbar in foreground + badge on Orders tab. |
| `order.delivered` | `{type, order_id}` | Snackbar + prompt to confirm receipt. |

Per `03-role-shells.md` §5, the Orders tab shows an active-order count dot.

---

## 7. Cross-cutting — customer side

### 7.1 Currency formatting

All prices, totals, and line items MUST use `formatMoney(int minorUnits, {String? currencyCode})`. See `phase-9-components-diff.md` §Currency. A widget test enforces no raw `/ 100` or `NumberFormat().format(x / 100)` usage on any widget in `features/` (grep-based).

### 7.2 Semantics

- `ProductTile`: `Semantics(button: true, label: "${name}, ${formatMoney(price)}, ${stockLabel}")`.
- `QuantityStepper`: two buttons with `Semantics(button: true, label: "Increase/Decrease quantity, current ${qty}")`.
- Cart sticky bar: `Semantics(label: "View cart, ${n} items, total ${formatMoney(subtotal)}", button: true)`.
- Status chip: `Semantics(label: "Status: ${statusHumanLabel}")`.
- Delivery status widget: `Semantics(liveRegion: true, label: "${statusHumanLabel}${etaLabel ?? ''}")`.

### 7.3 Offline behavior

- Discover: if cached products exist from a prior fetch, show them with a subtle banner "You're offline. Showing last-seen items." New adds to cart allowed; orders page will block checkout with a "You need to be online to place an order" dialog.
- Cart: fully available offline.
- Checkout: submit button disabled offline; banner.

### 7.4 401 / session expiry

Handled globally by `TokenInterceptor` + `AuthController.sessionExpired` callback, per `05-auth-flows.md`. No customer screen needs local 401 handling.

---

## 8. Summary of screens

| Route | Phase | Components used | New components |
|---|---|---|---|
| `/home/customer/discover` | 9 | AppEmptyState (ADR-0007), AppCard, AppAvatar, AppSkeleton | ProductTile |
| `/home/customer/sellers/:sellerId` | 9 | (reuses Discover) | — |
| `/home/customer/products/:productId` | 9 | AppButton, AppSkeleton, AppSnackbar | ImageGallery, QuantityStepper |
| `/home/customer/cart` | 9 | AppListTile, AppButton, AppEmptyState, AppAvatar | CartLineItem, QuantityStepper |
| `/home/customer/cart/checkout` | 9 | AppFormField, AppTextField, AppButton, AppDialog | CartLineItem |
| `/home/customer/orders` | 9 | AppListTile, AppSkeleton | OrderStatusChip |
| `/home/customer/orders/:orderId` | 9 | AppCard, AppListTile, AppButton, AppDialog | OrderStatusTimeline, CustomerDeliveryStatusWidget, CartLineItem |

Cart sticky bar is a shared widget (details in components-diff).

---

## 9. Frozen invariants recap (widget-level)

- **ADR-0007** — Discover's unreferred branch is a sealed `Unreferred` state, not a products-empty fallthrough. Widget test required (§1.4).
- **ADR-0014** — `CustomerOrderDeliveryProps` has zero coordinate fields; type-checked by the Dart compiler. No shared widget with seller/driver; the internal view lives under `features/tracking/internal/` and is unreachable from any customer route.
- **ADR-0009 / ADR-0013** — n/a in Phase 9 (no chat UI here). The Phase 10 `ChatBubble` spec is unchanged.

These three are PR review gates. Any PR that introduces a `role` flag that would collapse the two tracking widgets, adds a coordinate field to the customer props, or silently empty-lists the Discover tab when a user is unreferred should be rejected.
