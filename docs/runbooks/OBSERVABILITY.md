# Runbook — Observability

## Three-pillar layout

| Pillar   | Primary tool                            | Secondary                          |
|----------|------------------------------------------|------------------------------------|
| Logs     | CloudWatch Logs `/ecs/marketplace-backend` | Sentry breadcrumbs               |
| Metrics  | CloudWatch (container insights) + Prom  | Prometheus `/metrics` (scraped)    |
| Traces   | Sentry performance (10% sample)         | —                                  |

## Logs

- Structured JSON via stdlib: one object per line, fields `time`,
  `level`, `name`, `message`.
- `X-Request-ID` is propagated into the response header; the request
  ID also appears in Sentry breadcrumbs, so you can pivot a user report
  → CloudWatch log line → Sentry issue.
- Search example:
  ```
  aws logs filter-log-events \
    --log-group-name /ecs/marketplace-backend \
    --filter-pattern "\"x-request-id\": \"abcd-1234\""
  ```

## Metrics

- Container-level CPU/mem/network surfaced via ECS Container Insights
  in CloudWatch → Container Insights dashboard.
- App metrics scraped from `/metrics` with `X-Metrics-Token: <token>`.
  Scrape target is the ALB internal DNS, port 443, health-checked.
- Custom metrics (app-level):
  - `ws_connections_active` (Gauge) — open WebSocket connections
  - `messages_sent_total{kind}` (Counter) — outbound messages
  - `orders_placed_total{currency}` (Counter) — placed orders
- FastAPI RED metrics (requests, errors, duration) auto-produced by
  `prometheus-fastapi-instrumentator`: `http_requests_total`,
  `http_request_duration_seconds_*`, etc.

## Alerts

Defined in Terraform, dispatched via SNS topic `ops_alert_sns_arn`:

| Alarm                 | Condition                             | Action            |
|-----------------------|---------------------------------------|-------------------|
| `alb-5xx`             | 5xx count > 5 in 1 min for 5 min      | Page on-call      |
| `ecs-cpu`             | service CPU > 80% for 10 min          | Autoscale fires; page if sustained |
| `ecs-memory`          | service memory > 80% for 10 min       | Page on-call      |

The SNS topic typically fans out to PagerDuty + Slack webhook.  Both
subscriptions are created out-of-band (not Terraform-managed so rotating
the Slack webhook doesn't require a plan).

## Sentry

- One project per environment (`marketplace-prod`, `-staging`).
- DSN injected via `APP_SENTRY_DSN` (backend) and
  `--dart-define=SENTRY_DSN=...` (Flutter).
- Traces sample rate 10% to stay under free-tier volume.
- PII is **off**: `send_default_pii=False`.

## Dashboard layout (suggested)

CloudWatch dashboard JSON lives alongside Terraform (TODO —
not yet automated).  Key widgets:
1. ALB p50/p95/p99 latency + 5xx count (top row)
2. ECS running task count + CPU/mem (middle)
3. DB pool saturation from app logs (bottom)
4. Top 10 slow endpoints from Prometheus histograms (sidebar)

## Reading a production issue — tl;dr

1. PagerDuty alert fires → Slack `#incidents`.
2. Open CloudWatch alarm → click through to log group → filter by
   request-id or time window.
3. Cross-reference Sentry issues for the same window.
4. Decide: image rollback (most common) or forward fix (see
   `DEPLOYMENT.md`, `ROLLBACK.md`).
