# Frontend Spec — README

**Phase:** 8 — UI/UX Designer deliverable.
**Author:** UI/UX Designer (this agent).
**Consumer:** Frontend Engineer implementing Phase 8 scaffold + auth, and Phases 9–11.

This directory is the **design source of truth** for the Flutter app. Everything under it is design-time spec, not code. Do not place implementation files here — they belong under `/frontend/lib/`.

---

## Table of Contents

| File | Purpose |
|---|---|
| [00-overview.md](./00-overview.md) | Design philosophy, platforms, state-management decision (Riverpod), navigation framework (go_router), accessibility baseline. |
| [01-design-tokens.md](./01-design-tokens.md) | Color palette (light + dark), typography scale, spacing, radii, elevation, motion. Maps 1:1 onto Flutter `ThemeData`. |
| [02-component-library.md](./02-component-library.md) | Reusable widgets: Button, Input, Form Field Wrapper, Card, List Tile, Chat Bubble, **two distinct Map Views** (ADR-0014), Snackbar, Dialog / Bottom Sheet, Empty State, Skeleton Loader, Avatar + Badge, App Bar, Bottom Nav, FAB. |
| [03-role-shells.md](./03-role-shells.md) | Bottom-nav structure, app bar, FAB, and first-time empty states for the four role home shells: customer, seller, driver, admin. |
| [04-navigation-map.md](./04-navigation-map.md) | Full route tree (go_router), deep-link schemes, invite-link flow, redirect rules, guarded routes. |
| [05-auth-flows.md](./05-auth-flows.md) | Phase 8 auth journeys: first-time invite, returning cold start, login failure, invite errors, signup with/without role_choice, logout, offline, transparent token refresh. |
| [06-accessibility-i18n.md](./06-accessibility-i18n.md) | AA contrast, Dynamic Type, touch targets, semantic labels, keyboard support, motion reduction; intl/ARB scaffold for future locales. |

---

## How the Frontend Engineer should consume this

1. **Start with `00-overview.md`** to understand the design philosophy and the three invariants (referral-scoped visibility, asymmetric delivery, messaging opacity) that drive spec decisions.
2. **Wire tokens first.** `01-design-tokens.md` becomes `lib/app/theme/`. Everything else depends on this. Don't build screens before `context.colors`, `context.spacing`, etc. exist.
3. **Build the component library second.** `02-component-library.md` becomes `lib/shared/widgets/`. Build them test-first — each component has enough spec to unit-test variants and states in isolation.
4. **Stub the role shells third.** `03-role-shells.md` + `04-navigation-map.md` together give you the routing skeleton. Ship all four shells with placeholder tab contents (empty states) before implementing any auth flow.
5. **Implement auth last.** `05-auth-flows.md` drives the real work of Phase 8. The shells and components are primitives that make auth screens trivial to assemble.
6. **Keep accessibility in the critical path, not as a retrofit.** `06-accessibility-i18n.md` is a checklist — run through it on every screen before opening a PR.

Suggested PR cadence for Phase 8: **1.** theme + tokens, **2.** component library (split into 2–3 PRs by related components), **3.** navigation scaffold + role shell stubs, **4.** auth screens + flows, **5.** end-to-end integration test for Flows 1, 2, 7.

---

## Design invariants that must not be violated

These are the three product-level rules the design enforces at the Flutter layer. A PR that weakens any of these should be rejected.

1. **Referral-scoped visibility (ADR-0007).** Unreferred customer on Discover sees a first-class "You need a seller invite" empty state — **never** a "no products" layout. See `02-component-library.md` §10.1 and `03-role-shells.md` §1.4.
2. **Asymmetric delivery visibility (ADR-0014).** `CustomerDeliveryView` and `InternalDeliveryView` are **separate widgets in separate folders**. No `role: UserRole` flag on a single widget. A customer screen must be structurally unable to import the internal widget. See `02-component-library.md` §7.
3. **Messaging opacity (ADR-0009, ADR-0013).** `ChatBubble` accepts **already-decrypted** plaintext. It must not accept ciphertext, must not have a "decrypt" knob, and plaintext must not leak to logs / analytics. See `02-component-library.md` §6.

---

## Key design decisions locked in Phase 8

