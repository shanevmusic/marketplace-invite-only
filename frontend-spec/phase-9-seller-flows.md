# Frontend Spec — Phase 9 Seller Flows

**Phase:** 9 — UI/UX Designer deliverable (Frontend B).
**Audience:** Frontend Engineer implementing seller screens on top of the Phase 8 scaffold.
**Scope:** seller store setup, product CRUD, order inbox + order detail with state-machine actions, dashboard. Messaging UI (Phase 10), internal delivery map (Phase 10), admin (Phase 11) are out of scope.

This spec extends — it does not restate — `00-overview.md`, `02-component-library.md`, `03-role-shells.md`, `04-navigation-map.md`. Every screen reuses the Phase 8 component library where possible; any new component is called out in `phase-9-components-diff.md`.

---

## 0. Backend contract — gaps & deviations discovered

The Frontend Engineer must treat this list as authoritative over `docs/api-contract.md`. Gaps flagged here are for the Orchestrator to triage before Phase 9 implementation.

| # | Area | Status | Disposition |
|---|---|---|---|
| B-G1 | **Product image upload URL** — `POST /products/{id}/image-upload-url` described in api-contract §6 is **not implemented** in Phase 4 (see `phase-4-notes.md` §Key decisions point 8: "no upload pre-signed URL endpoint this phase"). Product images are accepted inline as `{s3_key, display_order}` metadata only. | **BACKEND GAP** | Phase 9 UI assumes a pre-signed PUT URL will be available; until then the `ImagePicker`/upload flow must show a *"Image upload coming soon — add URL-backed image metadata manually"* developer-preview state OR the orchestrator must land the upload endpoint before Phase 9 implementation. This spec proceeds assuming the endpoint ships; implementation order is the Engineer's call. |
| B-G2 | **Reviews endpoints** (`POST /orders/{id}/review`, `GET /reviews`) are **not implemented** yet. Customer-side "Leave review" route is declared in `04-navigation-map.md` §1.3 but has no backend. | **BACKEND GAP (customer-side)** | Flagged here because the seller order detail references review display in `phase-9-customer-flows.md`. Seller flows themselves do not depend on reviews in Phase 9. |
| B-D1 | Order state transitions use `POST` (not `PATCH` as in api-contract §7) and the paths are `/orders/{id}/accept`, `/preparing`, `/self-deliver`, `/request-driver`, `/out-for-delivery`, `/delivered`, `/complete`, `/cancel`. **Use these exactly.** | deviation — contract is stale; backend wins | Engineer: use the backend paths verbatim. |
| B-D2 | Order `create` endpoint requires `delivery_address: {line1, city, country, …}` as a structured `Address` object, not a free-text string. (See `backend/app/schemas/orders.py::Address`.) | deviation | Checkout form must collect structured fields. |
| B-D3 | Seller dashboard field names: `lifetime_sales_amount` (int, minor units), `lifetime_orders_count`, `active_orders_count`, `currency_code`, `last_updated`. Contract §12 uses `lifetime_revenue` (decimal string); backend wins. | deviation | Use minor-units int + `formatMoney()` helper. |
| B-D4 | Order listing is `limit`-only (no cursor in Phase 5). | deviation | Pagination UI in Phase 9 = "Load more" button or simple truncation; no infinite scroll cursor state needed. |
| B-D5 | `GET /stores/me` returns 404 when the seller has not created a store. | confirmed | Drives the dashboard empty state in §4.1. |
| B-D6 | One store per seller, enforced server-side (409 `STORE_ALREADY_EXISTS`). | confirmed | Drives §1 copy. |

---

## 1. Store Setup

### 1.1 Create Store — `/home/seller/store/new`

**Purpose:** Initial onboarding for a freshly signed-up seller. One store per seller; city is required; `POST /stores` returns `409 STORE_ALREADY_EXISTS` if one already exists.

**Entry points:**
- Dashboard empty state CTA (§4.1) — the normal path.
- Store tab → pencil icon when no store exists (edge case for power users).

**Layout (Material 3, reusing Phase 8 components):**

```
AppTopBar (variant: modal, title: "Create your store", leading: X → confirm-discard dialog if dirty)
Scrollable body:
  [ space6 ]
  Heading titleLarge: "Tell customers who you are"
  Body bodyMedium: "You can edit this later from the Store tab."
  [ space6 ]
  AppFormField(label: "Store name", required)      → AppTextField(text)
  AppFormField(label: "City",        required)      → AppTextField(text, autofill: addressCity)
  AppFormField(label: "Description", required:false)→ AppTextField(text, maxLines: 4)
  [ space6 ]
  AppButton(variant: primary, size: lg, expand: true, label: "Create store", isLoading: submitState.isSubmitting)
```

