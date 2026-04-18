# Runbooks

Operational procedures for the invite-only marketplace. Each runbook is
written for an on-call operator who just got paged — preconditions up
top, commands in copy-paste blocks, rollback path at the bottom.

## Index

| Runbook | One-line summary |
|---|---|
| [DEPLOYMENT.md](DEPLOYMENT.md) | Normal deploy, hotfix path, post-deploy validation. |
| [INCIDENT-RESPONSE.md](INCIDENT-RESPONSE.md) | Severity ladder, IC role, status-page + comms templates. |
| [DB-RESTORE.md](DB-RESTORE.md) | Supabase point-in-time recovery + `pg_restore` fallback for corrupt tables. |
| [SECRET-ROTATION.md](SECRET-ROTATION.md) | JWT primary↔secondary rotation with zero-downtime overlap. |
| [ROLLBACK.md](ROLLBACK.md) | Rolling back a bad image, a bad migration, or a feature flag. |
| [OBSERVABILITY.md](OBSERVABILITY.md) | Where logs, metrics, dashboards, alerts and Sentry events live. |

## Conventions

- **Severity**: SEV-1 (data loss or site down), SEV-2 (major feature
  degraded), SEV-3 (minor feature degraded), SEV-4 (nuisance).
- Every runbook starts with a *Preconditions* block naming the access
  and tools required. If you don't have them, escalate before acting.
- Commands prefix is `$ ` for local shell, `#` for a production bastion.
- All destructive commands (drops, force-pushes, restores) require a
  second-pair-of-eyes confirmation — never run them alone on a SEV-1.
