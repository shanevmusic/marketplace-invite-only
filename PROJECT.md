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
| DB | PostgreSQL 16+ | Managed in prod (RDS / Cloud SQL). Dev sandbox uses 17; both accepted. |
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
- [ ] **Phase 7** — Backend E: delivery tracking (asymmetric visibility)
- [ ] **Phase 8** — Frontend A: Flutter scaffold + auth
- [ ] **Phase 9** — Frontend B: seller & customer core flows
- [ ] **Phase 10** — Frontend C: messaging & tracking UI
- [ ] **Phase 11** — Admin panel
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

- **Phase 0** — Orchestrator (2026-04-17): stack + product logic frozen, agent roster defined, conventions established, monorepo scaffolded, PROJECT.md created. **Ready for Phase 1.**
- **Phase 1** — System Architect + Product Manager (2026-04-18): delivered `architecture.md`, `api-contract.md`, `er-diagram.md`, `prd.md` (28 P0 features). Orchestrator reconciliation in `phase-1-reconciliation.md` resolved all 15 architect/contract/ER open questions + 4 PM open questions. ADRs 0002–0009 recorded. **D2 closed.** **Ready for Phase 2.**
- **Phase 2** — Database Engineer (2026-04-18): delivered SQLAlchemy 2.x models (20 tables, 5 app enums + citext, 1 materialized view), Alembic migration `0001_initial_schema`, idempotent seed script, `docs/schema.md`. Stop condition verified independently: clean `alembic upgrade head`, `seed_dev` produces 4 users + 1 store + 3 products, full downgrade/re-upgrade cycle works, CHECK constraints bite (rating range, conversation canonical ordering, deliveries actor presence, platform singleton), materialized view refreshes. Critical invariants confirmed: `messages` has no plaintext columns (ADR-0009), `order_analytics_snapshots` has zero FKs (survives purges). **Ready for Phase 3.**
- **Phase 6** — Backend + Security Engineer (2026-04-18): delivered E2E-encrypted messaging per ADR-0009 (X25519 + HKDF-SHA256 + AES-256-GCM, per-message ephemeral ECDH). Server handles ciphertext only — never calls any crypto primitive on message content. Endpoints: `POST/GET /keys`, `GET /keys/me`, `GET /keys/{user_id}` (eligibility-gated), `DELETE /keys/{key_id}`; `POST/GET /conversations`, `GET /conversations/{id}`, `GET /conversations/{id}/messages` (cursor-paginated), `POST /conversations/{id}/messages`, `POST /conversations/{id}/messages/{id}/read`; `GET/PATCH /admin/settings/message-retention`, `POST /admin/jobs/purge-messages`. WebSocket at `/ws?token=` with close codes **4401** (no/invalid token) and **4403** (subscribe to non-participant conversation), 30s heartbeat, events `message.new`/`message.read`/`typing`. Conversation eligibility (ADR-0013): customer↔seller where customer was referred by seller (admin bypass). Multi-key rotation with partial unique index `WHERE status='active'` — concurrency-safe via `FOR UPDATE`. Alembic `0003_phase6_messaging` drops legacy 1:1 constraint on `user_public_keys`, adds key_version/status/rotated_at/revoked_at, adds `messages.recipient_key_id`, adds `platform_settings.message_retention_days` (default 90, CHECK `>= 7`). ADR-0013 documents crypto choice, conversation policy, retention minimum, WS close codes, and replay defense (client-side concern). Security Engineer review (`docs/phase-6-security-review.md`) verified the **ciphertext-only invariant** three independent ways: (1) runtime DB scan asserts plaintext substrings never appear across all tables, (2) static audit greps `messaging_service.py` for AESGCM/X25519/HKDF/decrypt — zero hits, (3) schema audit rejects `body/text/plaintext/content` field names via `extra='forbid'`. Orchestrator independently ran a two-client live probe: Alice (customer) and Bob (seller) generated X25519 keypairs locally, registered pubkeys, exchanged encrypted messages via REST and WS, and the orchestrator scanned **20 DB tables** confirming plaintext is absent — only 55-byte ciphertext + 12-byte nonce stored opaquely; stranger (driver) → 404 (no existence leak); injecting a `body` field → 422; WS no-token → close 4401; WS `message.new` broadcast works end-to-end with client-side decryption. **36 new tests (keys, conversations, messages, ciphertext-only, WS, admin retention) → 177/177 green.** Phase 12 follow-ups in security review: Redis pub/sub for WS fan-out, key pinning UX, message size cap, admin audit trail. **Ready for Phase 7.**
- **Phase 5** — Backend Engineer (2026-04-18): delivered full order + fulfillment flow. 17 new endpoints under `/orders`, `/admin/orders`, `/admin/settings`, `/admin/jobs`. State machine `pending → accepted → preparing → out_for_delivery → delivered → completed` with terminal `cancelled`; transitions gated by role (seller/driver/customer/admin). Per ADR-0003, `out_for_delivery` is idempotent and emits `409 DELIVERY_ALREADY_STARTED` on double-call; supports both self-deliver (seller triggers) and driver-assigned (seller requests → admin assigns → driver fulfills) flows. Stock reserved via row-level `SELECT ... FOR UPDATE`; totals computed server-side in minor units (ADR-0005). Analytics snapshot written atomically inside the `complete` transaction with `UNIQUE(order_id)` + `ON CONFLICT DO NOTHING` for idempotency; purge job also snapshots as fallback if an order was auto-completed. Retention: `platform_settings.retention_min_days` (admin-configurable, default 30, `>= 1`), `order_auto_complete_grace_hours` (default 72). `DELETE /orders/{id}` rejected pre-retention with `409 ORDER_RETENTION_NOT_MET` — no admin override per spec. `POST /admin/jobs/purge-orders` hard-deletes eligible terminal orders while preserving snapshots; opt-in APScheduler via `APP_ENABLE_SCHEDULER=1`. ADR-0011 formalizes the `sellers.id == users.id` shared-PK invariant (runtime-enforced, no cyclic FK). ADR-0012 records 7 state-machine / retention / snapshot decisions. Alembic migration `0002_phase5_orders` adds grace-hours column + snapshot unique constraint; downgrade tested clean. Orchestrator independently verified: place order (201, total 3000); full self-deliver lifecycle all 200 with customer-complete; second OFD on completed order → 409; full driver-assigned lifecycle with OFD idempotency 409; DELETE pre-retention → 409; PATCH retention to 1 day → 200 (0 rejected 422); DELETE post-retention → 204; purge removes remaining eligible orders (`purged_count: 1`); SQL confirms `orders=0, snapshots=2` and dashboard shows `lifetime_sales_amount=4500, lifetime_orders_count=2` unchanged after all deletions. **38 new tests (lifecycle, cancel, retention, purge, visibility, stock, admin retention) → 141/141 green.** **Ready for Phase 6.**
- **Phase 4** — Backend Engineer (2026-04-18): delivered 11 endpoints across `/sellers`, `/stores`, `/products` with seller-owned store creation (one-per-seller, city-required), product CRUD with image metadata and soft-delete, referral-scoped customer visibility (ADR-0007 depth=1: unreferred → 404 + empty list, no existence leak), and seller dashboard reading from `order_analytics_snapshots` (zero-FK table from Phase 2) so lifetime sales and order counts survive both product soft-delete AND order hard-delete. ADR-0010 records the two key decisions: `sellers.city` as single source of truth and snapshots-over-materialized-view for dashboard reads. Orchestrator independently verified stop conditions: duplicate store → 409 `STORE_ALREADY_EXISTS`; referred customer sees seller’s product (200) and list includes it; unreferred customer → 404 `PRODUCT_NOT_FOUND` + empty list; driver → 404 / empty; direct-SQL snapshot insert (4200 minor units) appears in dashboard immediately with NO orders row present, proving FK-less persistence; product soft-delete leaves dashboard totals intact. Ownership enforced service-side; admins bypass. **42 new tests (stores, products, visibility, dashboard) → 103/103 green.** Follow-up flagged for Phase 5: document or refactor implicit `Seller.id == User.id` invariant. **Ready for Phase 5.**
- **Phase 3** — Backend Engineer + Security Engineer (2026-04-18): delivered FastAPI app with JWT auth (HS256, 15-min access tokens) + server-side hashed refresh tokens (7-day TTL, rotation, reuse detection per ADR-0006), Argon2id password hashing, RBAC middleware (`require_roles`), 12 endpoints (auth + invites), slowapi rate limiting. Admin invites (single-use, role-targeted) and seller referrals (multi-use, idempotent per ADR-0002). Orchestrator review caught a `get_or_create_seller_referral` bug returning `token=null` on existing-invite path — fixed with 2 regression tests. Security Engineer audit produced 6 fixes (1 critical: hardcoded seed token → `secrets.token_urlsafe(32)`; 2 high: `.with_for_update()` on refresh tokens for TOCTOU, prod guard on default JWT secret; 3 medium: password min length 12 per OWASP, uniform `InvalidCredentials` response to prevent email enumeration, `disabled_at` check in `get_current_user` + refresh) plus 18 regression tests. **61/61 tests green.** Live stop-condition sweep passed: signup without invite → 422; bogus invite → 400 `INVITE_INVALID`; role=seller persisted via admin_invite; `referring_seller_id` set correctly via seller_referral; driver via seller_referral → 400 `INVITE_ROLE_MISMATCH`; OpenAPI/Swagger served; refresh rotation + reuse detection (`AUTH_TOKEN_REUSED`). Findings + Phase 12 follow-ups documented in `docs/phase-3-security-review.md`. Deferred to Phase 12: CORS lockdown, Redis-backed rate limiter, JWT `aud`/`iss` claims, timing side-channel on invite lookup. **Ready for Phase 4.**
