# Architecture

Deeper companion to the top-level `README.md`.  This document focuses on
data flow, trust boundaries, and scaling levers.

## 1. Component view

```
                    +------------------+
                    |  Flutter client  |
                    |  (iOS + Android) |
                    +---------+--------+
                              |
                  HTTPS/1.1 + HTTPS WS
                              |
+-----------------------------v-----------------------------+
|                     AWS ALB (public, 443)                 |
|   - HTTPS listener with ACM cert                          |
|   - Health check → /healthz/ready                         |
|   - Forwards to target group (port 8000)                  |
+---------------------------+-------------------------------+
                            |
                +-----------v-----------+
                |  VPC private subnets  |
                |  (2 AZs, 1 NAT)       |
                +-----------+-----------+
                            |
            +---------------+---------------+
            |                               |
+-----------v------------+      +-----------v------------+
|  ECS Fargate task #1   |      |  ECS Fargate task #N   |
|  gunicorn+uvicorn     ...     |  (autoscale 2-10,     |
|  FastAPI app           |      |   target CPU 70%)     |
|                        |      |                        |
|  /api/v1/*             |      |                        |
|  /ws (persistent)      |      |                        |
|  /metrics (token)      |      |                        |
|  /healthz, /healthz/ready     |                        |
+--+--+--+--+------------+      +-------------------------+
   |  |  |  |
   |  |  |  +---------------------------+
   |  |  |                              |
   |  |  +---+                          |
   |  |      |                          |
   |  v      v                          v
   |  S3 uploads (via pre-signed URLs, direct from client)
   |  CloudWatch logs (awslogs driver)
   |  Sentry SDK → sentry.io
   |
   +----TLS----->  Supabase Postgres (pooler endpoint)
   +----HTTPS--->  FCM (Android push)
   +----HTTPS--->  APNs (iOS push)
```

## 2. Trust boundaries

| Boundary                 | What crosses                           | Mitigation                            |
|--------------------------|----------------------------------------|---------------------------------------|
| Internet → ALB           | TLS-wrapped HTTP + WS                  | ACM cert, TLS 1.2+ only               |
| ALB → ECS task           | HTTP (VPC private)                     | SG rule: ECS accepts only from ALB SG |
| ECS task → Supabase      | TLS Postgres over public internet      | Pooler hostname + verified TLS        |
| ECS task → S3            | AWS SigV4 via task IAM role            | No long-lived AWS keys in env         |
| ECS task → FCM/APNs      | HTTPS + API key / p8 key               | Keys sourced from Secrets Manager     |
| Browser/app → S3         | HTTPS + pre-signed PUT URL (5 min TTL) | Short TTL; bucket is private          |

## 3. Data flow — placing an order

```
Buyer                   Flutter              ALB           ECS        Postgres
 |  tap "Checkout" -> | POST /orders        ->|  forward -> | BEGIN TX  |
 |                    |                       |             |  INSERT orders
 |                    |                       |             |  UPDATE stock
 |                    |                       |             |  INSERT order_items
 |                    |                       |             | COMMIT    |
 |                    |                       |             |<- 201     |
 |                    |<- 201 + order json    |<- 201       |           |
 |                    |                       |             |
 |                    |                       |   + WS event "order_placed" -> seller subs
 |                    |                       |   + Prometheus orders_placed_total++
 |                    |                       |   + push notification to seller device tokens
```

## 4. Data flow — E2E encrypted message

```
Sender                  Flutter                 ECS        Postgres
 |  compose "hi"     | ciphertext(X25519+AES-GCM) ->|       |
 |                   | POST /conversations/{id}/messages     |
 |                   |                              |  INSERT ciphertext only (ADR 0013)
 |                   |                              |<- 201  |
 |                   |  + WS event broadcast to recipient subs
Recipient Flutter:   |
 |  receive ciphertext -> decrypt locally -> render plaintext
```

The server never sees plaintext message bodies — only ciphertext +
metadata (timestamps, sender, conversation).

## 5. Scaling levers

- **Horizontal:** ECS service autoscale 2→10 by CPU (CloudWatch target
  tracking).  Headroom beyond 10 requires raising the ceiling in
  `variables.tf::service_max_count`.
- **DB:** Supabase pooler handles connection multiplexing; tuning is
  instance-size + read-replicas in Supabase dashboard.
- **WebSockets:** persistent connections don't distribute via ALB
  round-robin as cleanly as stateless requests.  The `ws_connections_active`
  gauge is the metric to watch; if any single task holds >3× the
  average, a restart will rebalance.
- **Uploads:** direct-to-S3 via pre-signed URLs means the task is not
  a bandwidth bottleneck.  Scale is effectively unbounded.

## 6. Failure modes

| Failure                       | Detection                        | Recovery                            |
|-------------------------------|----------------------------------|-------------------------------------|
| Task crash-loops              | ECS service events + 5xx alarm   | Rollback image per `ROLLBACK.md`    |
| DB unreachable                | /healthz/ready returns 503       | ALB withdraws task; Supabase status |
| S3 unreachable                | Upload 5xx, app log "boto_timeout" | Usually transient; retry + page if >5 min |
| APNs / FCM 403                | Push fanout log warn             | Rotate per `SECRET-ROTATION.md`     |
| Stale migration at task start | `alembic` one-shot fails in CI   | Deploy blocked before service swap  |

## 7. What is intentionally *not* here

- No Redis / queue.  Rate limiting is in-process (slowapi), background
  purge is an in-process scheduler.  When we need multi-instance
  coordination, add Redis or DynamoDB — not before.
- No service mesh.  Single service, single AZ pair — a mesh is
  overkill.
- No dedicated feature-flag service.  The kill-switch pattern is
  env-var-empty-means-off (see `ROLLBACK.md` section 3).
