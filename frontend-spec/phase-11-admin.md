# Phase 11 — Admin Panel (UI/UX spec)

Single-codebase Flutter admin (Decision D3): the admin panel is a role-gated
section of the same app, not a separate web build. Admin routes live under
`/home/admin/*` and are protected by the existing go_router `_redirect`.

References: `03-role-shells.md` (shell pattern), `04-navigation-map.md` (path
conventions), `phase-8-*` (shell architecture), `01-design-tokens.md` (tokens).

---

## 1. Goals

1. Give admins a single pane to operate the marketplace: users, content,
   aggregate analytics, and operational jobs.
2. Reuse the same Flutter app — no separate web build, no parallel design
   system, no separate auth. (ADR: D3.)
3. Enforce admin-only access at the **route** layer so no widget is ever
   built for a non-admin.
4. Preserve all Phase 8–10 tokens, components, and navigation idioms.

---

## 2. Information architecture

AdminShell has **four tabs** (IndexedStack for state preservation), replacing
the Phase 8 stub (`Invites / Users / Settings / Logs`):

| Tab       | Path                        | Purpose                                            |
|-----------|-----------------------------|----------------------------------------------------|
| Users     | `/home/admin/users`         | Directory of every account; search, filter, detail |
| Content   | `/home/admin/content`       | Products, moderation, reports queue                |
| Analytics | `/home/admin/analytics`     | Platform-wide KPIs + top sellers                   |
| Ops       | `/home/admin/ops`           | Retention config, purge job, system status         |

Tab order is fixed. Default landing path when the admin logs in is
`/home/admin/users` (replacing the old `/home/admin/invites`, which becomes an
**action** inside the Users tab).

Sub-pages that push on top of the shell (hide bottom nav):

| Sub-page             | Path                                    |
|----------------------|-----------------------------------------|
| User detail          | `/home/admin/users/:id`                 |
| Issue invite modal   | dialog (not a route)                    |
| Product detail       | `/home/admin/content/products/:id`      |
| Top sellers drawer   | dialog                                  |

---

## 3. Route guard

`_redirect` in `app_router.dart` already checks `role != 'admin'` on
`/home/admin/*` and pushes to `AppRoutes.homeFor(role)`. Phase 11 tightens the
fallback: when a non-admin hits **any** admin path (directly or via a deep
link), redirect to `/error/unknown` with a 403-style copy block.

Copy for the 403 screen (existing `UnknownErrorScreen`):
- Headline: "Admin area"
- Subhead: "You don't have access to this section."
- CTA: "Go home" → `AppRoutes.homeFor(role)`.

---

## 4. Design tokens & components

No new tokens. Reuse:

- Spacing: `AppSpacing.s1..s6` (4, 8, 12, 16, 24, 32).
- Typography: `context.textStyles.{headlineSmall, titleMedium, bodyMedium,
  bodySmall}`.
- Colors: `context.colors.{primary, error, onSurface, onSurfaceVariant,
  surfaceContainer}`.
- Components: `AppTopBar`, `AppBottomNav`, `AppListTile`, `AppCard` (new helper
  built on existing primitives), `AppButton`, `AppEmptyState`, `AppDialog`,
  `AppSnackbar`, `AppInput` (text search), `AppChip` (filters).
- Money: `formatMoney(int minorUnits)` shared util — no client-side math.

Admin uses **status chips** with semantic color mapping:

| Status      | Chip color                         |
|-------------|------------------------------------|
| active      | `surfaceContainer` / `onSurface`   |
| suspended   | `errorContainer` / `onErrorContainer` |
| disabled    | `errorContainer` / `onErrorContainer` |
| out_of_stock| `tertiaryContainer`                |

---

## 5. Users tab

### 5.1 List screen

Layout:
- Sticky top bar: search (`AppInput`, debounced 250 ms) + role filter
  (`AppChip` row: All / Admin / Seller / Customer / Driver) + status filter
  (All / Active / Suspended).
- Body: `ListView.builder` of `AppListTile` rows. Each row shows avatar
  (first letter), display name, email muted, trailing role badge + status
  chip. Tap → `/home/admin/users/:id`.
- Pagination: cursor-based (backend returns `next_cursor`), infinite scroll
  with a loading spinner at the bottom.
- FAB: "Issue invite" → dialog (see §5.3).

States:
- **Loading (first page)**: full-page `CircularProgressIndicator`.
- **Empty**: `AppEmptyState(icon: people, headline: "No users match this
  filter.")`.
- **Error**: retry button + humane message.
- **Suspended user**: status chip; tap-through still works.

### 5.2 Detail screen

Sections (vertical):
1. **Header card**: display name, email, role, status chip, created-at
   timestamp, suspend/unsuspend button (destructive if active, primary if
   suspended).
2. **Invite tree** card:
   - "Referred by" row (user + date) if present, else "Joined via admin
     invite."
   - "Referred users" list — collapsed behind a count if > 5.
3. **Metadata** card: user id, phone, referring_seller_id.

