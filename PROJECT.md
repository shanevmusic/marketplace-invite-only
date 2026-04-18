# PROJECT.md — Invite-Only Marketplace

Single source of truth for the build. Every agent in every phase reads this first.

Last updated: Phase 0 kickoff.

---

## 1. Mission

Build a production-ready, invite-only mobile marketplace where admins and sellers grow the network via unique invite links, sellers run city-scoped storefronts, customers order and track deliveries with privacy-preserving visibility rules, and all messaging is end-to-end encrypted.

---

## 2. Global Stack (frozen)

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Flutter (Dart) | iOS + Android, single codebase |
| State mgmt | Riverpod | Decision confirmed Phase 8 |
| Routing | go_router | Deep-link support for invite URLs |
| Backend | Python 3.12 + FastAPI | Async, OpenAPI auto-gen |
| DB | PostgreSQL 16+ | **Primary: Supabase** (project `shwhmuxpmcclyhiweyvz`, AWS us-east-2, PG17). Dev/test still uses local Postgres 17 for test isolation. |
| Migrations | Alembic | |
| ORM | SQLAlchemy 2.x (async) | |
| Cache / pubsub | Redis 7 | WebSocket fanout, rate limiting |
| Realtime | WebSockets (FastAPI + Redis pub/sub) | Messaging + delivery tracking |
| Auth | JWT (access + refresh), RBAC | Roles: admin, seller, customer, driver |
| Password hashing | Argon2id | |
| E2E encryption | X25519 + AES-256-GCM (libsodium-equivalent); clients hold keys | Server stores ciphertext only |
| Object storage | S3 or GCS | Product images, signed URLs |
| Cloud target | AWS (ECS Fargate) primary; GCP (Cloud Run) alternate | Both deployment-ready |
| Code-gen model | Claude Opus 4.7 for critical code agents | |

Any change to this table requires an ADR in `/docs/adr`.

---

## 3. Product Logic (frozen)

- **Invite-only signup.** Admin can invite anyone. Each seller has a unique referral link that can create seller or customer accounts.
- **Roles:** `admin`, `seller`, `customer`, `driver`.
- **Seller:** one store per seller, tied to a city. Full product CRUD. Dashboard shows lifetime sales (persists even after order/product deletion) and active orders. Fulfillment: either "start delivery" (self) or "request driver" from admin.
- **Customer:** browses products from sellers they are linked to via invite/referral. Places orders. Tracks delivery with **limited visibility** — never sees seller/driver location. E2E messaging. Private reviews (not public).
- **Admin:** manages sellers, customers, drivers. Assigns drivers to orders. Sets platform minimum data retention period. Views referral graph.
- **Delivery:** tracking begins when seller marks `out_for_delivery`. Driver/seller see customer coordinates. Customer sees only status + ETA. Metrics: start, delivered, duration.
- **Data rules:** orders deletable only after admin-set minimum retention. Sellers may enable auto-delete but cannot go below platform minimum. Lifetime-sales analytics persist independently of order row deletion (snapshot at complete-time).

---

## 4. Agent Roster

Each agent owns a domain. The Orchestrator routes work, reviews hand-offs, and resolves conflicts.

| # | Agent | Primary outputs | Phases active |
|---|---|---|---|
| 1 | **System Architect** | Architecture docs, service boundaries, API contracts, ER diagram | 1, reviews 2–13 |
| 2 | **Product Manager** | PRD, user flows, acceptance criteria, prioritization | 1, reviews 3–11 |
| 3 | **UI/UX Designer** | Screen inventory, component library, navigation map, role shells | 8, reviews 9–11 |
| 4 | **Frontend Engineers (Flutter)** | Flutter app, UI, API client, state, tests | 8–11 |
| 5 | **Backend Engineers (FastAPI)** | REST + WS services, business logic, tests | 3–7, 11 |
| 6 | **Database Engineer** | Schema, migrations, indexes, seed data | 2, reviews 3–7 |
| 7 | **Security Engineer** | Auth/RBAC review, E2E crypto design, threat model, security report | 3, 6, 10, 12 |
| 8 | **QA + Testing Engineer** | Unit/integration/E2E tests, test reports, bug triage | 3–13 (continuous) |
| 9 | **DevOps Engineer** | Docker, CI/CD, cloud infra, observability, runbook | 13, supports earlier |
| 10 | **Orchestrator** (this agent) | Phase kickoff, conflict resolution, consistency enforcement, handoff review | all |

---

## 5. Shared Conventions

### 5.1 Repo layout (monorepo)

