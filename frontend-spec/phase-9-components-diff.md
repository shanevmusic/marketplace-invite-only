# Frontend Spec — Phase 9 Component Diff

**Phase:** 9 — UI/UX Designer deliverable.
**Audience:** Frontend Engineer adding new shared widgets under `lib/shared/widgets/` (primitives) and feature widgets under `lib/features/<feature>/widgets/` (feature-scoped).

**Principle:** reuse before introduce. Phase 8 shipped 14 design-system widgets (`AppButton`, `AppInput`, `AppCard`, `AppListTile`, `AppDialog`, `AppSkeleton`, `AppSnackbar`, `AppEmptyState`, `AppAppBar`, `AppAvatar`, `AppBottomNav`, `ChatBubble`, `FormFieldWrapper`, `RoleBadge`) plus `AppFab`. Phase 9 composes them wherever possible. Each new component below has a justification — why a Phase 8 primitive alone didn't cover it.

---

## Summary table

| # | Name | Scope | Location | Rationale |
|---|---|---|---|---|
| 1 | `QuantityStepper` | shared primitive | `lib/shared/widgets/quantity_stepper.dart` | Cart + product detail need bounded integer stepping; `AppButton` pair is too verbose, doesn't enforce bounds/a11y. |
| 2 | `ImagePicker` | feature (seller products) | `lib/features/products/seller/widgets/image_picker.dart` | Seller-only, multi-image grid with upload state per slot. Too specific for `shared/`. |
| 3 | `ImageGallery` | shared primitive | `lib/shared/widgets/image_gallery.dart` | Product detail, reusable later (conversations, store header). |
| 4 | `ProductTile` | feature (discover/products) | `lib/features/products/customer/widgets/product_tile.dart` | Grid-tile variant not covered by `AppCard`/`AppListTile`; specific 2-col grid aspect. |
| 5 | `CartLineItem` | feature (cart) | `lib/features/cart/widgets/cart_line_item.dart` | Cart + checkout + order detail + seller order detail all show this row; stand-alone for consistency. |
| 6 | `OrderStatusChip` | shared primitive | `lib/shared/widgets/order_status_chip.dart` | Status rendering used in 4+ screens. |
| 7 | `OrderStatusTimeline` | shared primitive | `lib/shared/widgets/order_status_timeline.dart` | Vertical stepper with timestamps; distinct from Material's ExpansionTile/Stepper. |
| 8 | `OrderStateActionButton` | feature (orders seller) | `lib/features/orders/seller/widgets/order_state_action_panel.dart` | Seller-only action panel driven by the state machine. |
| 9 | `CustomerDeliveryStatusWidget` | feature (orders customer) | `lib/features/orders/customer/widgets/customer_order_delivery_status.dart` | ADR-0014 invariant: must live in customer/ tree, zero coordinate fields. |
| 10 | `MetricCard` | shared primitive (thin) | `lib/shared/widgets/metric_card.dart` | Dashboard metric blocks. Thin wrapper over `AppCard`; codified for consistency. |
| 11 | `MoneyField` / `CurrencyField` | shared primitive | `lib/shared/widgets/money_field.dart` | Form field that accepts localized currency input and yields `int minorUnits`. |
| 12 | `formatMoney()` helper | shared format | `lib/shared/format/money.dart` | Not a widget — the MANDATORY formatter for every rendered amount. |
| 13 | `TabBadge` | shared primitive | `lib/shared/widgets/tab_badge.dart` | Dot / count badge overlay for `AppBottomNavItem`. |
| 14 | `StickyCartBar` | feature (cart) | `lib/features/cart/widgets/sticky_cart_bar.dart` | Persistent bottom pill on Discover/ProductDetail; too specific for shared. |
| 15 | `AddressForm` | feature (checkout) | `lib/features/cart/widgets/address_form.dart` | Reusable structured address form matching backend `Address` schema. |

Nothing else new. Below are the full specs.

---

## 1. `QuantityStepper`

**Purpose:** bounded integer stepper. Used by ProductDetail (choosing add-to-cart qty), Cart (line qty), future admin forms.

