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
| DB | PostgreSQL 16 | Managed in prod (RDS / Cloud SQL) |
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
- [ ] **Phase 2** — Database schema + migrations
- [ ] **Phase 3** — Backend A: auth + invite system
- [ ] **Phase 4** — Backend B: sellers, stores, products
- [ ] **Phase 5** — Backend C: orders & fulfillment
- [ ] **Phase 6** — Backend D: E2E messaging + WebSockets
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
