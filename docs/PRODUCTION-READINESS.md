# Production Readiness Checklist

Signed off at Phase 14 (2026-04-18). Each row names a dimension, its
status, the authoritative source, and a short note. ✅ = ready for v1
launch, ⚠️ = scaffolded / partial with explicit follow-up tracked,
❌ = missing (none at this time).

## Status

| # | Area | Status | Source | Note |
|---|------|--------|--------|------|
| 1 | Authentication (JWT access + refresh) | ✅ | `backend/app/core/security.py`, ADR 0006 | HS256, primary+secondary secrets for zero-downtime rotation; refresh tokens server-side with revocation list. |
| 2 | Authorization (RBAC) | ✅ | `backend/app/api/v1/deps.py`, ADR 0011 | Four roles (admin/seller/customer/driver); role dependency decorators on every router; E2E tests cover cross-role denials. |
| 3 | Suspension enforcement at login | ✅ | `docs/CONTRACT-DEVIATIONS.md` C-G1 | `/auth/login` returns 403 `AUTH_ACCOUNT_SUSPENDED` before tokens are minted. |
| 4 | E2E message encryption | ✅ | ADR 0009, ADR 0013 | X25519 ECDH → AES-256-GCM; server stores ciphertext only; tests enforce ciphertext-only invariant. |
| 5 | Delivery-tracking visibility | ✅ | ADR 0014 | Customer sees status + ETA only; seller/driver see customer coords. Tests cover every role × endpoint pair. |
| 6 | Rate limiting | ✅ | `app/core/rate_limiter.py` (slowapi) | 5/min login, 3/min signup, 30/min refresh, 20/min uploads, 10/min WS; live-verified 429s in Phase 12. |
| 7 | Security headers | ✅ | `app/main.py::SecurityHeadersMiddleware` | HSTS (2 y), CSP `default-src 'none'; frame-ancestors 'none'`, X-Content-Type-Options, Referrer-Policy, Permissions-Policy. |
| 8 | Health checks | ✅ | `app/main.py` | `/healthz` plain 200 + `/healthz/ready` pings DB; ALB target group points at `/healthz/ready`. |
| 9 | Metrics endpoint | ✅ | `app/core/observability.py` + `tests/test_metrics_endpoint.py` | Prometheus `/metrics` gated by `X-Metrics-Token`; 4-case unit test for 404/404/404/200 matrix. |
| 10 | Error reporting (Sentry) | ✅ | `app/core/observability.py::init_sentry` | Enabled when `APP_SENTRY_DSN` set; 10 % trace sample, PII off. |
| 11 | CloudWatch alarms | ✅ | `infra/terraform/aws/main.tf` | ALB 5xx (>5/min 5×), ECS CPU (>80 % 10 min), ECS memory (>80 % 10 min); all route to SNS. |
| 12 | CloudWatch dashboard | ✅ | `infra/terraform/aws/dashboard.tf` | `${prefix}-ops` dashboard with 6 widgets (ALB requests/5xx/p95, ECS tasks/CPU/memory). |
| 13 | Log aggregation | ✅ | `infra/terraform/aws/main.tf::aws_cloudwatch_log_group.backend` | 30-day retention; stdout JSON from gunicorn streams here. |
| 14 | Database backups + PITR | ✅ | `docs/runbooks/DB-RESTORE.md` | Supabase PITR is default; `pg_dump` fallback documented with exact commands. |
| 15 | Restore drill | ⚠️ | `docs/runbooks/DB-RESTORE.md` | Procedure is documented and commands verified syntactically; an end-to-end drill against a staging restore should be run before first customer signup. |
| 16 | CI / tests | ✅ | `.github/workflows/test.yml` | Backend pytest (231), Flutter analyze + test (57/2 skipped), terraform fmt + validate — all required on PR. |
| 17 | CI / security | ✅ | `.github/workflows/security.yml` | Nightly gitleaks + pip-audit + flutter pub outdated. |
| 18 | CD / backend | ✅ | `.github/workflows/deploy-main.yml` | push-to-main triggers OIDC-assumed ECR push → alembic-migrate one-shot → ECS wait-for-stability. |
| 19 | CD / mobile | ⚠️ | `.github/workflows/mobile-release.yml` | AAB → Play Internal + IPA → TestFlight scaffolded; iOS job gated `if: false` until ASC keys land. |
| 20 | IaC — AWS primary | ✅ | `infra/terraform/aws/` | `terraform validate` green; VPC + ECS + ALB + ECR + S3 + Secrets Manager + IAM + alarms + dashboard. |
| 21 | IaC — GCP alternate | ✅ | `infra/gcp/` | Cloud Run service spec + cloudbuild + secrets mapping, ready to `gcloud run deploy`. |
| 22 | Secrets management | ✅ | `docs/runbooks/SECRET-ROTATION.md` | 9 Secrets Manager entries in Terraform; env→secret mapping documented; no hardcoded secrets (`gitleaks` nightly). |
| 23 | Secret rotation (JWT) | ✅ | `app/core/security.py` + rotation runbook | Primary/secondary keys with 2× access-token-TTL overlap; CLI to swap. |
| 24 | Mobile signing — Android | ✅ | `frontend/android/SIGNING.md` | Keystore env-var flow documented; falls back to debug signing when keystore absent (dev). |
| 25 | Mobile signing — iOS | ✅ | `frontend/ios/SIGNING.md` + `ExportOptions.plist` | Manual-signing flow documented; requires ASC keys to exercise. |
| 26 | README | ✅ | `README.md` | All links resolve (verified Phase 14); env var table 20 rows; quickstart for backend + frontend + deploy. |
| 27 | Architecture doc | ✅ | `docs/ARCHITECTURE.md` | Includes component view, data-flow sequences, scaling levers, failure modes, new `6a. Production Topology` hub table. |
| 28 | ADR index | ✅ | `docs/adr/README.md` | All 15 ADRs (0001–0015) listed with one-line summaries + contribution guide. |
| 29 | Runbook index | ✅ | `docs/runbooks/README.md` | All 6 runbooks listed with one-line summaries + severity ladder + command conventions. |
| 30 | API contract | ✅ | `docs/api-contract.md` + `docs/CONTRACT-DEVIATIONS.md` | Contract deviations authoritatively reconciled: resolved-in-Phase-12 vs. migrated-to-POST-V1-BACKLOG. |

## Known deferrals — tracked in [`POST-V1-BACKLOG.md`](./POST-V1-BACKLOG.md)

None of these block v1; each has a revisit trigger.

- **WS fan-out via Redis pub/sub** — required before we run >1 app
  instance (v1 is single-instance Fargate).
- **B-G2** — CDN invalidation on product delete (S3 lifecycle cleans
  orphans on 7-day window).
- **B-G3** — Server-side avatar cropping pipeline (client crops are
  acceptable for beta).
- **C-G5** — Client-side WS reconnect back-off (server-side flood
  protection already in place).
- **C-G6** — Per-conversation message retention override (global floor
  is sufficient for beta moderation load).
- **C-G7** — Push-on-message-send wiring (scaffolded; gated on real
  FCM/APNs credentials via mobile-release pipeline).
- **C-G8 / C-G9** — Read receipts + typing indicators (low signal in
  beta cohort).
- **Custom metrics → CloudWatch** — `ws_connections_active`,
  `orders_placed_total`, `messages_sent_total` currently Prometheus-only;
  dashboard shows infra-side metrics until OTEL sidecar lands.

## Sign-off

All 30 rows ✅ except two ⚠️ (rows 15 and 19). Both have explicit
follow-up conditions. **The system is ready for the invite-only beta
launch.**
