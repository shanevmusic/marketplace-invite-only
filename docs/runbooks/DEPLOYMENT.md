# Runbook — Deployment

## Normal deploy (from main)

1. PR merges to `main`.
2. `deploy-main.yml` triggers:
   - OIDC-assumes the CI role.
   - `docker build` + `docker push` → ECR tagged with the short SHA.
   - `aws ecs run-task --command alembic upgrade head` (waits for exit 0).
   - `amazon-ecs-deploy-task-definition` — rolling deploy, 50% min healthy,
     `wait-for-service-stability: true`.
3. CloudWatch `/ecs/marketplace-backend` is the first place to watch for
   task startup errors.

Expected duration: 5–8 min (migration + rolling task replacement).

## Hotfix (urgent patch, no merge to main)

```bash
# From a hotfix branch:
gh workflow run deploy-main.yml --ref hotfix/<name> --field image_tag=<sha>
```

- Only `main` is allowed to push to prod — so a hotfix must first be
  fast-forwarded into main via a merge commit.
- If the hotfix MUST ship before tests complete, reviewers approve the
  PR and merge, then immediately re-run `deploy-main` manually.

## Rollback

Two paths — **image rollback** (no data change) vs. **migration rollback**
(data change required).

### Image-only rollback

```bash
PREV_TAG=<previous-short-sha>
aws ecs update-service \
  --cluster marketplace \
  --service marketplace-backend \
  --force-new-deployment \
  --task-definition "marketplace-backend:<prev-revision>"
```

Rollback completes in 3–5 min.  Previous revisions are visible in:

```bash
aws ecs list-task-definitions --family-prefix marketplace-backend --sort DESC
```

### Migration rollback

See `DB-RESTORE.md` — do not blindly `alembic downgrade` in production.

## Validation after deploy

- `curl https://api.<env>.marketplace.example/healthz/ready` → 200
- CloudWatch "HTTPCode_Target_5XX_Count" stays near zero for 10 min.
- Sentry issues tab — no new unresolved issues spike.