No slug field (backend auto-generates from name).

**States:**

| State | Behavior |
|---|---|
| loading (initial) | not applicable; form is synchronous until submit |
| validating | Field-level (`required`, 1–255 chars). Trim whitespace. Inline `errorText`. |
| submitting | `AppButton.isLoading=true`; all inputs disabled. |
| success | `context.showAppSnackbar(success, "Store created")`; pop back to `/home/seller/dashboard` (which re-fetches). |
| error (409 `STORE_ALREADY_EXISTS`) | `AppDialog(title: "Store already exists", body: "This account already has a store. Open it?")` → primary CTA navigates to `/home/seller/store`. |
| error (422 validation) | Map `detail` field errors to per-field `errorText`. |
| error (network / 500) | `AppSnackbar(error, "Couldn't create store. Try again.", actionLabel: "Retry")`. |

**API:** `POST /api/v1/stores` body `{name, city, description?}` → 201 `StoreResponse`.

**Navigation on success:** `go_router.pop()` back to `/home/seller/dashboard`; the dashboard `AsyncNotifier` invalidates on the session resume.

**Edge cases:**
- Form dirty + back press → `AppDialog` confirm-discard.
- Rate-limit 429 → `AppSnackbar(error, "Too many attempts, try again in a minute.")`.

**A11y:** Every field wrapped in `AppFormField`; `semanticsLabel` inherited from `label`. Submit button `Semantics(button: true, label: "Create store, submit")`.

---

### 1.2 Edit Store — `/home/seller/store`

**Purpose:** Review and edit the store. Also the Store tab (tab index 3) body.

**Layout:**
```
AppTopBar(title: store.name, trailing: [Icons.edit] → toggles edit mode)
Scrollable body:
  [Read mode]
    AppCard(variant: default):
      TitleRow: storefront icon + store.name + RoleBadge(seller)
      KeyValueRow("City", store.city)
      KeyValueRow("Description", store.description or "—")
    AppListTile(icon: share, title: "Share my referral link", onTap: copyToClipboard + snackbar)
    AppListTile(icon: logout, title: "Sign out", onTap: confirm dialog, destructive=true)
  [Edit mode — same AppFormFields as §1.1, Save / Cancel actions]
```

**States:**

| State | Behavior |
|---|---|
| loading | `AppSkeleton.SkeletonBox(h=120)` + 3× `SkeletonLine` |
| empty (404 — no store) | Should not happen on this route (redirect to `/home/seller/store/new`). If it does, render the dashboard empty state inline. |
| read success | Layout above |
| edit | Same form as §1.1 pre-populated via `PATCH /stores/me` body |
| error (network) | Full-screen `AppEmptyState`(icon: wifi_off, headline: "Can't load store", ctaLabel: "Retry") |

**API:**
- `GET /api/v1/stores/me` → `StoreResponse` (200) or 404.
- `PATCH /api/v1/stores/me` body `{name?, city?, description?, is_active?}` → 200.

**Edge cases:**
- PATCH with an empty form (no changes) → treat Save as a no-op, pop.
- `is_active=false` toggle is a Phase 9 stretch; if included, confirmation dialog must explain that deactivating hides the store from new orders (does not delete it).

---

## 2. Product CRUD

### 2.1 Product List — `/home/seller/products` (tab)

**Purpose:** The seller's inventory view. Primary entry to create/edit.

**Layout:**
```
AppTopBar(title: "Products", trailing: [search])
Body: Paginated list
  SliverList of AppListTile(
    leading: product image thumbnail (48dp rounded, radiusSm) or placeholder,
    title: product.name,
    subtitle: "${formatMoney(price_minor)} · stock ${stock_quantity ?? '∞'}",
    trailing: if !is_active: Chip("Hidden") else Chip("Active"),
    onTap: → /home/seller/products/:productId/edit,
  )
AppFab.extended(icon: add, label: "Add product", onPressed: → /home/seller/products/new)
```

**States:**

