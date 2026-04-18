# Invite-Only Marketplace

An invite-gated, mobile-first marketplace.  FastAPI + Postgres (Supabase)
backend, Flutter client, AWS ECS Fargate deploy with GCP Cloud Run as an
alternate target.

See `PROJECT.md` for phase-by-phase history and `docs/adr/` for the
locked architectural decisions (ADRs 0001–0015).

## Architecture at a glance

```
                                +-----------------+
                                |  Flutter app    |
                                |  (iOS/Android)  |
                                +--------+--------+
                                         |
                            HTTPS + WebSocket (wss://)
                                         |
                                +--------v---------+
                                |  AWS ALB (443)   |
                                |  TLS termination |
                                +--------+---------+
                                         |
                                         | (private subnet)
                                +--------v----------+
                                |  ECS Fargate svc  |
                                |  marketplace-bkd  |   <-- /metrics scraped
                                |  2-10 tasks       |       by Prometheus
                                +---+---+---+--+----+
                                    |   |   |  |
         +--------------------------+   |   |  +-----------------+
         |                              |   |                    |
  +------v------+             +---------v+  +---v---------+  +---v--------+
  |  Supabase   |             |    S3     |  |   FCM/     |  |  Sentry    |
  |  Postgres   |             |  uploads  |  |   APNs     |  |  + logs    |
  | (TLS pooler)|             | (versioned|  | (push)     |  +------------+
  +-------------+             +-----------+  +------------+
```

- **Auth:** JWT (HS256), primary + secondary rotation keys.
- **Data:** Supabase Postgres over TLS pooler; backend is async (asyncpg).
- **Uploads:** pre-signed S3 URLs, 10 MiB cap, CDN-served.
- **Messaging:** WebSocket fanout, E2E X25519+AES-GCM (ciphertext-only
  server path — see ADR 0013).
- **Push:** FCM (Android) + APNs (iOS), device tokens registered via
  `/api/v1/devices`.
- **Observability:** Sentry + Prometheus `/metrics` + CloudWatch logs.

Deeper diagram: `docs/ARCHITECTURE.md`.

## Quickstart — backend dev

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" email-validator

# Bring up Postgres (Docker) or point APP_DATABASE_URL_SYNC at Supabase.
export APP_ENVIRONMENT=dev
alembic upgrade head