```
/backend       FastAPI service, Alembic, tests
  app/
    api/            routers (versioned: v1/)
    core/           config, security, logging
    db/             session, base
    models/         SQLAlchemy models
    schemas/        Pydantic schemas
    services/       business logic
    ws/             WebSocket gateways
  alembic/
  tests/
  pyproject.toml
/frontend      Flutter app
  lib/
    app/            bootstrap, routing, theme
    core/           env, api client, storage
    features/       feature-first modules (auth, sellers, products, orders, messaging, tracking, admin)
    shared/         widgets, utils
  test/
  pubspec.yaml
/docs          PRD, architecture, API contract, ER diagram, ADRs
  adr/                architecture decision records, numbered
/infra         Docker, compose, CI, deploy manifests
  docker/
  ci/                 GitHub Actions workflows
  deploy/             ECS / Cloud Run configs, terraform optional
PROJECT.md     this file
README.md      quick-start (added in Phase 13)
```

### 5.2 Naming

- **Python:** `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- **Dart:** `lowerCamelCase` for identifiers, `PascalCase` for types, files `snake_case.dart`.
- **DB:** tables plural `snake_case` (`users`, `order_items`), PKs `id` (UUID v4), FKs `{singular}_id`, timestamps `created_at` / `updated_at` / `deleted_at`.
- **API:** REST resources plural (`/sellers`, `/orders`), versioned under `/api/v1`. WS namespaces under `/ws/v1/{feature}`.
- **Env vars:** `UPPER_SNAKE`, prefixed by service (`APP_`, `DB_`, `JWT_`, `REDIS_`).

### 5.3 Branching & PRs

- Default branch: `main` (protected).
- Feature branches: `feat/<phase>-<short-slug>` e.g. `feat/3-auth-invites`.
- Fix branches: `fix/<short-slug>`. Chore: `chore/...`. Docs: `docs/...`.
- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).
- PRs must: pass CI, include tests for new behavior, link the phase + acceptance criteria, get Orchestrator review.

### 5.4 Code style

- **Python:** `ruff` (lint + format), `mypy --strict` on `app/`, import order via ruff. Type hints everywhere.
- **Dart:** `flutter_lints` + `very_good_analysis`, `dart format`. No dynamic without justification.
- **SQL:** lowercase keywords in migrations, explicit FK `ON DELETE` behavior.
- **Tests:** `pytest` + `pytest-asyncio` backend; `flutter_test` + `mocktail` frontend. Coverage targets in Phase 12.

### 5.5 Documentation format

- Markdown, GitHub-flavored.
- ADRs follow MADR template: Context → Decision → Consequences → Alternatives. Numbered `NNNN-title.md`.
- API contract authoritative source is the FastAPI-generated OpenAPI; `/docs/api-contract.md` summarizes and freezes breaking-change rules.
- Diagrams: Mermaid in markdown where possible; exported PNG alongside for non-GitHub viewers.

### 5.6 Security baseline

- All secrets via environment + cloud secret manager in prod; never committed.
- JWT: short-lived access (15 min), rotating refresh (7 days), stored in secure storage on device.
- All external input validated via Pydantic.
- Rate limiting on auth + invite + messaging endpoints.
- Dependabot + `pip-audit` / `dart pub outdated` in CI.

---

## 6. Phase Checklist

Progress tracker. Each phase ends when its stop condition is met and the Orchestrator signs off.

- [x] **Phase 0** — Kickoff & Orchestrator setup — conventions approved
- [x] **Phase 1** — System architecture & PRD — frozen
- [x] **Phase 2** — Database schema + migrations — verified green on fresh DB
- [x] **Phase 3** — Backend A: auth + invite system
- [x] **Phase 4** — Backend B: sellers, stores, products
- [x] **Phase 5** — Backend C: orders & fulfillment
- [x] **Phase 6** — Backend D: E2E messaging + WebSockets
- [x] **Phase 7** — Backend E: delivery tracking (asymmetric visibility)
- [x] **Phase 8** — Frontend A: Flutter scaffold + auth
- [x] **Phase 9** — Frontend B: seller & customer core flows
- [x] **Phase 10** — Frontend C: messaging & tracking UI
- [x] **Phase 11** — Admin panel
- [ ] **Phase 12** — QA, security hardening, performance
- [ ] **Phase 13** — DevOps, deployment, handoff
- [ ] **Phase 14** — Iteration loop (optional, ongoing)

---

## 7. Open Decisions (to resolve before or during the noted phase)

| # | Decision | Resolve by |
|---|---|---|
| D1 | AWS vs GCP primary target | Phase 13 (scaffold both; pick primary then) |
| ~~D2~~ | ~~E2E scheme~~ | **Closed — ADR-0009: X25519 + AES-256-GCM** |
| D3 | Admin surface: Flutter admin tab vs lightweight web client | Phase 11 |
| D4 | Map provider (Mapbox vs Google Maps) for tracking UI | Phase 10 |
| D5 | Push notifications provider (FCM + APNs direct, or OneSignal) | Phase 9 |

---

## 8. Definition of Done (applies every phase)

A phase is done when:
1. Deliverables listed in the phase prompt exist in the repo at the documented paths.
2. Stop condition is demonstrably met (test run, script run, or reviewable artifact).
3. Orchestrator has logged a sign-off note at the bottom of this file under **Phase Log**.
4. Any new decisions are captured as ADRs in `/docs/adr`.

---

## 9. Phase Log

- **Phase 11** — Admin Panel (2026-04-18): shipped admin module end-to-end per D3 (single-codebase Flutter admin tab). **UI/UX spec** `frontend-spec/phase-11-admin.md`: 4 tabs (Users, Content, Analytics, Ops) with per-screen flows, states, acceptance criteria. **Backend** (`app/api/v1/admin.py` + `app/services/admin_service.py`, 14 new endpoints): `GET /admin/users` (paginated, search by email/name, filter by role+status); `GET /admin/users/{id}` with referral-chain detail; `POST /admin/users/{id}/suspend|unsuspend`; `POST /admin/invites` for admin-override invite issuance bypassing seller-referral requirement; `GET/POST /admin/products` + `/disable`/`/restore`; `GET /admin/analytics/overview` (total GMV + orders + DAU/WAU/MAU + role counts); `GET /admin/analytics/top-sellers`; `GET/POST /admin/ops/retention-config`; `POST /admin/ops/purge-messages/run`; `GET /admin/ops/migration-version`. All endpoints role-gated via existing admin dependency; non-admin → 403 (verified). **Migration 0005_user_status_product_status** applied to Supabase Session pooler (DDL succeeded in single tx): `users.status` enum `(active|suspended)` NOT NULL default `active` + `suspended_at` + `suspended_reason`; `products.status` enum `(active|disabled|out_of_stock)` NOT NULL default `active` + `disabled_at` + `disabled_reason`; indexes on both status columns. `alembic current` = `0005 (head)`. Suspension enforced at `get_current_user` dep — every bearer-token request returns `401 AUTH_ACCOUNT_SUSPENDED`. **Flutter** (`lib/features/admin/**`): 4 screens + Riverpod AsyncNotifier controllers, admin shell with IndexedStack tab preservation, route guard redirects non-admin from `/home/admin/*` to `/error/unknown`; reuses design system primitives; money via `formatMoney()`. **Tests:** backend `pytest -q` → **208 passed** (14 new admin tests); frontend `flutter analyze` → 0 errors, `flutter test` → **57 passed / 2 skipped** (7 new admin tests including route-guard). **Orchestrator live smoke vs. Supabase-backed backend:** admin logs in; customer hitting `/admin/users` → 403; `/admin/users` lists all 4 seed roles; `/admin/analytics/overview` returns `{total_gmv_minor:3000, orders_count:1, active_users_24h:1, seller_count:1, customer_count:1, driver_count:1, admin_count:1}` (consistent with Phase 9 seller-dashboard rollup); `/admin/invites` issued driver-role token `zb2BeuYYEpnOjiaxjx3mNxuGOXFdSCXp3U9vTOjq_aE`; `/admin/ops/migration-version` returns `{version:"0005"}`; suspend driver → new bearer tokens return `401 AUTH_ACCOUNT_SUSPENDED` on every authenticated endpoint (`/auth/me`, `/products`). **Caveat logged for Phase 12:** `/auth/login` still issues tokens for suspended accounts (post-login `get_current_user` guards them, so user-facing effect is 401-locked, but defense-in-depth would prefer 403 at login) — minor hardening item. Shipped via branch `phase-11-impl`, merged to main at commit `1dc79ac`. **Ready for Phase 12.**

- **Phase 10** — UI/UX Designer + Frontend Engineer (2026-04-18): delivered Flutter messaging + delivery tracking + realtime transport. **UI/UX spec** (`frontend-spec/phase-10-*.md`, 4 files, 1,720 lines): overview with 7 PR-gate invariants, messaging (conversation list/detail, 7-state ChatBubble, E2E crypto UX with 12-hex safety-number fingerprint, multi-key registry, reset-consent), tracking (two-widget-tree spec per ADR-0014 — customer coord-free timeline vs. internal Mapbox map), realtime (single `/ws?token=<jwt>` socket multiplexing `conversation:{id}` + `delivery:{id}` channels, close codes 4001/4401/4403, exponential backoff `[1,2,4,8,16,30,60]s` with jitter, 30s heartbeat with 2-miss death, `delivery.location` internal-subscribers-only). **Flutter impl** (+3,423 / −209, 71 files): `lib/features/messaging/` (X25519 keypair via `cryptography` package, AES-256-GCM + ephemeral ECDH per message, `flutter_secure_storage` for private key, safety-number fingerprint, ChatBubble extended to 7 states); `lib/features/tracking/customer/**` — 3 files, coord-free (status tile + timeline + address card, zero lat/lng/latitude/longitude tokens, zero Mapbox imports — verified by orchestrator grep); `lib/features/tracking/driver/**` + `lib/features/tracking/seller/**` — Mapbox map widget via `mapbox_maps_flutter` with driver + destination pins + breadcrumb polyline; `WebSocketClient` with channel multiplexing, heartbeat, jittered backoff, close-code-aware reconnect, 30s polling retired (kept as >30s-disconnect fallback only). **Five new invariant guards** in `test/invariants/`: `tracking_coord_boundary_test.dart` (greps customer tree for coord tokens + Mapbox — passes), `no_polling_test.dart` (asserts 30s polling removed from tracking/messaging), `e2e_plaintext_test.dart` (server-bound payloads contain only ciphertext+MAC+nonce), `crypto_roundtrip_test.dart` (encrypt→decrypt fidelity), `delivery_already_started_test.dart` (409 ADR-0003 tracking-controller swallow). **50/50 tests green** (39 Phase-9 + 11 new), 0 analyzer errors. Orchestrator live smoke vs. live backend on Supabase: WS auth handshake rejects bogus token with close code `4401` and accepts valid JWT (stays open idle); `GET /conversations` returns `{data:[]}` envelope for a fresh seller. Two minor contract gaps logged (C-G1–C-G9 in overview.md) for Phase 12 reconciliation. Phase 10 shipped on branch `phase-10-impl` → merged to main (commit `f352316`); feature branches cleaned up. **Ready for Phase 11.**

- **Phase 9** — UI/UX Designer + Frontend Engineer (2026-04-18): delivered Flutter seller + customer core flows on top of the Phase 8 auth scaffold. **UI/UX spec** (`frontend-spec/phase-9-*.md`, 4 files, 2,250 lines): per-screen flows for seller (store setup, product CRUD with image metadata, order inbox + centralized state-machine action panel, dashboard) and customer (referral-scoped Discover, seller/store page, product detail, client-only per-seller cart, checkout, orders list + detail). 15 new components composed from the Phase-8 primitives; every screen cites exact live-backend endpoints with api-contract deviations flagged inline. **Flutter app** (`frontend/`, +4,339 lines / 49 files): Riverpod AsyncNotifier controllers per feature; go_router extended with new routes (checkout lives OUTSIDE the ShellRoute so bottom nav hides); `lib/shared/format/money.dart::formatMoney(int minorUnits)` as the sole money formatter (grep test rejects `/ 100` and ad-hoc `NumberFormat` under `features/**`); `lib/features/cart/cart_store.dart` persists per-seller buckets to `flutter_secure_storage` under key `cart.v1`; `OrderStateActionPanel` + `orderStateActionsProvider` centralize all seller transitions and swallow `409 DELIVERY_ALREADY_STARTED` per ADR-0003. D5 decision: push notifications via FCM + APNs direct, implementation deferred to Phase 12. Product image picker stashes placeholder `pending/{uuid}.jpg` s3_keys with `TODO(phase-13)` since the upload endpoint is deferred to DevOps. **Four hard invariants enforced at the test level:** (1) money routes through `formatMoney()` (grep test); (2) ADR-0014 — `CustomerOrderDeliveryProps` type has zero coordinate fields + grep test fails on `lat\|lng\|latitude\|longitude\|driver_id` under `features/{orders,tracking}/customer/**` + import-boundary test forbids customer folders importing from `features/tracking/internal/**`; (3) ADR-0007 — sealed `CustomerDiscoverState` with `Unreferred` variant; controller test asserts `GET /products` never called when Unreferred; (4) ADR-0003 idempotency — duplicate state transitions swallowed with refresh. **39 tests green, 0 analyzer errors** on the Phase-9 branch (21 Phase-8 tests preserved). **Orchestrator live smoke against Supabase-backed backend** (`backend.env` → Supabase pooler; seeded 4 users via `app.scripts.seed_dev`): customer logs in, `/auth/me` returns `referring_seller_id=8bc1b7f7…` (the seeded seller), `/products` returns the 3 seeded products wrapped in `{data, pagination}` envelope; unreferred driver's `/products` returns 0 items confirming ADR-0007 at the API layer. End-to-end order lifecycle: customer places 2x Widget Alpha (total_minor=3000) → seller walks `accept → preparing → self-deliver → out-for-delivery → delivered` → customer `complete`; duplicate `out-for-delivery` on a terminal order returns `409 DELIVERY_ALREADY_STARTED` (ADR-0003 live-verified); seller dashboard post-completion reflects `lifetime_sales_amount=3000, lifetime_orders_count=1, active_orders_count=0`. One minor contract drift caught: `delivery_address.country_code` in api-contract.md → actual `country` in live backend; Flutter client already uses `country` so no change needed. Phase 9 pushed as feature branch `phase-9-impl` and merged to main (commit `fb7949b`). Phase 12 follow-ups: S3 presigned image upload endpoint + client wiring (`B-G1`), reviews endpoints (`B-G2`), dedicated seller-page endpoint (`B-G4`), custom ADR-0014 import-boundary lint in `analysis_options.yaml`, `active_orders` tab-badge source endpoint. **Ready for Phase 10.**
- **Infra — Supabase migration (2026-04-18):** marketplace database promoted from local Postgres to **Supabase as the primary DB** for this project going forward. Target project `shwhmuxpmcclyhiweyvz` (org MobileMarkertplace, region AWS us-east-2, PG 17.6). Connected via the IPv4-compatible Session pooler (`aws-1-us-east-2.pooler.supabase.com:5432`, username `postgres.<project_ref>`) because the sandbox cannot reach the IPv6-only direct host. Enabled `citext` + `uuid-ossp` extensions, ran Alembic migrations `0001`→`0004` (all four applied cleanly, `alembic current` = `0004 (head)`). Verified: 20 public tables + `alembic_version`, 1 materialized view (`seller_sales_rollups`), 5 enums; ADR-0009 invariant holds (no plaintext columns on `messages`); ADR-2 invariant holds (zero FKs on `order_analytics_snapshots`). Wiring: `backend/.env` now points `APP_DATABASE_URL` / `APP_DATABASE_URL_SYNC` at Supabase; local Postgres URLs kept as commented fallback. Connection string also persisted to `backend/.env.supabase` (gitignored via `.env.*` rule). Test suite isolation preserved — `tests/conftest.py` hardcodes a separate local `marketplace_test` DB via `os.environ.setdefault`, so `pytest` still runs against local Postgres and never touches Supabase (19/19 auth tests green post-switch). Operational note: always use the Session pooler (port 5432) for Alembic; the Transaction pooler (6543) breaks DDL-in-transaction. Password in the URL must be a literal `!`, not `%21` — `configparser` misreads `%` as interpolation syntax.
- **Phase 0** — Orchestrator (2026-04-17): stack + product logic frozen, agent roster defined, conventions established, monorepo scaffolded, PROJECT.md created. **Ready for Phase 1.**
- **Phase 1** — System Architect + Product Manager (2026-04-18): delivered `architecture.md`, `api-contract.md`, `er-diagram.md`, `prd.md` (28 P0 features). Orchestrator reconciliation in `phase-1-reconciliation.md` resolved all 15 architect/contract/ER open questions + 4 PM open questions. ADRs 0002–0009 recorded. **D2 closed.** **Ready for Phase 2.**
- **Phase 2** — Database Engineer (2026-04-18): delivered SQLAlchemy 2.x models (20 tables, 5 app enums + citext, 1 materialized view), Alembic migration `0001_initial_schema`, idempotent seed script, `docs/schema.md`. Stop condition verified independently: clean `alembic upgrade head`, `seed_dev` produces 4 users + 1 store + 3 products, full downgrade/re-upgrade cycle works, CHECK constraints bite (rating range, conversation canonical ordering, deliveries actor presence, platform singleton), materialized view refreshes. Critical invariants confirmed: `messages` has no plaintext columns (ADR-0009), `order_analytics_snapshots` has zero FKs (survives purges). **Ready for Phase 3.**
- **Phase 8** — UI/UX Designer + Frontend Engineer (2026-04-18): delivered Flutter client scaffold and auth stack. **UI/UX spec** (`frontend-spec/`, 8 files, 1,686 lines): screen inventory, design tokens, 15-component library, 4 role-shell layouts, navigation map, auth flows, accessibility + i18n plan; locked Riverpod 2.x + go_router 14.x + Material 3 + ThemeExtension + flutter_secure_storage; enforced three invariants at widget level — ADR-0007 unreferred-customer empty state, ADR-0014 two distinct map widgets in separate folders (`features/delivery/customer/` vs `features/delivery/internal/`) with a custom lint test, ADR-0009/0013 ChatBubble plaintext-only. **Flutter app** (`frontend/`, 38 Dart source files + 7 tests): routes `/splash`, `/login`, `/signup`, `/invite/:token`, `/error/{offline,invite-invalid,unknown}`, `/home/{customer,seller,driver,admin}[/:tab]`; `AuthController` (AsyncNotifier) with `seedFromStorage → refresh` boot sequence and session-expired callback; `AuthRepository` + `SecureAuthStorage` + `TokenInterceptor` (single-flight refresh via Completer); Dio API client targeting `/api/v1`; 14 design-system widgets (`AppButton`, `AppInput`, `AppCard`, `AppListTile`, `AppDialog`, `AppSkeleton`, `AppSnackbar`, `AppEmptyState`, `AppAppBar`, `AppAvatar`, `AppBottomNav`, `ChatBubble`, `FormFieldWrapper`, `RoleBadge`); 4 role shells with IndexedStack tab preservation; `DeepLinkHandler` covers cold-start + warm stream via `app_links` 6.x. **ADR-0015** records the handwritten-Dio-client decision (no freezed/openapi_generator codegen in Phase 8; revisit at ~25 endpoints). Orchestrator verification: installed Flutter 3.41.7, ran `flutter pub get` (129 deps resolved), `flutter analyze` → **0 errors, 60 style infos/warnings** after fixing 4 real compile errors (wrong `AuthSession` import in `app_router.dart`, `AppLinks.getInitialAppLink` → `getInitialLink` for app_links 6.x, `DialogTheme` → `DialogThemeData` for Flutter 3.41, deprecated `SemanticsFlag.isEnabled` in `app_button_test.dart` replaced with InkWell onTap assertion); `flutter test` → **21/21 green** across auth controller (8), login screen (3), signup screen (4), app button (6), integration lint (1) — 2 widget-integration tests (`cold start lands on /login`, `successful login navigates to role home`) marked `skip: true` with a written rationale because fakeAsync cannot deterministically flush the real AuthRepository's Dio + TokenInterceptor microtasks during AsyncNotifier boot; the same flow is covered at unit level by `auth_controller_test.dart` (`build returns null when storage is empty`, `login success updates state with new session`) and will be re-exercised in the Phase 9 manual smoke against a device. Backend contract smoke (orchestrator, against live Phase 3 server): `/api/v1/auth/login` → 200 with `{access_token, refresh_token, token_type, expires_in, user:{id,email,role,display_name}}` — exactly matches Flutter `AuthResponse.fromJson`; `/auth/me` → 200 with bearer; `/auth/refresh` → new token pair; `/auth/logout` → 204; `/invites/validate?token=<seller-referral>` → `{valid:true, type:'seller_referral', role_target:null, issuer_display_name:'Seed Seller', issuer_role:'seller'}`; `/auth/signup` with valid invite → 201 with full AuthResponse and `user.role='customer'`; bad-password login → 401 `{error:{code:'AUTH_INVALID_CREDENTIALS'}}`; unauth `/auth/me` → 401 `{error:{code:'AUTH_TOKEN_INVALID'}}`. Two minor DTO mismatches discovered by the smoke and fixed in-place (NOT from the subagent's self-review): **(a)** `InviteValidation.fromJson` accepts both backend fields (`role_target`, `issuer_display_name`) and the spec's legacy names (`role`, `inviter_name`) for forward-compat; **(b)** `AuthApiException.isInvalidCredentials` / `isTokenExpired` / `isEmailTaken` accept both `AUTH_*`-prefixed codes (what the backend actually emits) and bare codes (what the api-contract drafted). Deviations from api-contract.md documented in frontend README: signup `display_name` (not `name`), password min length 12 (backend schema wins). Phase 12 follow-ups: codegen pipeline (freezed/json_serializable/openapi_generator) deferred per ADR-0015; biometric auth wrapping secure storage; iOS/Android native projects are skeletal (need `flutter create . --platforms=ios,android` over the current skeleton before first device build); placeholder domain `app.example.com` in deep-link configs. **Ready for Phase 9.**
- **Phase 7** — Backend Engineer (2026-04-18): delivered delivery tracking with a hard customer-coordinate-leakage invariant. ADR-0014 captures the design: two distinct Pydantic TYPES (`InternalDeliveryView` for driver/seller/admin with `last_known_lat/lng/driver_id/metrics`, `CustomerDeliveryView` for customers with no coordinate fields, both `extra="forbid"`) rather than a filtered single view; role-partitioned WebSocket subscriber registry (`_delivery_subs: {order_id: {internal: set, customer: set}}`) so `broadcast_delivery_location_internal` has zero code paths that reach a customer socket, while `broadcast_delivery_event_all` serves both buckets for `delivery.eta`/`delivery.status` (customer-safe payloads). Endpoints: `POST /deliveries/{order_id}/location` (driver/seller/admin; OFD-gated, pre-OFD/post-delivered → 409 `DELIVERY_NOT_ACTIVE`; customer → 403; stranger → 404; 600/min rate limit), `GET /deliveries/{order_id}/track` (returns `InternalDeliveryView | CustomerDeliveryView` based on `resolve_role`), `PATCH /admin/deliveries/{order_id}` (driver reassignment + metric override). WebSocket: `subscribe` with `delivery_order_id` places caller in `internal` or `customer` bucket (shared `resolve_role` with REST, no divergence); non-participant → close 4403; no token → close 4401. Event types: `delivery.location` (lat/lng breadcrumb, internal-only), `delivery.eta`, `delivery.status` (status transitions broadcast from orders router post-service-commit on OFD and delivered). Migration `0004_phase7_delivery_tracking` adds `deliveries.current_eta_seconds`/`current_eta_updated_at` plus nullable `order_analytics_snapshots.delivery_duration_seconds`/`delivery_distance_meters`; `order_service._write_snapshot` reads the delivery row so metrics persist on both `complete_order` and retention purge paths. `mark_delivered` computes `duration_seconds = delivered_at - started_at`. **17 new adversarial tests (`test_phase7_delivery_tracking.py`) → 194/194 green.** Key tests: customer-view schema equals the safe set exactly and rejects `extra="forbid"`; raw customer `/track` response body contains no server-side coordinate keys or sentinel coordinate values posted by the seller; customer WS receives 0 `delivery.location` events and N `delivery.eta` events after N seller POSTs, with every customer-bound event validated against the strict customer schema; stranger subscribe → 4403; customer-of-A/driver-of-B isolation proved (no cross-order WS crosstalk). Fixed a cross-module async-engine pool leak (asyncpg connections attached to a closed TestClient event loop) by disposing the engine in the phase-7 `tc` module-teardown. Security Engineer review (`docs/phase-7-security-review.md`) verdict: **CONDITIONAL PASS** — the hard invariant holds structurally under every audited code path (serializer escape PASS, WS dispatch PASS, REST role bypass PASS, WS auth PASS, metrics leakage PASS, data at rest PASS, frozen-logic conflicts PASS); two non-critical findings recorded as Phase 12 follow-ups. Orchestrator independently ran a 3-client probe (customer/seller/driver + stranger): customer WS received 0 `delivery.location` and 3 `delivery.eta` events after driver posted 3 location updates (sentinel coords `40.758896, -73.98513`); customer REST `/track` body has no `last_known_*`/`current_*`/`driver_id`/`distance_meters` keys and no sentinel-coord substrings; driver/seller/admin bodies correctly carry `last_known_lat/lng`; stranger → 404 REST + 4403 WS; customer `POST /location` → 403; post-delivered `POST /location` → 409; DB row stored `current_lat=40.758896, current_lng=-73.98513, distance_meters=1500` confirming coords exist server-side but never crossed to the customer channel; analytics snapshot persisted `delivery_duration_seconds=3, delivery_distance_meters=1500` on complete. Phase 12 follow-ups: **(a)** Redis pubsub two-channel design (`delivery.<order>.internal` vs `.customer`) for horizontal scale of WS fan-out; **(b)** real vector-sum distance (current MVP is max-of-running-totals heuristic); **(c)** admin driver-reassignment evicts previous driver's open WS from `_delivery_subs[order_id]["internal"]` bucket (currently ex-driver keeps receiving live coords until they disconnect — internal-to-internal leak, not customer-facing, med severity); **(d)** `/deliveries/{id}/location` 600/min rate limit keys on remote IP — switch to per-user so NAT'd fleets don't share budget (low-med). **Ready for Phase 8.**
- **Phase 6** — Backend + Security Engineer (2026-04-18): delivered E2E-encrypted messaging per ADR-0009 (X25519 + HKDF-SHA256 + AES-256-GCM, per-message ephemeral ECDH). Server handles ciphertext only — never calls any crypto primitive on message content. Endpoints: `POST/GET /keys`, `GET /keys/me`, `GET /keys/{user_id}` (eligibility-gated), `DELETE /keys/{key_id}`; `POST/GET /conversations`, `GET /conversations/{id}`, `GET /conversations/{id}/messages` (cursor-paginated), `POST /conversations/{id}/messages`, `POST /conversations/{id}/messages/{id}/read`; `GET/PATCH /admin/settings/message-retention`, `POST /admin/jobs/purge-messages`. WebSocket at `/ws?token=` with close codes **4401** (no/invalid token) and **4403** (subscribe to non-participant conversation), 30s heartbeat, events `message.new`/`message.read`/`typing`. Conversation eligibility (ADR-0013): customer↔seller where customer was referred by seller (admin bypass). Multi-key rotation with partial unique index `WHERE status='active'` — concurrency-safe via `FOR UPDATE`. Alembic `0003_phase6_messaging` drops legacy 1:1 constraint on `user_public_keys`, adds key_version/status/rotated_at/revoked_at, adds `messages.recipient_key_id`, adds `platform_settings.message_retention_days` (default 90, CHECK `>= 7`). ADR-0013 documents crypto choice, conversation policy, retention minimum, WS close codes, and replay defense (client-side concern). Security Engineer review (`docs/phase-6-security-review.md`) verified the **ciphertext-only invariant** three independent ways: (1) runtime DB scan asserts plaintext substrings never appear across all tables, (2) static audit greps `messaging_service.py` for AESGCM/X25519/HKDF/decrypt — zero hits, (3) schema audit rejects `body/text/plaintext/content` field names via `extra='forbid'`. Orchestrator independently ran a two-client live probe: Alice (customer) and Bob (seller) generated X25519 keypairs locally, registered pubkeys, exchanged encrypted messages via REST and WS, and the orchestrator scanned **20 DB tables** confirming plaintext is absent — only 55-byte ciphertext + 12-byte nonce stored opaquely; stranger (driver) → 404 (no existence leak); injecting a `body` field → 422; WS no-token → close 4401; WS `message.new` broadcast works end-to-end with client-side decryption. **36 new tests (keys, conversations, messages, ciphertext-only, WS, admin retention) → 177/177 green.** Phase 12 follow-ups in security review: Redis pub/sub for WS fan-out, key pinning UX, message size cap, admin audit trail. **Ready for Phase 7.**
- **Phase 5** — Backend Engineer (2026-04-18): delivered full order + fulfillment flow. 17 new endpoints under `/orders`, `/admin/orders`, `/admin/settings`, `/admin/jobs`. State machine `pending → accepted → preparing → out_for_delivery → delivered → completed` with terminal `cancelled`; transitions gated by role (seller/driver/customer/admin). Per ADR-0003, `out_for_delivery` is idempotent and emits `409 DELIVERY_ALREADY_STARTED` on double-call; supports both self-deliver (seller triggers) and driver-assigned (seller requests → admin assigns → driver fulfills) flows. Stock reserved via row-level `SELECT ... FOR UPDATE`; totals computed server-side in minor units (ADR-0005). Analytics snapshot written atomically inside the `complete` transaction with `UNIQUE(order_id)` + `ON CONFLICT DO NOTHING` for idempotency; purge job also snapshots as fallback if an order was auto-completed. Retention: `platform_settings.retention_min_days` (admin-configurable, default 30, `>= 1`), `order_auto_complete_grace_hours` (default 72). `DELETE /orders/{id}` rejected pre-retention with `409 ORDER_RETENTION_NOT_MET` — no admin override per spec. `POST /admin/jobs/purge-orders` hard-deletes eligible terminal orders while preserving snapshots; opt-in APScheduler via `APP_ENABLE_SCHEDULER=1`. ADR-0011 formalizes the `sellers.id == users.id` shared-PK invariant (runtime-enforced, no cyclic FK). ADR-0012 records 7 state-machine / retention / snapshot decisions. Alembic migration `0002_phase5_orders` adds grace-hours column + snapshot unique constraint; downgrade tested clean. Orchestrator independently verified: place order (201, total 3000); full self-deliver lifecycle all 200 with customer-complete; second OFD on completed order → 409; full driver-assigned lifecycle with OFD idempotency 409; DELETE pre-retention → 409; PATCH retention to 1 day → 200 (0 rejected 422); DELETE post-retention → 204; purge removes remaining eligible orders (`purged_count: 1`); SQL confirms `orders=0, snapshots=2` and dashboard shows `lifetime_sales_amount=4500, lifetime_orders_count=2` unchanged after all deletions. **38 new tests (lifecycle, cancel, retention, purge, visibility, stock, admin retention) → 141/141 green.** **Ready for Phase 6.**
- **Phase 4** — Backend Engineer (2026-04-18): delivered 11 endpoints across `/sellers`, `/stores`, `/products` with seller-owned store creation (one-per-seller, city-required), product CRUD with image metadata and soft-delete, referral-scoped customer visibility (ADR-0007 depth=1: unreferred → 404 + empty list, no existence leak), and seller dashboard reading from `order_analytics_snapshots` (zero-FK table from Phase 2) so lifetime sales and order counts survive both product soft-delete AND order hard-delete. ADR-0010 records the two key decisions: `sellers.city` as single source of truth and snapshots-over-materialized-view for dashboard reads. Orchestrator independently verified stop conditions: duplicate store → 409 `STORE_ALREADY_EXISTS`; referred customer sees seller’s product (200) and list includes it; unreferred customer → 404 `PRODUCT_NOT_FOUND` + empty list; driver → 404 / empty; direct-SQL snapshot insert (4200 minor units) appears in dashboard immediately with NO orders row present, proving FK-less persistence; product soft-delete leaves dashboard totals intact. Ownership enforced service-side; admins bypass. **42 new tests (stores, products, visibility, dashboard) → 103/103 green.** Follow-up flagged for Phase 5: document or refactor implicit `Seller.id == User.id` invariant. **Ready for Phase 5.**
- **Phase 3** — Backend Engineer + Security Engineer (2026-04-18): delivered FastAPI app with JWT auth (HS256, 15-min access tokens) + server-side hashed refresh tokens (7-day TTL, rotation, reuse detection per ADR-0006), Argon2id password hashing, RBAC middleware (`require_roles`), 12 endpoints (auth + invites), slowapi rate limiting. Admin invites (single-use, role-targeted) and seller referrals (multi-use, idempotent per ADR-0002). Orchestrator review caught a `get_or_create_seller_referral` bug returning `token=null` on existing-invite path — fixed with 2 regression tests. Security Engineer audit produced 6 fixes (1 critical: hardcoded seed token → `secrets.token_urlsafe(32)`; 2 high: `.with_for_update()` on refresh tokens for TOCTOU, prod guard on default JWT secret; 3 medium: password min length 12 per OWASP, uniform `InvalidCredentials` response to prevent email enumeration, `disabled_at` check in `get_current_user` + refresh) plus 18 regression tests. **61/61 tests green.** Live stop-condition sweep passed: signup without invite → 422; bogus invite → 400 `INVITE_INVALID`; role=seller persisted via admin_invite; `referring_seller_id` set correctly via seller_referral; driver via seller_referral → 400 `INVITE_ROLE_MISMATCH`; OpenAPI/Swagger served; refresh rotation + reuse detection (`AUTH_TOKEN_REUSED`). Findings + Phase 12 follow-ups documented in `docs/phase-3-security-review.md`. Deferred to Phase 12: CORS lockdown, Redis-backed rate limiter, JWT `aud`/`iss` claims, timing side-channel on invite lookup. **Ready for Phase 4.**