| State | Visual |
|---|---|
| loading | 5× `AppSkeleton.SkeletonTile()` |
| empty | `AppEmptyState(icon: inventory_2_outlined, headline: "No products yet", subhead: "Add your first product to start selling.", ctaLabel: "Add product")` |
| data | List above |
| end-of-list | If response indicates `has_more=false` (future cursor) or < limit returned, show faint `bodySmall` "You've reached the end." |
| error (network) | `AppEmptyState(icon: wifi_off, headline: "Can't load products", ctaLabel: "Retry")` |
| error (401) | Handled globally by TokenInterceptor → session expiry flow (see `05-auth-flows.md`). |

**API:** `GET /api/v1/products?seller_id=<me>&limit=50` (seller-scoped; backend filters to own automatically when no `store_id`). Response `{data: ProductListItem[], pagination: {has_more, next_cursor?}}`.

**Edge cases:**
- Pull-to-refresh: `RefreshIndicator` wrapping the list invalidates the provider.
- No store yet → this tab is still reachable; show `AppEmptyState(icon: storefront, headline: "Create a store first", ctaLabel: "Create store" → `/home/seller/store/new`)`. Do NOT hit `POST /products` without a store; backend will 400.

---

### 2.2 Product Create — `/home/seller/products/new`

**Purpose:** Add a product. Multi-image (primary + additional) supported.

**Layout:**
```
AppTopBar(variant: modal, title: "Add product")
Scrollable body:
  Section "Images" (see §2.4 for ImagePicker spec)
    ImagePicker(max: 8, primaryAt: 0)
  Section "Details"
    AppFormField(label: "Name",            required)   → AppTextField(text)
    AppFormField(label: "Description",     required:false) → AppTextField(text, maxLines: 6)
    AppFormField(label: "Price",           required)   → MoneyField (see components-diff §CurrencyField)
    AppFormField(label: "Stock (optional)", required:false) → AppTextField(numeric) — null = unlimited
  [ space6 ]
  AppButton(variant: primary, size: lg, expand: true, label: "Add product", isLoading: ...)
```

**Validation:**
- Name 1–255 chars.
- Description max 10,000.
- Price: parsed via `MoneyField`, submitted as `price_minor` int (> 0). Localized display.
- Stock: empty string = null (unlimited); otherwise int ≥ 0.
- Images: optional. A primary image is auto-set to index 0 if any images exist.

**States:**

| State | Behavior |
|---|---|
| idle | Form |
| image uploading | Each `ImagePicker` tile has its own progress ring and error state (retry button). Submit disabled until all uploads resolve or user removes failures. |
| submitting | `AppButton.isLoading=true` after images finalized; body is `{store_id, name, description?, price_minor, stock_quantity?, images: [{s3_key, display_order}]}`. |
| success | Pop to list; snackbar "Product added". |
| error 400 / 422 | Field errors or top dialog. |
| error 409 (slug conflict — unlikely on products; server handles) | Snackbar + retry. |

**API:**
- Image upload (§2.4): `POST /api/v1/products/{id}/image-upload-url` → `{upload_url, expires_in_seconds, object_key}` then `PUT upload_url` (direct to S3). **BACKEND GAP B-G1** — until endpoint lands, disable image upload or accept a text-entered s3_key in developer builds only.
- `POST /api/v1/products` body `{store_id, name, description?, price_minor, stock_quantity?, images: [{s3_key, display_order}]}` → 201 `ProductResponse`.

**Navigation:** pop to `/home/seller/products` on success.

**Edge cases:**
- Dirty + back → confirm discard.
- Image upload partial failure: allow submit with only successfully uploaded images; UI shows "2 of 3 images uploaded". Failed slots marked for retry inside the picker.

---

### 2.3 Product Edit — `/home/seller/products/:productId/edit`

Same layout as §2.2, pre-populated from `GET /api/v1/products/:productId`. PATCH instead of POST.

**States:** add `loading` (fetch), `not-found` (404 → snackbar + pop).

**API:**
- `GET /api/v1/products/:id` → `ProductResponse` (200/404).
- `PATCH /api/v1/products/:id` body — partial per `UpdateProductRequest` (name, description, price_minor, stock_quantity, is_active, images) — passing `images` **replaces the set wholesale** (phase-4 contract).
- Soft delete: `DELETE /api/v1/products/:id` → 204.

**Additional actions block (bottom of edit body):**
```
AppListTile(icon: visibility_off, title: "Hide from catalog", trailing: Switch(is_active))
AppButton(variant: destructive, expand: true, label: "Delete product") 
  → AppDialog(title: "Delete this product?", body: "Existing orders keep their product snapshot; this removes it from your catalog.", primaryAction: destructive "Delete", secondary: "Cancel")
```