**Props:**
```dart
class QuantityStepper extends StatelessWidget {
  final int value;
  final int min;       // default 1
  final int max;       // default 99; product detail passes min(stock, 99)
  final ValueChanged<int> onChanged;
  final bool enabled;  // default true
  final String? semanticsLabelPrefix;  // "Quantity of ${productName}"
}
```

**Layout:** horizontal pill, height 40dp, radius `radiusPill`, `surfaceVariant` bg.
```
[ − ]   3   [ + ]
 ^44dp ^centered ^44dp
```
- `−` and `+` are `InkWell`-wrapped; 44×44 tap target (a11y minimum per `06-accessibility-i18n.md`).
- Center is `titleMedium` number, `onSurfaceVariant`.

**States:**
- Decrement disabled when `value <= min` (opacity 38%, no ripple).
- Increment disabled when `value >= max`.
- Whole widget disabled → both buttons inactive.

**Semantics:**
- `−` button: `Semantics(button: true, label: "Decrease ${semanticsLabelPrefix ?? 'quantity'}, current $value")`.
- `+` button: analogous.
- Current value: wrapped in `Semantics(liveRegion: true, label: "Quantity $value")` so changes announce on screen readers.

---

## 2. `ImagePicker` (seller products)

**Purpose:** multi-image grid with per-slot upload state. Max 8 images; first slot is the "Primary" image.

**Props:**
```dart
class SellerImagePicker extends StatefulWidget {
  final List<ImageSlot> slots;                // controlled from form state
  final int max;                              // default 8
  final ValueChanged<List<ImageSlot>> onChange;
  final Future<String> Function(File file) uploadFn;  
  //   ^ returns s3_key on success. Throws on failure.
}

sealed class ImageSlot {
  const ImageSlot();
}
class PendingLocal extends ImageSlot { final File file; }
class Uploading extends ImageSlot { final File file; final double? progress; }
class Uploaded extends ImageSlot { final String s3Key; final String? previewUrl; }
class FailedUpload extends ImageSlot { final File file; final String message; }
```

**Layout:** 3-column grid (90dp square tiles, gap 8dp). Each tile is a stacked `Container(radiusSm)` with:
- Image preview (from File or previewUrl).
- Top-left "Primary" chip (only on index 0 when there is at least one image).
- Overlay states: spinner (Uploading), `Icons.error + Retry` (FailedUpload).
- Top-right `×` button to remove.

One extra trailing tile with `Icons.add_a_photo_outlined` centered → opens picker.

**Interactions:**
- Tap `+` → native image_picker single → append `PendingLocal` → upload starts.
- Long press a tile → promote to index 0 (swap). Announces "Primary image set."
- Tap `×` → remove.
- Tap failed tile → retry upload.

**Semantics:** each tile has `Semantics(label: "Image $index${isPrimary ? ', primary' : ''}${stateHint}", button: true)`.

**Backend dependency (BACKEND GAP B-G1):** `POST /products/{id}/image-upload-url` → pre-signed PUT. Until endpoint ships, the picker shows `isEnabled=false` state with a sub-caption "Image upload coming soon" — see `phase-9-seller-flows.md` §0.

---

## 3. `ImageGallery`

**Purpose:** horizontally-swipeable image viewer with page dots. Used on ProductDetail.

**Props:**
```dart
class ImageGallery extends StatelessWidget {
  final List<String> imageUrls;       // resolved URLs (not raw s3_key)
  final double aspectRatio;           // default 16 / 9
  final BoxFit fit;                   // default cover
  final VoidCallback? onExpandTap;    // future: open fullscreen
}
```

**States:**
- Empty list → `Container(surfaceVariant, aspectRatio)` with `Icons.image_not_supported_outlined` centered.
- Individual image load error → same placeholder for that slide only.
- Loading → `AppSkeleton.SkeletonBox` overlay.

**A11y:** PageView announces "Image $n of $total" on page change (liveRegion).

---

## 4. `ProductTile` (customer discover/grid)

**Props:**
```dart
class ProductTile extends StatelessWidget {
  final String productId;
  final String name;
  final int priceMinor;
  final String currencyCode;
  final String? thumbUrl;
  final int? stockQuantity;   // null = unlimited
  final VoidCallback onTap;
}
```

