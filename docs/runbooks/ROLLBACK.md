# Runbook — Rollback

Three independent rollback mechanisms.  Pick the least-invasive one
that addresses the symptoms.

## 1. Image rollback (fastest; no DB impact)

Use when: code bug, no schema change required.

```bash
PREV=marketplace-backend:<previous-sha>
aws ecs update-service \
  --cluster marketplace \
  --service marketplace-backend \
  --task-definition $PREV \
  --force-new-deployment
```

Recovery time: 3–5 min (rolling replace, 50% min healthy).

## 2. Migration rollback (dangerous; coordinate)

Use when: a migration broke the schema AND the previous image can't run
against the new schema.

Prefer a *forward-fix* migration over `alembic downgrade`.  Only downgrade
when:
- The offending migration is the latest head.
- The downgrade function is known correct (read the migration code).
- No data written post-migration depends on the new columns.

```bash
# Run as an ECS task, same execution role so secrets are injected.
aws ecs run-task \
  --cluster marketplace \
  --task-definition marketplace-backend \
  --launch-type FARGATE \
  --overrides '{"containerOverrides":[{"name":"backend","command":["alembic","downgrade","-1"]}]}' \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG],assignPublicIp=DISABLED}"
```

Then follow (1) to deploy the older image.

## 3. Feature-flag kill switch (soft rollback)

Use when: a bounded feature misbehaves and the rest of the deploy is
fine (e.g. push notifications flooding).

We do not have a dedicated feature-flag service yet.  The short-term
substitute is env-var based — set the relevant `APP_*` secret to an
empty value and redeploy, which disables the feature code path
defensively (push, S3 uploads, metrics endpoint all honour empty
credentials as "disabled").

Example — disable push fanout:

```bash
aws secretsmanager put-secret-value \
  --secret-id marketplace-prod/fcm_server_key --secret-string ""
aws secretsmanager put-secret-value \
  --secret-id marketplace-prod/apns_key_pem --secret-string ""
aws ecs update-service --cluster marketplace --service marketplace-backend \
  --force-new-deployment
```

Re-enable by restoring the secret value and redeploying.

## Post-rollback checklist

- [ ] CloudWatch 5xx rate returning to baseline.
- [ ] Sentry issue volume decreasing.
- [ ] Synthetic probe from `/healthz/ready` is green.
- [ ] The failure that triggered rollback is captured as an issue with
      steps to reproduce, owner, and "no-retry-without-fix" label.