---

### 2.4 Image Picker — component behavior (detailed in components-diff §1)

**On tap of the `+` tile:**
1. Open native image picker (`image_picker` pkg) — single selection; user repeats for multiple.
2. Client: validate file size ≤ 10 MB and mime in `{jpeg, png, webp}`.
3. `POST /products/{id}/image-upload-url` → `{upload_url, object_key}`.
4. `PUT upload_url` raw bytes with `Content-Type` matching.
5. On 2xx, append `{s3_key: object_key, display_order: index}` to form state.
6. On failure, mark slot as "Retry" and allow remove.

**Primary image:** a long-press on any slot promotes it to index 0. The first slot is visually marked "Primary" via a small badge.

**Backend dependency on create:** the product must exist before `image-upload-url` can be called (since route is `/products/{id}/image-upload-url`). Two approaches:
- **(a) Create-then-upload:** POST product with empty images, get id, upload, PATCH images. Two round-trips.
- **(b) Defer create-until-upload-done:** pre-signed endpoint accepts `store_id` pre-creation, returns a temporary object key. This requires a backend change and is **not available** in Phase 4.

**Decision:** use **(a)** — create with empty images, then upload + PATCH. Document in UI as a single "Add product" action; the engineer handles the multi-step internally.

---

## 3. Order Inbox + Order Detail

### 3.1 Order List — `/home/seller/orders` (tab)

**Purpose:** Prioritized view of active + historical orders.

**Layout:**
```
AppTopBar(title: "Orders", trailing: [filter])
TabBar (stateless segmented control, no MaterialTabBar):
  [ Active (count) ] [ Completed ] [ Cancelled ]
Body: List of AppListTile per order:
  leading: status dot icon (see §3.3 timeline colors)
  title: "Order #${id.substring(0,8)} · ${formatMoney(total_minor)}"
  subtitle: "${item_count} items · ${relativeTime(placed_at)}"
  trailing: OrderStatusChip(status)
  onTap: → /home/seller/orders/:orderId
```

The Active filter is the default; shows orders in statuses `pending, accepted, preparing, out_for_delivery`. Completed = `delivered, completed`. Cancelled = `cancelled`.

**States:**

| State | Visual |
|---|---|
| loading | 5× SkeletonTile |
| empty (active) | `AppEmptyState(icon: receipt_long_outlined, headline: "No active orders", subhead: "When customers place orders, they'll appear here.")` |
| empty (completed/cancelled) | "Nothing here yet" |
| data | List |
| error (network) | Retry empty state |

**API:** `GET /api/v1/orders?status={status}&limit=50`. Seller sees own-store orders only (backend enforces).

**Badges:** Dashboard tab shows an active-order count dot (per `03-role-shells.md` §5) based on the Active count.

---

### 3.2 Order Detail — `/home/seller/orders/:orderId`

**Purpose:** Full order view with the state-machine action button for the next transition.

**Layout (scrollable):**

```
AppTopBar(title: "Order #${id.substring(0,8)}", trailing: [chat icon → message customer (Phase 10)])
[OrderStatusTimeline] (new component — §components-diff)
  Timeline rows with timestamps: placed → accepted → preparing → out_for_delivery → delivered → completed
AppCard (customer block):
  AppListTile(leading: AppAvatar(md), title: customer display name, subtitle: "Customer", trailing: Icons.chat_bubble_outline)
AppCard (items block):
  CartLineItem-style rows (reuse component from customer flow, see §components-diff):
    each item: name_snapshot · qty · formatMoney(unit_price_minor_snapshot * quantity)
  Divider
  Row("Subtotal", formatMoney(subtotal_minor))
  Row("Total",    formatMoney(total_minor), emphasis: titleMedium)
AppCard (delivery block):
  title: "Deliver to"
  Multi-line: formatted Address (line1, line2, city, region, postal, country)
  if address.notes: subdued bodySmall "Note: $notes"
[OrderStateActionPanel] — see §3.3
```

**Bottom action panel (sticky):** see §3.3 state-machine matrix.

**States:**

