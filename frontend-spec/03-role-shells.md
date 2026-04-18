# Frontend Spec — 03 Role Shells

**Audience:** Frontend Engineer building the four role home shells. Phase 8 ships these as **scaffolds with placeholder tab contents**; Phase 9–11 fill them in.

Each shell is hosted by a `ShellRoute` (go_router) at `/home/<role>/...` so that the bottom nav survives tab changes. Role enforcement is done in the redirect (see `04-navigation-map.md`), not inside the shell widget.

Common structure across all four shells:

```
Scaffold
├── AppTopBar (role-specific title + trailing actions)
├── IndexedStack (tab bodies, preserve state across tab switches)
├── AppBottomNav (role-specific items)
└── AppFab? (role-specific; not every role has one)
```

---

## 1. Customer Shell — `/home/customer`

**Feel:** discovery-first. The first tab is where most time is spent. Role badge never displayed to customer ("customer" is the default — no need to announce).

### 1.1 Tabs

| Tab | Path | Initial route | Icon (outline / filled) | Label | Notes |
|---|---|---|---|---|---|
| 0 | `/home/customer/discover` | Default | `storefront_outlined` / `storefront` | Discover | Referral-scoped feed. See empty state §1.4. |
| 1 | `/home/customer/orders` | — | `receipt_long_outlined` / `receipt_long` | Orders | Customer's order history + active order. |
| 2 | `/home/customer/messages` | — | `chat_bubble_outline` / `chat_bubble` | Messages | Conversations with seller(s). Unread count badge. |
| 3 | `/home/customer/profile` | — | `person_outline` / `person` | Profile | Name, email, referring seller name, logout. |

### 1.2 App bar

- **Discover:** title = referring seller's store name if available, else `"Discover"`. Trailing: `Icons.search` (Phase 9: F33). No back button.
- **Orders:** title `"Orders"`. Trailing: `Icons.filter_list` (Phase 9).
- **Messages:** title `"Messages"`. Trailing none.
- **Profile:** title `"Profile"`. Trailing none.

### 1.3 Primary action / FAB

No FAB on customer shell. Customer primary actions (add to cart, place order, message seller) are contextual to individual screens.

### 1.4 First-time / empty states

- **Discover (unreferred customer):** `AppEmptyState` per `02-component-library.md` §10.1. Headline: *"You need a seller invite"*. **Do not render a "no products" layout** (ADR-0007).
- **Discover (referred, seller has no products yet):** headline *"[Seller name] hasn't added products yet"*, subhead *"Check back soon, or message them directly."*, CTA *"Message seller"*.
- **Orders (no orders):** headline *"No orders yet"*, subhead *"When you place an order, it'll appear here."* No CTA.
- **Messages (no conversations):** headline *"No messages yet"*, subhead *"Conversations with your seller appear here."* CTA *"Message [Seller name]"* when a referring seller exists.
- **Profile:** never empty.

### 1.5 Phase 8 placeholder

Ship tab bodies as `AppEmptyState` widgets with "Coming in Phase 9" copy where the real content isn't built — **except Discover**, which must render the proper ADR-0007 referral-gated empty state for unreferred customers from day 1. That empty state is a Phase 8 invariant test target.

---

## 2. Seller Shell — `/home/seller`

**Feel:** business dashboard. Lifetime sales and active orders are the first thing the seller sees. The seller's role badge appears in the app bar (on profile photo) and in lists.

### 2.1 Tabs

| Tab | Path | Initial route | Icon | Label |
|---|---|---|---|---|
| 0 | `/home/seller/dashboard` | Default | `dashboard_outlined` / `dashboard` | Dashboard |
| 1 | `/home/seller/products` | — | `inventory_2_outlined` / `inventory_2` | Products |
| 2 | `/home/seller/orders` | — | `receipt_long_outlined` / `receipt_long` | Orders |
| 3 | `/home/seller/profile` | — | `store_outlined` / `store` | Store |

### 2.2 App bar

- **Dashboard:** title = store name (or `"Dashboard"` if no store yet). Trailing: share icon (copies seller referral link to clipboard — F02).
- **Products:** title `"Products"`. Trailing: search.
- **Orders:** title `"Orders"`. Trailing: filter (by status).
- **Store (profile):** title `"Store"`. Trailing: edit (pencil) icon opens store edit screen.

### 2.3 Primary action / FAB

- **Products tab:** `AppFab.extended` — icon `Icons.add`, label *"Add product"*. Phase 9 wires it to the product create screen.
- Other tabs: no FAB.

### 2.4 First-time / empty states

- **Dashboard (no store created yet):** this is the post-signup landing state for a brand-new seller. Large `AppEmptyState`: icon `Icons.storefront_outlined`, headline *"Create your store"*, subhead *"Give it a name and city so customers can find you."*, CTA *"Create store"* → `/home/seller/store/new`.
- **Dashboard (store created, zero sales):** show the dashboard chrome (two metric cards: Lifetime sales 0, Active orders 0) and an inline hint *"Share your referral link to invite your first customer."* with a copy-link chip.
- **Products (zero products):** headline *"No products yet"*, subhead *"Add your first product to start selling."*, CTA *"Add product"*.
- **Orders (zero):** headline *"No orders yet"*, subhead *"Orders from your customers will appear here."* No CTA.

### 2.5 Phase 8 placeholder

