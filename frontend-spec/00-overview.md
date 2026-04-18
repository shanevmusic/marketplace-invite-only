# Frontend Spec — 00 Overview

**Phase:** 8 — UI/UX Designer deliverable
**Audience:** Frontend Engineer (Flutter) implementing Phase 8 scaffold + auth, and Phases 9–11.
**Scope of this document:** Design philosophy, platform targets, state management, navigation, and accessibility baseline. All token/component/flow detail lives in the companion files.

---

## 1. Design Philosophy

This is an **invite-only** marketplace. The UI must feel like a closed club, not a public mall: deliberate, uncluttered, quietly opinionated. Every participant was personally vouched for — the visual language should reflect that trust. Mobile-first, high legibility, minimal chrome, one primary action per screen. Typography and spacing do most of the work; color is used sparingly, usually to signal role, status, or destructive action. Nothing should feel "social-network loud." When in doubt, show less.

Three product invariants shape the UI directly:

1. **Referral-scoped visibility (ADR-0007).** An unreferred customer's discovery feed is not "empty" — it's a first-class "you need a seller invite" state with actionable guidance. Never render a zero-results UI that implies products exist but are filtered out.
2. **Asymmetric delivery visibility (ADR-0014).** Customer and driver/seller see **different components**, not the same component with a flag. This is enforced at the widget library level (see `02-component-library.md` §Map View).
3. **Messaging is opaque to the server (ADR-0009, ADR-0013).** The UI shows decrypted plaintext; decryption happens client-side. Message composition UI never sends plaintext to any logging, analytics, or error-reporting surface.

---

## 2. Platforms & Framework

| Item | Choice |
|---|---|
| Framework | Flutter 3.22+ (Dart 3.4+), stable channel |
| Target platforms | iOS 14+, Android 8+ (API 26+) |
| Platform widgets | Material 3 primitives with a custom `ThemeData`; Cupertino-style feel achieved via design tokens, not `CupertinoApp`. One codebase, one visual language. |
| Minimum device | 4.7" (iPhone SE gen-2), 360 dp Android baseline |
| Orientation | Portrait primary for Phase 8–10; admin screens may unlock landscape in Phase 11 |
| Web build | Not targeted in v1, but keep widgets layout-agnostic (no gesture-only affordances) so a future `flutter build web` is a small lift |

---

## 3. State Management — Riverpod 2.x

**Decision:** Riverpod 2.x (code-generation style via `riverpod_generator`) over Bloc.

**Rationale:**
- **Compile-time safety:** `@riverpod` generated providers give strong typing end-to-end — the state shape is the function's return type. Bloc's event/state classes are unchecked by comparison, and the boilerplate scales with feature count.
- **Test-friendliness:** overriding a provider in a `ProviderContainer` is one line; Bloc requires mocking the bloc stream. For a team writing widget tests against auth, order, and delivery flows, this difference compounds.
- **Simpler mental model for this team:** a provider is a function. There is no event → handler → state pipeline to trace. For an app this size (≈30 screens at v1), the Bloc ceremony is overhead without a proportional benefit.
- **Async-first:** `AsyncValue<T>` aligns naturally with `loading / data / error` UI states, which is most screens in this app (auth, discover, orders, tracking).
- **Ecosystem fit:** pairs cleanly with `go_router` (a `ref.listen` on an `authStateProvider` drives redirect).

**Provider hierarchy (sketch; detailed wiring is the Frontend Engineer's call):**
```
authControllerProvider          // AsyncValue<AuthSession?>  — drives boot + redirect
sessionProvider                 // derived, null when logged out
currentUserProvider             // derived User from session
apiClientProvider               // singleton, reads access token from sessionProvider
secureStorageProvider           // flutter_secure_storage wrapper
themeProvider                   // light/dark/system
featureFlagProvider             // no-op in Phase 8, hook-point for later
```

**Conventions:**
- One controller-class (`AsyncNotifier` / `Notifier`) per feature, co-located under `lib/features/<feature>/application/`.
- No global `ChangeNotifier`. No `Provider.of` from `provider` package.
- Never read a provider inside `initState`; use `ref.listen` in `build` or `ConsumerStatefulWidget.didChangeDependencies`.

---

## 4. Navigation — go_router

**Decision:** `go_router` 14.x, declarative routing with typed routes (`go_router_builder`).

**Key capabilities used:**
- **Deep links** for invite URLs — see `04-navigation-map.md`.
- **Redirect callback** as the single source of truth for "where should this user be?" — reads `authControllerProvider`, resolves role, lands user on `/home/:role`.
- **ShellRoute** per role to host the bottom nav.
- **Refresh stream** wired to the auth controller so route evaluation re-runs on login / logout / token refresh.

**Conventions:**
- Path constants live in `lib/app/routes.dart` — never hard-code `'/login'` in a widget.
- Every route declares required role(s); redirect enforces centrally (don't duplicate role checks in widgets).
- Deep links pass through the redirect, not `push`/`go` in random places — a tap on `marketplace://invite/abc` from a cold start lands at `/signup?invite_token=abc` via redirect, never via ad-hoc parsing in `main()`.

---

## 5. Accessibility Baseline (Phase 8)

Detail in `06-accessibility-i18n.md`. The non-negotiables for Phase 8:

- **WCAG 2.1 AA contrast** on all text and icons over their backgrounds. Tokens in `01-design-tokens.md` are pre-checked.
- **Dynamic Type:** all text uses `Theme.of(context).textTheme.*` — no hard-coded font sizes. Scale up to 200% without layout breakage on auth screens.
- **Minimum touch target 44×44 dp** on every interactive element (buttons, list tiles, icon buttons).
- **Semantic labels:** every `IconButton`, `InkWell`-wrapped custom widget, and non-text-only interactive has a `Semantics` label. Error messages are announced via `SemanticsService.announce`.
- **VoiceOver / TalkBack:** form fields expose `labelText` as the accessible name; password field announces masking state; auth errors are wrapped in a `Semantics(liveRegion: true, ...)`.
- **Reduced motion:** respect `MediaQuery.disableAnimations` — when true, cross-fades and slides become instant snaps.

---

## 6. Anticipating Phases 9–11

This spec intentionally goes slightly beyond the Phase 8 minimum so the Frontend Engineer doesn't have to rewrite primitives later. Specifically:

| Phase | Needed primitive | Defined in |
|---|---|---|
| 9 (seller/customer flows) | Card, List Tile, Product tile pattern (via Card + List Tile + Image), Empty State, Skeleton Loader, FAB | `02-component-library.md` |
| 10 (messaging + tracking) | Chat Bubble, two distinct Map View components, Snackbar, Bottom Sheet | `02-component-library.md`, `03-role-shells.md` |
| 11 (admin) | List Tile variants, Dialog, Data-table-ish list (reuse List Tile + App Bar action), Badge | `02-component-library.md` |

Phase 8 only needs to *implement* Splash, Invite Landing, Signup, Login, Error states, and four placeholder role home shells. Everything else is defined so later phases can pull from a settled library.

---

## 7. Out-of-Scope for Phase 8

- Seller dashboard content (F28) — placeholder only.
- Product discovery UI (F11) — placeholder only, but the unreferred-customer empty state IS designed (critical invariant).
- Messaging UI (F21) — chat bubble component is specified; screen is not.
- Delivery tracking UI (F20) — two map view components are specified; screens are Phase 10.
- Map provider (D4), push provider (D5), admin surface (D3) — see `README.md` for open questions.