**Layout (grid tile, 2-col):**
```
[ Image square (aspectRatio 1:1, radiusSm) ]
  (overlay chip "Out of stock" if stockQuantity == 0)
Padding vertical=space2:
  Text(name, maxLines=2, titleSmall)
  Text(formatMoney(priceMinor, currencyCode), bodyMedium, primary color)
```

Background: `colorScheme.surface`. Full tile is an `InkWell`.

**States:** loading → `SkeletonBox(1:1)` + 2 `SkeletonLine`. Disabled when `stockQuantity == 0` → tap still navigates (product detail handles the CTA), so no visual disable.

**Semantics:** `Semantics(button: true, label: "$name, ${formatMoney(priceMinor)}${stockLabel}", onTap: onTap)`.

---

## 5. `CartLineItem`

**Purpose:** canonical cart/order line row. One component for cart, checkout review, seller order detail items, customer order detail items.

**Props:**
```dart
class CartLineItem extends StatelessWidget {
  final String name;
  final int unitPriceMinor;
  final String currencyCode;
  final int quantity;
  final String? thumbUrl;
  final bool editable;                      // cart true; order-detail false
  final ValueChanged<int>? onQuantityChanged;
  final VoidCallback? onRemove;
  final String? semanticsLabel;
}
```

**Layout (editable):**
```
[thumb 48dp]  name (titleSmall, 2 lines)       formatMoney(unit * qty)
              formatMoney(unitPriceMinor) each  [− qty +]  [ × ]
```

**Layout (read-only):**
```
[thumb 48dp]  name (titleSmall, 2 lines)                ×qty
              formatMoney(unitPriceMinor) each         formatMoney(unit * qty)
```

**Semantics:** single `Semantics(label: "$name, $quantity at ${formatMoney(unit)}, total ${formatMoney(unit*qty)}")` wrapping.

---

## 6. `OrderStatusChip`

**Purpose:** consistent rendering of an order status across all order screens.

**Props:** `final String status;` + `final OrderStatusChipSize size = sm;`

**Mapping:**

| Status | Icon | Fg | Bg |
|---|---|---|---|
| pending | `hourglass_empty` | onSurface | surfaceVariant |
| accepted | `check_circle_outline` | onSecondaryContainer | secondaryContainer |
| preparing | `restaurant_outlined` / `inventory_2_outlined` | onSecondaryContainer | secondaryContainer |
| out_for_delivery | `local_shipping_outlined` | onPrimary | primary |
| delivered | `task_alt` | onSuccessContainer (ext) | successContainer |
| completed | `verified_outlined` | onSuccessContainer | successContainer |
| cancelled | `cancel_outlined` | onErrorContainer | errorContainer |

Shape: pill, radius `radiusPill`, h=24 (sm) / 32 (md), horizontal padding 10dp. Label is `labelSmall` TitleCase ("Out for delivery" not "out_for_delivery"). Single source of truth: `_statusHumanLabel(status)` in the same file.

**Semantics:** chip is `Semantics(label: "Status: $humanLabel")`.

---

## 7. `OrderStatusTimeline`

**Purpose:** vertical stepper on order detail.

**Props:**
```dart
class OrderStatusTimeline extends StatelessWidget {
  final String currentStatus;
  final DateTime placedAt;
  final DateTime? acceptedAt;
  final DateTime? preparingAt;
  final DateTime? outForDeliveryAt;
  final DateTime? deliveredAt;
  final DateTime? completedAt;
  final DateTime? cancelledAt;
}
```

**Layout:** vertical list of 6 steps (or 5 + cancelled badge if cancelled):
```
● Placed          ${time}
|
● Accepted        ${time}
|
○ Preparing       (not yet)
|
○ Out for delivery
|
○ Delivered
|
○ Completed
```
Filled circle when timestamp present; hollow when future. Line between circles uses `outline` color (past) / `outlineVariant` (future). Active step (current) has a pulsing ring animation (respect `disableAnimations`).

**Cancelled case:** show up to the last fulfilled step, then a single red `● Cancelled  ${time}`.

**Semantics:** whole widget is `Semantics(label: "Order status: ${currentHumanLabel}, placed ${relative(placedAt)}")` — each step additionally labeled for screen reader traversal.

