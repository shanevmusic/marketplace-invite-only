# Frontend Spec — Phase 9 Navigation Additions

**Phase:** 9 — UI/UX Designer deliverable.
**Audience:** Frontend Engineer extending `lib/app/routes.dart` and the go_router tree.

This document **adds** to `04-navigation-map.md`. Nothing here replaces the Phase 8 tree — the redirect logic, role guards, deep-link behavior, and session-refresh handling stay exactly as specified. New routes must slot into the existing `ShellRoute` per role so the bottom nav and tab-state `IndexedStack` continue to work.

---

## 1. Tab ordering & naming (confirmed unchanged)

Per `03-role-shells.md` §1.1 and §2.1, the tab order is stable. Phase 9 does not reorder or rename any tab.

### 1.1 Customer shell

| Index | Path | Icon (outline / filled) | Label |
|---|---|---|---|
| 0 | `/home/customer/discover` | `storefront_outlined` / `storefront` | Discover |
| 1 | `/home/customer/orders` | `receipt_long_outlined` / `receipt_long` | Orders |
| 2 | `/home/customer/messages` | `chat_bubble_outline` / `chat_bubble` | Messages |
| 3 | `/home/customer/profile` | `person_outline` / `person` | Profile |

**Badges:** Orders tab shows an active-order count dot computed from `GET /orders?status=in_progress_like` (pending, accepted, preparing, out_for_delivery). See `phase-9-components-diff.md` §TabBadge.

### 1.2 Seller shell

| Index | Path | Icon | Label |
|---|---|---|---|
| 0 | `/home/seller/dashboard` | `dashboard_outlined` / `dashboard` | Dashboard |
| 1 | `/home/seller/products` | `inventory_2_outlined` / `inventory_2` | Products |
| 2 | `/home/seller/orders` | `receipt_long_outlined` / `receipt_long` | Orders |
| 3 | `/home/seller/profile` | `store_outlined` / `store` | Store |

**Badges:** Orders tab shows active-order count dot (same semantics as customer). Dashboard shows no badge.

No changes to driver or admin shells in Phase 9.

---

## 2. New detail routes introduced

These were declared (path-only) in `04-navigation-map.md` §1.3; Phase 9 ships their bodies. Paths confirmed or adjusted here.

### 2.1 Customer

| Path | Screen | Allowed roles | Phase 9 status | Notes |
|---|---|---|---|---|
| `/home/customer/discover` | DiscoverScreen | customer | NEW (body) | Tab 0. Replaces the Phase 8 placeholder. Implements ADR-0007 sealed-state branching. |
| `/home/customer/sellers/:sellerId` | SellerDetailScreen | customer | NEW | Depth=1 today — typically the same as Discover; reserved for depth>1. 404 on non-visible. |
| `/home/customer/products/:productId` | ProductDetailScreen | customer | NEW | 404 on non-visible. |
| `/home/customer/cart` | CartScreen | customer | **NEW (not in Phase 8 spec)** | Entry: sticky cart bar or cart icon in Discover app bar. See §3. |
| `/home/customer/cart/checkout` | CheckoutScreen | customer | **NEW** | Not a tab; modal-style app bar. |
| `/home/customer/orders` | OrdersListScreen | customer | NEW (body) | Tab 1. |
| `/home/customer/orders/:orderId` | OrderDetailScreen | customer | NEW | Includes `CustomerDeliveryStatusWidget` (Phase 9). Live-map widget added Phase 10. |
| `/home/customer/orders/:orderId/review` | reserved | customer | DEFERRED — backend gap B-G2 | Route registered but renders "Coming soon" placeholder. |

### 2.2 Seller

| Path | Screen | Allowed roles | Phase 9 status | Notes |
|---|---|---|---|---|
| `/home/seller/dashboard` | DashboardScreen | seller | NEW (body) | Tab 0. |
| `/home/seller/store/new` | CreateStoreScreen | seller | NEW | Modal-style app bar; can be deep-linked from dashboard empty state. |
| `/home/seller/store` | StoreDetailScreen | seller | NEW (body of Tab 3) | Read/edit modes. |
| `/home/seller/products` | ProductsListScreen | seller | NEW (body) | Tab 1. |
| `/home/seller/products/new` | CreateProductScreen | seller | NEW | Modal. |
| `/home/seller/products/:productId/edit` | EditProductScreen | seller | NEW | Modal. |
| `/home/seller/orders` | OrdersListScreen | seller | NEW (body) | Tab 2. |
| `/home/seller/orders/:orderId` | SellerOrderDetailScreen | seller | NEW | Includes `OrderStateActionButton` for state transitions. |

---

## 3. Cart route — rationale & placement

Cart is **not a bottom-nav tab** (customer shell has four tabs, none of them cart). Why:

1. The depth=1 rule means cart is used only briefly between Discover and Checkout. A persistent tab would be overkill.
2. Adding a fifth tab breaks the 4-tab tidiness locked in Phase 8.
3. The sticky cart bar (see `phase-9-customer-flows.md` §4.3) gives always-visible access when the cart is non-empty and the user is on Discover or ProductDetail.

**Route structure:** `/home/customer/cart` and `/home/customer/cart/checkout` are child `GoRoute`s **under the customer ShellRoute** — the bottom nav stays visible on the cart screen (same as Phase 8 style for sub-routes) but **hidden on checkout** (modal app bar, more focused).

