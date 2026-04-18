# GCP Cloud Run — alternate deployment target

This directory contains a Knative service spec and Cloud Build pipeline
for running the backend on Cloud Run.  Kept in sync with the AWS stack at
the image-boundary level: the same container image runs on either
platform, differing only in secret injection and logging plumbing.

## Why an alternate?

- DR: if ECS/ALB has a regional outage, repoint DNS to Cloud Run.
- Cost exploration: Cloud Run's scale-to-zero may be cheaper for staging.
- Vendor negotiation leverage.

We do **not** dual-run in production steady state.

## Supabase is still the database

Supabase is DB-as-a-service regardless of compute platform.  The backend
connects over the public internet via TLS to the Supabase pooler.  No
Cloud SQL, no VPC peering required (Cloud Run + Supabase pooler is
perfectly acceptable for our scale).

## Quickstart

```bash
# One-time — create secrets per infra/gcp/secrets.md, then:
gcloud run deploy marketplace-backend \
  --source backend \
  --region us-central1 \
  --no-allow-unauthenticated \
  --min-instances 2 --max-instances 10 \
  --memory 2Gi --cpu 1
```

Or via `cloudbuild.yaml` trigger on push to `main`:

```bash
gcloud builds submit --config infra/gcp/cloudbuild.yaml \
  --substitutions=SHORT_SHA=$(git rev-parse --short HEAD)
```

To apply the Knative spec directly (instead of `gcloud run deploy`):

```bash
# Replace PROJECT_ID, REGION, TAG in service.yaml first.
gcloud run services replace infra/gcp/service.yaml --region=us-central1
```

## Files

- `service.yaml`    — Knative Service spec
- `cloudbuild.yaml` — build + push + deploy pipeline
- `secrets.md`      — Secret Manager keys and creation recipe