---

## 8. `OrderStateActionButton` / `OrderStateActionPanel`

**Purpose:** seller-side sticky bottom action panel whose content switches by current order status. Encapsulates the state machine so screens don't duplicate logic.

**Props:**
```dart
class OrderStateActionPanel extends ConsumerWidget {
  final String orderId;
  final String status;
  final String? driverAssignmentStatus;  // indicates requested_driver state
}
```

Internally reads an `orderStateActionsProvider(orderId, status)` that returns a `List<OrderAction>`:
```dart
sealed class OrderAction {
  final String label;
  final OrderActionKind kind;    // primary | secondary | destructive
  final Future<void> Function() run;   // calls the backend + shows dialogs
}
```

**Buttons rendered** use `AppButton` variants (primary/secondary/destructive text). See `phase-9-seller-flows.md` §3.3 for the per-status matrix.

**Semantics:** each button's semanticsLabel mirrors the label plus a verb hint, e.g. "Accept order, next step of fulfillment".

**Idempotency note:** the `run` functions catch `409 DELIVERY_ALREADY_STARTED` silently and refresh; they only throw for real errors. This is the widget-level contract that honors ADR-0003 idempotency.

---

## 9. `CustomerDeliveryStatusWidget`

**Purpose:** Phase 9 customer-facing widget showing status + ETA without any coordinate information. Precursor to the Phase 10 `CustomerDeliveryView` live map (the Phase 10 widget composes this one).

**Props (MANDATORY SHAPE — see ADR-0014 enforcement in `phase-9-customer-flows.md` §5.3):**
```dart
class CustomerOrderDeliveryProps {
  final DeliveryStatus status;       // enum — preparing, out_for_delivery, delivered, etc.
  final int? etaSeconds;             // maps from CustomerDeliveryView.eta_seconds
  final DateTime? etaUpdatedAt;
  final DateTime? startedAt;
  final DateTime? deliveredAt;
  final String destinationLabel;     // customer's own address, preformatted

  // HARD INVARIANT: no coordinate fields allowed.
  //   - no driverLat, driverLng
  //   - no sellerLat, sellerLng
  //   - no breadcrumbs, distanceMeters, driverId, sellerId
}
```

**Layout:**
```
Row:
  Large status chip (OrderStatusChip variant md)
  spacer
  ETA badge: "Arriving in ~${humanDuration(etaSeconds)}"   (only when status == out_for_delivery and etaSeconds != null)
subdued caption:
  "Delivered at ${formatDateTime(deliveredAt)}" OR "Last updated ${relativeTime(etaUpdatedAt)}"
```

No map. No driver. No distance. No breadcrumbs.

**Tests (gate to merge):**
1. **Source-grep test** (`test/widget_invariants_test.dart`) reads this file and asserts zero occurrences of the strings `lat`, `lng`, `coord`, `driverId`, `sellerId`, `breadcrumb`, `distance` outside of a whitelist of harmless Dart words (add `latitude`/`longitude` to a blocklist).
2. **Widget test** constructs the widget with the full expected prop set and asserts no text node contains a decimal that matches a coordinate-like pattern `(\d{1,3}\.\d{4,})`.

**Semantics:** `Semantics(liveRegion: true, label: "${statusLabel}${etaLabel ?? ''}")`.

---

## 10. `MetricCard`

**Purpose:** dashboard metric with label, value, optional caption, optional tap action.

```dart
class MetricCard extends StatelessWidget {
  final String label;
  final String value;      // already formatted (use formatMoney for money metrics)
  final String? caption;
  final VoidCallback? onTap;
  final Widget? trailing;  // e.g. small trend indicator (Phase 12)
}
```

**Layout:** reuses `AppCard(variant: onTap != null ? interactive : default)`; inside: label (`labelMedium`, `onSurfaceVariant`), value (`headlineSmall`), caption (`bodySmall`).

**Semantics:** when `onTap != null`, entire card is `Semantics(button: true, label: "$label, $value${caption ?? ''}")`.

---

## 11. `MoneyField`

**Purpose:** form field for entering monetary amounts. Yields `int minorUnits`. Used on product create/edit.