**How to hide bottom nav for checkout only:** use a top-level `GoRoute` outside the ShellRoute for `/home/customer/cart/checkout`. When the user is on checkout the shell is not in the widget tree; back nav pops back to `/home/customer/cart` which re-enters the shell with the same tab index preserved.

---

## 4. Updated path constants

Add these to `lib/app/routes.dart`:

```dart
abstract class AppRoutes {
  // ... Phase 8 constants ...

  // Customer — Phase 9
  static const customerDiscover = '/home/customer/discover';
  static const customerOrders = '/home/customer/orders';
  static const customerCart = '/home/customer/cart';
  static const customerCheckout = '/home/customer/cart/checkout';
  static String customerSellerDetail(String sellerId) => '/home/customer/sellers/$sellerId';
  static String customerProductDetail(String productId) => '/home/customer/products/$productId';
  static String customerOrderDetail(String orderId) => '/home/customer/orders/$orderId';
  static String customerOrderReview(String orderId) => '/home/customer/orders/$orderId/review';

  // Seller — Phase 9
  static const sellerDashboard = '/home/seller/dashboard';
  static const sellerProducts = '/home/seller/products';
  static const sellerOrders = '/home/seller/orders';
  static const sellerStore = '/home/seller/store';
  static const sellerStoreNew = '/home/seller/store/new';
  static const sellerProductNew = '/home/seller/products/new';
  static String sellerProductEdit(String productId) => '/home/seller/products/$productId/edit';
  static String sellerOrderDetail(String orderId) => '/home/seller/orders/$orderId';
}
```

---

## 5. go_router tree additions (sketch)

Slot inside the existing customer ShellRoute:

```
ShellRoute(customer):
  GoRoute(/home/customer/discover, builder: DiscoverScreen)
    GoRoute('sellers/:sellerId', builder: SellerDetailScreen)
    GoRoute('products/:productId', builder: ProductDetailScreen)
    GoRoute('cart', builder: CartScreen)  // bottom nav still visible
  GoRoute(/home/customer/orders, builder: OrdersListScreen)
    GoRoute(':orderId', builder: CustomerOrderDetailScreen)
      GoRoute('review', builder: ReviewPlaceholderScreen)  // deferred
  GoRoute(/home/customer/messages, builder: PlaceholderScreen)  // Phase 10
  GoRoute(/home/customer/profile, builder: PlaceholderScreen)

// Top-level (outside ShellRoute — hides bottom nav):
GoRoute(/home/customer/cart/checkout, builder: CheckoutScreen)
```

Similarly for seller:

```
ShellRoute(seller):
  GoRoute(/home/seller/dashboard, builder: DashboardScreen)
  GoRoute(/home/seller/products, builder: ProductsListScreen)
  GoRoute(/home/seller/orders, builder: SellerOrdersListScreen)
    GoRoute(':orderId', builder: SellerOrderDetailScreen)
  GoRoute(/home/seller/profile, builder: StoreDetailScreen)  // reuses /store content

// Top-level modals (hide bottom nav):
GoRoute(/home/seller/store/new, builder: CreateStoreScreen)
GoRoute(/home/seller/products/new, builder: CreateProductScreen)
GoRoute(/home/seller/products/:productId/edit, builder: EditProductScreen)
```

Guards: all seller routes are enforced by the existing redirect (see `04-navigation-map.md` §3); no new redirect logic needed.

---

## 6. Deep-link additions

No new deep-link schemes in Phase 9. Existing `marketplace://invite/:token` stays the only external entry point. In-app links (share links, for example a seller sharing a product) use the internal `customerProductDetail(id)` helper and do not leave the app.

**Phase 12 consideration (flagged):** if we want shareable product URLs (`https://<domain>/p/:productId`), they must resolve to `/home/customer/products/:productId` **post-login-only** — sharing a product URL to an unreferred customer must land them on Discover's ADR-0007 empty state, not on the product page. Recommended handling: the deep-link resolver checks the visibility via `GET /products/:id`; a 404 response routes to Discover with a snackbar "You need an invite to view this store."

---

## 7. Redirect-rule clarifications

The existing `redirect()` function covers Phase 9 without changes. Two clarifications:

- `/home/customer/cart/**` is allowed for role `customer` only (matched by the `/home/customer` prefix guard).
- `/home/seller/store/new` is allowed for role `seller` (matched by `/home/seller` prefix).

The redirect does not need to inspect whether a customer has items in cart, nor whether a seller has a store — those are screen-level empty-state concerns, not route-level guards.

---

## 8. Tab preservation & back-stack behavior

`IndexedStack`-based ShellRoute behavior (from Phase 8) is preserved:

- Deep-link into `/home/customer/orders/:orderId` lands with tab index = 1 (Orders); system back returns to orders list, then to discover.
- Switching tabs never drops in-flight cart data — the CartController is a top-level provider above the ShellRoute.
- `Navigator.pop()` inside a modal (`/home/seller/products/new`) returns to whichever tab was active when the modal was opened.

---

## 9. Tab badges (new in Phase 9)

Per `03-role-shells.md` §5 the Messages tab reserves a badge (Phase 10) and Orders tab earns its badge in Phase 9.

**Source:** `activeOrdersCountProvider` derived from a periodic refresh of `GET /orders?status=...` OR the simpler `active_orders_count` already in `GET /sellers/me/dashboard` for sellers.

**Widget:** see `phase-9-components-diff.md` §TabBadge — a small dot with optional count, positioned at the top-right of the icon.

**A11y:** Badge is read as "Orders, N active" by VoiceOver — implement via `Semantics(label: ...)` on the wrapping `AppBottomNavItem`.