- **State management:** Riverpod 2.x, codegen style. (`00-overview.md` §3.)
- **Routing:** go_router 14.x with a single `redirect` callback as the role guard. (`04-navigation-map.md` §3.)
- **Theme primitive:** Material 3 `ColorScheme` + `TextTheme`, extended with `ThemeExtension` for success/warning and role badges. System theme mode default in Phase 8. (`01-design-tokens.md`.)
- **Fonts:** system defaults only in Phase 8 (SF Pro / Roboto). No bundled font. (`01-design-tokens.md` §2.)
- **Map provider:** **deferred to Phase 10 (D4)** — widgets written against an abstract interface.
- **Secure storage:** `flutter_secure_storage` under keys `auth.access`, `auth.refresh`, `auth.user_json`, and (Phase 11) X25519 private keys. No other auth state persisted. (`05-auth-flows.md`.)
- **i18n:** intl + ARB, English only in Phase 8, Spanish scaffolded for Phase 10. (`06-accessibility-i18n.md` §2.)

---

## Open questions to flag to the Orchestrator

These are decisions that are **outside the UI/UX Designer's authority** but the spec must note for Phase 9+:

1. **D4 — Map provider (Mapbox vs Google Maps vs flutter_map / OSM).** Needed before Phase 10. Both `CustomerDeliveryView` and `InternalDeliveryView` are written against an abstract `MapProvider` so the decision is low-cost at code level, but there's a licensing / cost decision the Orchestrator must resolve. **Recommendation:** `flutter_map` + OSM for v1 (zero ToS risk, no API keys, acceptable tile quality for delivery ETA). Google Maps if a funder insists on polished feel.
2. **D5 — Push provider (FCM + APNs direct vs OneSignal).** Needed before Phase 9 (order/message push in F30/F31). Affects signup flow only marginally (permission prompt timing). **Design recommendation:** request push permission on the **first entry into a role shell**, not at signup — users are more likely to grant after seeing value.
3. **D3 — Admin surface: Flutter admin tab vs web client.** Spec assumes both: the Flutter admin shell is the mobile fallback and is designed independently of the potential web client. If Orchestrator decides to build a web client only, the Flutter admin shell can be deprioritized.
4. **Final brand primary color.** Tokens use a placeholder indigo `#3F3D9E`. One-file swap to update if a brand designer provides alternates.
5. **Icon set.** Phase 8 uses Material Icons. Consider switching to Phosphor or Lucide in Phase 10 for chat/tracking affordance consistency. No blocker.
6. **Manual invite entry on Login screen.** `05-auth-flows.md` §3 mentions an "I have an invite" link on login; decide whether to add a paste-token dialog or keep the flow deep-link-only. Recommendation: deep-link-only in Phase 8 (simpler); add manual entry in Phase 9 if support feedback demands it.
7. **Splash minimum dwell time.** Spec sets 300 ms minimum. Verify with Orchestrator whether that should be 0 ms (snappier) or longer (brand moment). Currently a reasonable default.

---

## Phase 9–11 concerns anticipated in this spec

The spec deliberately goes slightly beyond Phase 8 to avoid rework later:

| Concern | Where anticipated |
|---|---|
| Product tile / product detail screen | `02-component-library.md` §4 Card + §5 List Tile — composable pattern |
| Chat UI (Phase 10) | `02-component-library.md` §6 Chat Bubble |
| Delivery tracking UX (Phase 10) | `02-component-library.md` §7 (two separate widgets) + `03-role-shells.md` §3 driver active tab + `04-navigation-map.md` §1.3 |
| Admin surface (Phase 11) | `03-role-shells.md` §4 (assuming mobile Flutter fallback regardless of D3 outcome) |
| Push notifications (F30/F31, Phase 9) | `README.md` D5 and permission-prompt timing guidance |
| RTL / Spanish (Phase 10, 14) | `06-accessibility-i18n.md` §2.4 |
| Seller dashboard metrics (F28) | `03-role-shells.md` §2.4 empty states + chrome layout |
| Referral graph (F29) | `03-role-shells.md` §4.1 trailing overflow link |

What is **not** designed yet and should be picked up by a future design task: product detail page layout, cart UI, checkout screen, order detail layout, conversation list and thread layout, review submission, store edit screens, admin referral graph visualization.

---

## Change control

Any change to a design token, component API, or flow documented here requires a spec update in the same PR as the code change. If a token is renamed, bump the heading with `(deprecated: renamed from <old>)` for one release cycle before removing. Flutter code should never diverge silently from this spec.
