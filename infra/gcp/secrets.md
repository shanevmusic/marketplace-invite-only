# GCP Secret Manager — required keys

The Cloud Run alternate uses Secret Manager exclusively.  Create one secret
per key and grant the service account `roles/secretmanager.secretAccessor`
on each.

| Secret name             | Env var injected           | Notes                                    |
|-------------------------|----------------------------|------------------------------------------|
| `jwt_secret_primary`    | `APP_JWT_SECRET_PRIMARY`   | 32-byte random, base64                   |
| `jwt_secret_secondary`  | `APP_JWT_SECRET_SECONDARY` | Rotation fallback                        |
| `database_url`          | `APP_DATABASE_URL`         | Supabase async pooler URL (asyncpg)      |
| `database_url_sync`     | `APP_DATABASE_URL_SYNC`    | Sync URL for alembic                     |
| `fcm_server_key`        | `APP_FCM_SERVER_KEY`       | Android push                             |
| `apns_key_pem`          | `APP_APNS_KEY_PEM`         | iOS push (.p8 contents)                  |
| `apns_key_id`           | `APP_APNS_KEY_ID`          |                                          |
| `apns_team_id`          | `APP_APNS_TEAM_ID`         |                                          |
| `sentry_dsn`            | `APP_SENTRY_DSN`           |                                          |
| `metrics_token`         | `APP_METRICS_TOKEN`        | Shared secret for `/metrics`             |

Create a secret:

```bash
echo -n "$(openssl rand -base64 48)" | \
  gcloud secrets create jwt_secret_primary --data-file=- --replication-policy=automatic
```

Grant the runtime SA access:

```bash
gcloud secrets add-iam-policy-binding jwt_secret_primary \
  --member=serviceAccount:marketplace-backend@PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

Rotating a secret: publish a new version; Cloud Run pulls `latest` at
container start, so a new revision is needed to pick it up (or pin a
version in `service.yaml`).