uvicorn app.main:app --reload
# → http://localhost:8000/docs
pytest                          # full test suite (≥227 tests)
```

Preflight check before deploying (fails on missing prod secrets):

```bash
APP_ENVIRONMENT=prod python -m app.scripts.check_env
```

## Quickstart — frontend dev

```bash
cd frontend
flutter pub get
flutter run                     # dev device
flutter analyze                 # lints
flutter test                    # unit + widget tests (≥57)
```

See `frontend/SMOKE-TESTING.md` for manual QA recipes.

## Deployment

Primary target: **AWS ECS Fargate** (locked in ADR D1, Phase 13).

```bash
cd infra/terraform/aws
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform validate && terraform plan
terraform apply
```

Alternate: **GCP Cloud Run** — see `infra/gcp/README.md`.

CI/CD:

- `.github/workflows/test.yml` — PR + main: backend pytest, flutter
  analyze + test, terraform validate.
- `.github/workflows/deploy-main.yml` — push to main: build → push to
  ECR → run migrations → update ECS service.
- `.github/workflows/security.yml` — nightly gitleaks + pip-audit +
  flutter outdated.
- `.github/workflows/mobile-release.yml` — manual dispatch only: AAB
  to Play Internal, IPA to TestFlight.

## Environment variables (prefix `APP_`)

| Var                            | Purpose                                          | Prod required? |
|--------------------------------|--------------------------------------------------|----------------|
| `APP_ENVIRONMENT`              | `dev` / `test` / `prod`                          | yes            |
| `APP_DATABASE_URL`             | async Postgres URL                               | yes            |
| `APP_DATABASE_URL_SYNC`        | sync URL for alembic                             | yes            |
| `APP_JWT_SECRET_PRIMARY`       | HS256 signing key                                | yes            |
| `APP_JWT_SECRET_SECONDARY`     | rotation verifier (empty outside rotation window)| no             |
| `APP_JWT_ALGORITHM`            | default HS256                                    | no             |
| `APP_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | default 15                                | no             |
| `APP_JWT_REFRESH_TOKEN_EXPIRE_DAYS`   | default 7                                 | no             |
| `APP_CORS_ORIGINS`             | comma-separated allowed origins                  | yes            |
| `APP_S3_BUCKET`                | uploads bucket name                              | yes            |
| `APP_S3_REGION`                | e.g. `us-east-1`                                 | yes            |
| `APP_S3_CDN_BASE_URL`          | CDN prefix, no trailing slash                    | yes if uploads |
| `APP_S3_UPLOAD_MAX_BYTES`      | default 10 MiB                                   | no             |
| `APP_S3_PRESIGN_EXPIRES_SECONDS` | default 300                                    | no             |
| `APP_AWS_ACCESS_KEY_ID`        | set only when NOT using task IAM                 | no             |
| `APP_AWS_SECRET_ACCESS_KEY`    | set only when NOT using task IAM                 | no             |
| `APP_FCM_SERVER_KEY`           | Android push                                     | required for push |
| `APP_APNS_KEY_PEM`             | .p8 contents for iOS push                        | required for push |
| `APP_APNS_KEY_ID`              | iOS push key ID                                  | required for push |
| `APP_APNS_TEAM_ID`             | Apple team ID                                    | required for push |
| `APP_APNS_BUNDLE_ID`           | iOS bundle ID                                    | required for push |
| `APP_SENTRY_DSN`               | error reporting (empty → Sentry off)             | recommended    |
| `APP_SENTRY_RELEASE`           | release id, typically git SHA                    | no             |
| `APP_METRICS_TOKEN`            | shared secret for `/metrics`                     | recommended    |

## Runbooks

All production operations are documented in `docs/runbooks/`:

- `DEPLOYMENT.md`         — normal deploy, hotfix, validation
- `INCIDENT-RESPONSE.md`  — severity ladder, IC role, comms templates
- `DB-RESTORE.md`         — Supabase PITR + manual pg_restore fallback
- `SECRET-ROTATION.md`    — JWT primary↔secondary rotation
- `ROLLBACK.md`           — image, migration, feature-flag rollbacks
- `OBSERVABILITY.md`      — where logs, metrics, alerts live

## Architecture decisions

Locked in `docs/adr/`:

- 0001 — Record architecture decisions
- 0002 — Referral token cardinality (multi-use)
- 0003 — Out-for-delivery trigger actors
- 0004 — Server-side cart persistence
- 0005 — Single platform currency
- 0006 — Server-side refresh tokens
- 0007 — Referral chain depth one
- 0008 — Conversations two-participants
- 0009 — E2E crypto scheme (X25519 + AES-GCM)
- 0010 — Phase 4 store city + dashboard source
- 0011 — seller_id == user_id invariant
- 0012 — Order state machine + retention
- 0013 — Phase 6 messaging crypto + conversation policy
- 0014 — Delivery tracking asymmetric visibility
- 0015 — Frontend API client

## Repo layout

```
backend/                FastAPI app + alembic migrations + tests
frontend/               Flutter client
frontend-spec/          UX/spec docs
infra/terraform/aws/    ECS Fargate stack (primary)
infra/gcp/              Cloud Run alternate
docs/
  adr/                  Architecture decision records
  runbooks/             Operational runbooks
  api-contract.md       Frozen API contract
  architecture.md       Component narrative
  ARCHITECTURE.md       Deeper component + data-flow diagram
.github/workflows/      CI/CD pipelines
PROJECT.md              Phase-by-phase log
```