| State | Visual |
|---|---|
| loading | Full-screen SkeletonBox with 3 SkeletonTile |
| not-found (404) | `AppEmptyState(icon: error_outline, headline: "Order not found", subhead: "It may have been deleted or doesn't belong to your store.", ctaLabel: "Back to orders")` |
| forbidden (403) | Same as 404 (backend returns 404 on non-visible anyway) |
| data | Layout above |
| action-in-flight | Action button `isLoading=true`; other actions disabled |
| action error (409 conflict, e.g. retry stale state) | `AppSnackbar(error, "Order state changed. Reloading…")` + auto-refresh |

**API:**
- `GET /api/v1/orders/:id` → `OrderResponse`.
- State transitions (see §3.3).

---

### 3.3 Order State Machine (seller actions)

Per `PROJECT.md` §3 and backend `/orders/*` routes. The seller's action surface varies by status.

| Current status | Available seller actions | Endpoint | Outcome |
|---|---|---|---|
| `pending` | Accept · Decline | `POST /orders/{id}/accept` ; `POST /orders/{id}/cancel` | accepted / cancelled |
| `accepted` | Start preparing · Cancel | `POST /orders/{id}/preparing` ; `POST /orders/{id}/cancel` | preparing / cancelled |
| `preparing` | Self-deliver → (go to out_for_delivery) · Request driver · Cancel | `POST /orders/{id}/self-deliver` → then `POST /orders/{id}/out-for-delivery` ; `POST /orders/{id}/request-driver` | out_for_delivery / driver requested |
| `out_for_delivery` | Mark delivered (self-deliver only) · Open delivery tracking (Phase 10) | `POST /orders/{id}/delivered` | delivered |
| `delivered` | (none — customer completes or auto-complete) | — | — |
| `completed` | (none) | — | — |
| `cancelled` | (none) | — | — |

**Idempotency note:** `out-for-delivery` returns `409 DELIVERY_ALREADY_STARTED` on double-call (ADR-0003); the UI must treat this as "already in that state" and reload without error toast.

**Action panel layout (component: `OrderStateActionButton` — see components-diff):**
```
Primary action  (AppButton primary, expand=true, size=lg) — biggest CTA
Secondary      (AppButton secondary, expand=true) — e.g. "Request driver"
Destructive    (AppButton text color=destructive, expand=true) — "Cancel order"
```

For `preparing`, "Self-deliver" is a single combined button that hits `/self-deliver` then `/out-for-delivery` sequentially (the backend models these as two transitions; UX is one tap). Confirmation `AppDialog`: *"Start self-delivery? You'll be able to update the customer when it's delivered."*

For `request-driver` the confirmation copy: *"Request a driver from admin? Admin will assign one when available."*

Cancel: `AppDialog(title: "Cancel this order?", body: "This can't be undone. The customer will be notified.", primaryAction: destructive "Cancel order", secondaryAction: "Keep order")`. Cancel reason: optional text field inside the dialog body (maps to `CancelOrderRequest.reason`).

---

## 4. Dashboard

### 4.1 Seller Dashboard — `/home/seller/dashboard` (tab)

**Purpose:** At-a-glance lifetime and active metrics per F28.

**Layout:**
```
AppTopBar(title: store.name ?? "Dashboard", trailing: [share → copy referral link])
Pull-to-refresh wrapper
Scrollable body:
  [if no store]
    AppEmptyState(icon: storefront_outlined, headline: "Create your store", subhead: "Give it a name and city so customers can find you.", ctaLabel: "Create store" → /home/seller/store/new)
  [else]
    Row of two MetricCards (see components-diff §MetricCard — or reuse AppCard):
      MetricCard(label: "Lifetime sales", value: formatMoney(lifetime_sales_amount, currency_code), caption: "since day 1")
      MetricCard(label: "Lifetime orders", value: lifetime_orders_count.toString())
    MetricCard(label: "Active orders", value: active_orders_count.toString(), onTap: → /home/seller/orders?filter=active)
    
    Section "Recent activity"
      List of the 5 most recent orders (reuse AppListTile from §3.1). Tap → order detail.
      If no orders yet: inline bodySmall "Share your referral link to invite your first customer." + copy-link chip.
```

**States:**

| State | Visual |
|---|---|
| loading (both store + dashboard) | 2 `SkeletonBox(w=double, h=96)` + 3 `SkeletonTile` for recent activity |
| no-store (404 from `/stores/me`) | Create-store empty state above |
| zero-data (store exists, all counts == 0) | Metric cards with zeros + inline copy-link hint |
| data | Full layout |
| error | `AppEmptyState(icon: wifi_off, ctaLabel: "Retry")` |

