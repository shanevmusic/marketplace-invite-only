# Runbook — JWT secret rotation

Phase 12 introduced `APP_JWT_SECRET_PRIMARY` (signing) +
`APP_JWT_SECRET_SECONDARY` (verifier-only).  Rotation is zero-downtime.

## Prerequisites

- AWS CLI authenticated against the target account.
- `openssl` (or another cryptographic RNG).
- The access-token TTL is 15 min (see `APP_JWT_ACCESS_TOKEN_EXPIRE_MINUTES`);
  budget **at least 2× that** before finalising a rotation.

## Steps

```bash
# 1. Generate the new signing key.
NEW=$(openssl rand -base64 48)

# 2. Stash the current primary → secondary.
CUR=$(aws secretsmanager get-secret-value \
        --secret-id marketplace-prod/jwt_secret_primary \
        --query SecretString --output text)

aws secretsmanager put-secret-value \
  --secret-id marketplace-prod/jwt_secret_secondary \
  --secret-string "$CUR"

# 3. Publish the new primary.
aws secretsmanager put-secret-value \
  --secret-id marketplace-prod/jwt_secret_primary \
  --secret-string "$NEW"

# 4. Force task restart so ECS re-pulls both secrets.
aws ecs update-service \
  --cluster marketplace \
  --service marketplace-backend \
  --force-new-deployment

# 5. Wait out 2× the access-token TTL (default 15 min → wait 30+ min).
#    Refresh tokens (7d) continue signing/verifying with secondary.

# 6. Clear the old secondary.
aws secretsmanager put-secret-value \
  --secret-id marketplace-prod/jwt_secret_secondary \
  --secret-string ""

# 7. Force one more restart so the now-empty secondary is loaded and
#    verification is single-key again.
aws ecs update-service \
  --cluster marketplace \
  --service marketplace-backend \
  --force-new-deployment
```

## What the code does during rotation

- `app.core.config.settings.jwt_signing_key` returns `_primary` (new).
- `app.core.config.settings.jwt_verification_keys` returns
  `[primary, legacy, secondary]`, deduplicated.
- Any token minted before step 2 verifies against `secondary` (old
  primary).  Any token minted after step 3 verifies against `primary`
  (new).  Users stay logged in throughout.

## Emergency rotation (suspected leak)

Skip the staged rollout — set primary = new, secondary = empty, force
redeploy.  All existing access tokens are invalidated immediately.
Refresh tokens are **also** signed with the same key set and will
fail, forcing every user to re-authenticate.  Accept this as the cost
of containing the breach.

## Related: other secrets

- `fcm_server_key`, `apns_key_pem`: rotate in FCM/APNs consoles first,
  then update Secrets Manager; push only supports one key at a time so
  there is a brief window where old devices may fail to register.
- `db_password`: must rotate through Supabase dashboard; update
  `APP_DATABASE_URL` secret values accordingly.
