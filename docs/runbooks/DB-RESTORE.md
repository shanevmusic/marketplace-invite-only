# Runbook — Database Restore

The production database is Supabase Postgres.  Two recovery paths:

## Path A — Supabase Point-in-Time Recovery (PITR)

Supabase retains WAL for 7 days (Pro plan) or 30 days (Team plan).  PITR
is the default recovery path — it is lossless up to the chosen
timestamp.

1. Open the Supabase dashboard → Project → Database → Backups.
2. Choose **Restore to a point in time** and pick a UTC timestamp
   immediately before the incident.
3. Supabase provisions a restored database on the same or a new host.
   Acquiring the restored connection string takes 5–15 min.
4. **Do not** cut traffic over until you verify the restore:
   ```bash
   psql "$RESTORED_URL" -c "SELECT count(*) FROM users;"
   psql "$RESTORED_URL" -c "SELECT MAX(created_at) FROM orders;"
   ```
5. Rotate `APP_DATABASE_URL` / `APP_DATABASE_URL_SYNC` secrets in
   Secrets Manager, then force a new ECS deploy so tasks pick up the
   new URLs.

## Path B — Manual pg_dump / pg_restore (fallback)

Used when PITR is unavailable (plan downgrade, cross-region, or manual
export requirement).

### Creating a manual backup (routine)

```bash
pg_dump --no-owner --no-privileges \
  --format=custom \
  --file=marketplace-$(date -u +%Y%m%dT%H%M%S).dump \
  "$APP_DATABASE_URL_SYNC"
```

Store backups in S3 bucket `marketplace-db-backups-<env>` with
versioning and lifecycle (keep 30 days).  Nightly backups are a manual
`cron` placeholder — schedule with EventBridge + Lambda or an ECS
scheduled task when added.

### Restoring a manual backup

```bash
# Target DB should be empty or a fresh Supabase project.
pg_restore --clean --if-exists \
  --no-owner --no-privileges \
  --dbname="$RESTORE_URL" \
  marketplace-<ts>.dump
```

## After restore — required re-actions

- [ ] `alembic current` on the restored DB matches the code's expected head.
- [ ] Run `alembic upgrade head` if the code is newer than the dump.
- [ ] Rotate any secrets that may have leaked during the incident.
- [ ] Re-publish the cached list-unread-count WebSocket state by
      bouncing ECS tasks (`force-new-deployment`) — in-memory state is
      lost on restart, which is fine.
- [ ] Verify S3 uploads still resolve (bucket is out-of-band from DB).

## Data loss accounting

Whatever window between the restore point and the incident is lost.
The IC announces this explicitly in the post-mortem.  Customers whose
orders/messages fall in the gap must be notified by support.