**API:**
- `GET /api/v1/stores/me` → 200 (data) or 404 (no-store state).
- `GET /api/v1/sellers/me/dashboard` → `SellerDashboardResponse` (200).
- `GET /api/v1/orders?limit=5` (recent activity).

**Currency formatting rule (MANDATORY):** every amount rendered on the dashboard (and anywhere else) must go through `formatMoney(int minorUnits, {String? currencyCode})` in `lib/shared/format/money.dart`. Ad-hoc `/ 100` or `String.format("%.2f")` is forbidden at review. The helper reads `currency_code` from the dashboard response; default fallback `USD` only if the response omits it. See `phase-9-components-diff.md` §Currency for the helper signature.

**A11y:**
- Metric cards are `Semantics(label: "Lifetime sales, \$123.45", button: true if onTap)`.
- Pull-to-refresh announces "Refreshed" via `SemanticsService.announce`.

---

## 5. Cross-cutting loading / error / empty patterns

These are applied to every list in §2.1, §3.1, and §4.1. Enumerated here so the Frontend Engineer can factor them into a single `AsyncValueWidget<T>`.

| Flavor | UI |
|---|---|
| Loading list | 5× `AppSkeleton.SkeletonTile()` matching the list tile layout |
| Loading detail | `SkeletonBox` header + 3× `SkeletonLine` |
| Loading button | `AppButton.isLoading=true` |
| Empty | `AppEmptyState` with role-appropriate icon, headline, optional CTA |
| Network error (connectivity) | `AppEmptyState(icon: Icons.wifi_off, headline: "You're offline", ctaLabel: "Retry")` |
| 401 | Handled by TokenInterceptor (see `05-auth-flows.md`). Widget never sees raw 401; controller emits `sessionExpired`. |
| 403 | Treat like 404 (we don't reveal existence). Empty state "Not found" copy. |
| 404 | `AppEmptyState(icon: error_outline, headline: "Not found", ctaLabel: "Back")` |
| 409 | Inline `AppSnackbar(error, "Conflict — please retry")` + auto-refresh where applicable |
| 429 | `AppSnackbar(info, "Too many requests. Try again in a minute.")` |
| 500 | `AppSnackbar(error, "Something went wrong. Try again.")` + `AppEmptyState` retry CTA on list screens |

**Image placeholders:** use `AppSkeleton.SkeletonBox(radius: radiusSm)` while a product image loads. On failed load, show `Icons.image_not_supported_outlined` inside a `surfaceVariant` box of the same shape.

---

## 6. Notifications (deferred — D5 decision)

**D5 resolution:** Push notifications will use **FCM (Android) + APNs direct (iOS)**, no OneSignal. Implementation is deferred to **Phase 12**.

**Seller-side triggers (Phase 12 payload contract, specified here so Phase 9 screens can surface the in-app equivalents):**

| Trigger | Payload (opaque to Phase 9) | In-app equivalent in Phase 9 |
|---|---|---|
| `order.new` | `{type: "order.new", order_id, customer_display_name}` | Orders tab badge count + snackbar "New order from $name" on foreground |
| `order.cancelled` (by customer) | `{type: "order.cancelled", order_id}` | Order detail auto-refresh + snackbar |

Phase 9 does **not** request push permission, configure FCM, or register a device token. The scaffold hook is `features/notifications/` created empty in Phase 12.

---

## 7. Summary of screens

| Route | Phase | Components used | Components introduced |
|---|---|---|---|
| `/home/seller/dashboard` | 9 | AppCard, AppListTile, AppSkeleton, AppEmptyState | MetricCard (if not AppCard composition) |
| `/home/seller/store/new` | 9 | AppFormField, AppTextField, AppButton, AppDialog | — |
| `/home/seller/store` | 9 | AppCard, AppListTile, AppFormField | — |
| `/home/seller/products` | 9 | AppListTile, AppFab.extended, AppSkeleton, AppEmptyState | OrderStatusChip / ProductThumb placeholder |
| `/home/seller/products/new` | 9 | AppFormField, AppButton | ImagePicker, MoneyField |
| `/home/seller/products/:id/edit` | 9 | (same) + AppDialog destructive | — |
| `/home/seller/orders` | 9 | AppListTile, AppSkeleton | OrderStatusChip |
| `/home/seller/orders/:id` | 9 | AppCard, AppListTile, AppButton, AppDialog | OrderStatusTimeline, OrderStateActionButton, CartLineItem |

Every new component is specified in `phase-9-components-diff.md`.