**Props:**
```dart
class MoneyField extends StatefulWidget {
  final int? initialMinor;
  final String currencyCode;         // e.g. "USD"
  final ValueChanged<int?> onChanged;
  final String? errorText;
  final String? label;               // used for a11y; wrap in AppFormField for visual label
}
```

**Behavior:**
- Uses `NumberFormat.currency(locale, symbol, decimalDigits)` derived from `currencyCode`.
- Strips all non-numeric on input; treats as minor units directly (e.g. user typing "999" with USD → $9.99).
- Displays the formatted amount above the bare input in bodySmall ("$ 9.99").
- `TextInputType.number` keyboard.

**Validation:** returns null when empty; the field is required-or-not at the form level.

---

## 12. `formatMoney()` helper — **MANDATORY**

Location: `lib/shared/format/money.dart`.

```dart
String formatMoney(
  int minorUnits, {
  String currencyCode = 'USD',
  Locale? locale,
  bool symbol = true,
  int? decimalDigitsOverride,
});
```

**Rules:**
1. Every rendered amount in the app goes through this function. No `x / 100`, no ad-hoc formatting.
2. Tests grep `lib/features/**/*.dart` for `/ 100` and `NumberFormat.*format(.*\/.*)` patterns and fail if found.
3. Decimal digits default to `NumberFormat.currency(locale: ..., name: currencyCode).decimalDigits`.
4. Negative amounts render with a leading `-` (used for refunds in later phases).

---

## 13. `TabBadge`

**Purpose:** small count/dot badge overlaid on a bottom nav icon.

**Props:**
```dart
class TabBadge extends StatelessWidget {
  final int? count;     // null → dot only
  final bool visible;   // false hides entirely
  final Widget child;   // the icon
}
```

**Layout:** Stack with positioned (top: -2, right: -6) `Container` 16dp pill, bg `error` (or `primary` for attention-only dot), text `labelSmall onError`. If count > 99 render "99+".

**Semantics:** wrap the composed widget `Semantics(label: "$baseLabel, $count ${pluralize(count, 'active', 'active')}")` at the call site (AppBottomNavItem).

**Integration:** `AppBottomNavItem` gets a new optional `badgeCount: int?` prop that threads into this.

---

## 14. `StickyCartBar` (cart)

**Props:**
```dart
class StickyCartBar extends ConsumerWidget {
  final VoidCallback onTap;
}
```

Reads `cartControllerProvider`; renders nothing if cart is empty. Otherwise a bottom-anchored 56dp bar:
```
[ N items · formatMoney(subtotal) ][ View cart > ]
```

Uses `Positioned(bottom: 0)` within the Discover/ProductDetail screen's `Stack`. Respects bottom nav height (offset by 56dp when shell is visible).

**A11y:** `Semantics(button: true, label: "View cart, $n items, total ${formatMoney(subtotal)}")`.

---

## 15. `AddressForm`

**Props:**
```dart
class AddressForm extends StatefulWidget {
  final Address? initial;
  final ValueChanged<Address?> onChanged;  // null = invalid
  final bool enabled;
}
```

Builds the structured `Address` per backend `backend/app/schemas/orders.py`:
line1* / line2 / city* / region / postal / country* (ISO-2 length 2) / notes. Asterisk = required.

Uses `AppFormField` + `AppTextField`. Keyboard hints via `autofillHints: [AddressLine1, ...]`.

---

## Cross-cutting guardrails

- **No color literals** in any new component — token-driven only (rule inherited from Phase 8 `02-component-library.md` §16).
- **No Duration literals** for animation — use `AppMotion`.
- **Every new component** has a `semanticsLabel` or builds one internally; none is silent for screen readers.
- **Destructive actions** in any new component still require an `AppDialog` confirm before firing.
- **Loading state as a property**, never a sibling swap — same rule as Phase 8.
- **ADR-0014 file boundary:** any file under `lib/features/orders/customer/` or `lib/features/tracking/customer/` **must not import** from `lib/features/tracking/internal/` or `lib/features/orders/seller/`. Add a static analysis / custom lint to `analysis_options.yaml` in Phase 9. Until the lint lands, the Frontend Engineer enforces this manually on PR review.