Dashboard displays the "Create your store" empty state on first landing — even before Phase 9 builds the store creation screen. The CTA can route to a `/home/seller/store/new` placeholder screen with a "Coming in Phase 9" notice. All other seller tabs are placeholder empty states.

---

## 3. Driver Shell — `/home/driver`

**Feel:** utility. Minimal visual chrome, high tap-target-to-screen ratio. Drivers work one-handed.

### 3.1 Tabs

| Tab | Path | Initial route | Icon | Label |
|---|---|---|---|---|
| 0 | `/home/driver/available` | Default | `list_alt_outlined` / `list_alt` | Available |
| 1 | `/home/driver/active` | — | `local_shipping_outlined` / `local_shipping` | Active |
| 2 | `/home/driver/history` | — | `history` / `history` | History |
| 3 | `/home/driver/profile` | — | `person_outline` / `person` | Profile |

### 3.2 App bar

- **Available:** title `"Available deliveries"`. Trailing: refresh icon (pull-to-refresh also supported).
- **Active:** title shows `"Active — Order #XXXX"` when one is in progress, `"No active delivery"` otherwise.
- **History:** title `"Completed"`.
- **Profile:** title `"Profile"`.

### 3.3 Primary action / FAB

No FAB. Primary actions ("Accept", "Mark delivered") are inline on the active-order screen — see the `InternalDeliveryView` internal action bar.

### 3.4 First-time / empty states

- **Available (no assignments):** headline *"No deliveries assigned"*, subhead *"When admin assigns you a delivery, it'll appear here."*. No CTA. Gentle: drivers will look at this view a lot.
- **Active (no active):** headline *"Nothing active right now"*, subhead *"Accept a delivery from the Available tab to start."*.
- **History (new driver):** headline *"No completed deliveries yet"*.
- **Profile:** shows name, role badge (driver), and a logout button.

### 3.5 Phase 8 placeholder

All four tabs ship as empty states per §3.4. `/home/driver/active` is reachable but shows "no active" until Phase 10 builds `InternalDeliveryView`.

---

## 4. Admin Shell — `/home/admin`

**Feel:** operational console. Dense information, minimal celebration. Admin role badge shown in profile.

> **Note (D3):** the admin surface may split into a web client in Phase 11 (D3 open). This shell is the **mobile admin fallback** — the minimum admin can do on a phone. Assume it will exist regardless of D3 outcome; the Flutter web build path keeps it usable.

### 4.1 Tabs

| Tab | Path | Initial route | Icon | Label |
|---|---|---|---|---|
| 0 | `/home/admin/invites` | Default | `mail_outline` / `mail` | Invites |
| 1 | `/home/admin/users` | — | `people_outline` / `people` | Users |
| 2 | `/home/admin/settings` | — | `settings_outlined` / `settings` | Settings |
| 3 | `/home/admin/logs` | — | `event_note_outlined` / `event_note` | Logs |

### 4.2 App bar

- **Invites:** title `"Invites"`. Trailing: overflow with "Referral graph" (F29 — Phase 11).
- **Users:** title `"Users"`. Trailing: search + filter (role, disabled).
- **Settings:** title `"Platform settings"`.
- **Logs:** title `"Activity"`.

### 4.3 Primary action / FAB

- **Invites tab:** `AppFab.extended` — icon `Icons.add`, label *"Issue invite"*. Opens bottom sheet with role picker + expiry.
- **Users tab:** no FAB (drivers are created via invite → admin-targeted admin_invite, not a separate CTA).
- Settings / Logs: no FAB.

### 4.4 First-time / empty states

- **Invites (no invites ever issued — fresh admin install):** headline *"Issue your first invite"*, subhead *"Seed the network by inviting a seller or another admin."*, CTA *"Issue invite"*.
- **Users (pre-bootstrap):** in a brand-new system there's only the admin themselves. Headline *"Just you so far"*, subhead *"Invite sellers and drivers to populate the network."*
- **Settings:** never empty — platform defaults always present (retention days, grace hours).
- **Logs:** headline *"No activity yet"*.

### 4.5 System stats

The Invites tab is the admin home and surfaces at-a-glance stats (above the invite list) in Phase 11:

```
┌ Users: 124    Sellers: 12    Drivers: 3    Pending invites: 8 ┐
```

In Phase 8, render the card with placeholder zeros and a "Data coming in Phase 11" footnote.

### 4.6 Phase 8 placeholder

All four tabs ship as empty states or the single placeholder stats card. The Issue-Invite FAB opens a placeholder dialog ("Coming in Phase 11"). No admin actions are wired in Phase 8.

---

## 5. Shared conventions across role shells

- **Tab switching:** `IndexedStack` preserves tab state. Changing tabs does not drop scroll position, form input, or in-flight requests.
- **Deep links into a non-default tab** (e.g. `/home/customer/orders`) land on that tab with the correct `currentIndex`.
- **Tab order is stable** — never rearrange based on badge counts.
- **Badges on tabs:** Messages tab shows unread count (Phase 10). Orders tab shows active-order count dot (Phase 9). Admin Invites tab shows pending-assignment-queue count dot (Phase 11).
- **Bottom nav is always visible** inside the shell. Hiding it (e.g. on a full-screen chat) is a Phase 10 concern — Phase 8 does not need to support it.
- **Logout** is always reachable via Profile tab → Logout button → confirmation dialog. No other logout entry point.