Suspend action: opens `AppDialog` with a required reason (`AppInput`,
min 1 char, max 500), primary action "Suspend account" (destructive). On
success: snackbar "User suspended." and refresh detail.

Unsuspend: single-tap, no reason required, confirmation dialog.

### 5.3 Issue-invite dialog

Fields:
- Role target (`DropdownButtonFormField`: admin / seller / customer / driver).
- Expires in days (`AppInput` numeric, default 7, 1–365).

Submit → POST `/admin/invites`. On success, show the token as a read-only
field with a **Copy** button, and a snackbar "Invite issued." The token is
only returned once — copy it now.

Acceptance criteria (Users tab):
- Search filters within 500 ms of typing.
- Role + status filters combine (AND).
- Pagination loads next page without losing scroll position.
- Suspend + unsuspend round-trip updates the list within 1 s.
- Non-admin cannot reach any Users screen (route guard).

---

## 6. Content tab

### 6.1 Products list

- Same layout as Users list: search (`q`) + status filter (All / Active /
  Disabled / Out of stock). No seller filter in the list (filter from the
  detail screen link instead).
- Each row: product name (bold), price via `formatMoney(price_minor)`, seller
  id (muted), status chip.
- Tap → `/home/admin/content/products/:id`.

### 6.2 Product detail + moderation

- Header: name, image (if available), price, stock.
- Actions: **Disable** (opens reason dialog, min 1 / max 500) or **Restore**
  (single tap) depending on current status.
- Seller card: display name + link to `/home/admin/users/:sellerId`.
- "History" card: disabled_at + disabled_reason if disabled.

### 6.3 Reports queue (stub)

Tab-level empty state: "No open reports." Backend endpoints for reports
land in a later phase; the UI scaffolds a tab so future work drops in
without re-arranging shell tabs.

Acceptance criteria (Content tab):
- `formatMoney(price_minor)` is the ONLY way money renders.
- Disable + restore flow round-trips in < 1 s and updates chip color.

---

## 7. Analytics tab

Top-level cards, in order:

1. **KPI strip** (4 tiles): Total GMV (formatted money), Orders, Active users
   (30d), Seller count.
2. **Active users** card: 24h / 7d / 30d as small counters.
3. **Role breakdown** card: seller / customer / driver / admin counts.
4. **Top sellers** card: top 10 from `/admin/analytics/top-sellers`, showing
   display name + lifetime revenue (via `formatMoney`) + order count.

Empty state: when the platform has zero delivered orders, KPI strip shows
`formatMoney(0)` and an inline hint "Metrics populate once orders are
delivered."

Acceptance criteria (Analytics tab):
- GMV is **always** `formatMoney(total_gmv_minor)`. No client division.
- Endpoint shape matches `AdminAnalyticsOverview` schema.
- Data refreshes on pull-to-refresh (Riverpod `refresh`).

---

## 8. Ops tab

Sections:

1. **Message retention**: current value, slider / input (1–365 days), Save
   button → POST `/admin/ops/retention-config`.
2. **Purge job**: "Run purge now" destructive-primary button → POST
   `/admin/ops/purge-messages/run`. Show result snackbar with
   `purged_count`.
3. **System info**:
   - Alembic migration version (from `/admin/ops/migration-version`).
   - WebSocket connections: stub ("Real-time metrics coming soon.").
4. **Danger zone**: placeholder for future destructive ops.

Acceptance criteria (Ops tab):
- Retention Save shows the new value immediately (optimistic).
- Purge button disables while the request is in flight.
- Migration version renders verbatim from the backend; "—" when unknown.

---

## 9. States summary

| State      | Presentation                                           |
|------------|--------------------------------------------------------|
| Loading    | `CircularProgressIndicator` (screen) or skeleton rows  |
| Empty      | `AppEmptyState` with icon + headline                   |
| Error      | `AppEmptyState(icon: error, headline: "Can't load…")` + retry |
| 403        | Route guard redirects → `/error/unknown`               |
| Rate-limited | Snackbar "Too many requests. Try again shortly."     |

---

## 10. Acceptance criteria (top-level)

1. Admin sees 4 tabs — Users, Content, Analytics, Ops — in that order.
2. Any non-admin hitting `/home/admin/*` is redirected to `/error/unknown`.
3. All money rendering uses `formatMoney(int)`.
4. Suspend/unsuspend and disable/restore round-trip < 1 s on a local
   backend.
5. Analytics overview returns the full shape; UI renders zero values without
   crashing.
6. ADR-0014 still holds: any delivery view opened from admin uses the
   internal tracking widget tree (admin may see coordinates).
7. ADR-0007 still holds: admin viewing of customer/seller data does not
   expose referral chains deeper than 1 hop on the customer side.

---

## 11. Open questions (deferred)

- Reports/complaints queue — spec'd as a stub; backend in a later phase.
- Live WebSocket connections monitor — backend plumbing lands later.
- Bulk actions (select many users) — not in Phase 11.
