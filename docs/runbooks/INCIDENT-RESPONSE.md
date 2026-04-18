# Runbook — Incident Response

## Severity ladder

| Level | Criteria                                                             | Response                                       |
|-------|----------------------------------------------------------------------|------------------------------------------------|
| SEV-1 | Full API outage, data loss, security breach.                         | Page on-call immediately; all-hands.           |
| SEV-2 | Major feature broken for >5% of users, auth degraded.                | Page on-call; single incident commander.       |
| SEV-3 | Minor feature broken, single-region latency, no user impact yet.     | On-call acknowledges during business hours.    |
| SEV-4 | Cosmetic / self-heals / known transient.                             | Ticket only.                                   |

## On-call rotation

*Placeholder — fill in as the team grows.*  Weekly rotation, primary +
backup.  Rotation managed in `#oncall` Slack channel.  Pager duty via
PagerDuty or equivalent — see SNS topic `ops-alerts-prod`.

## Incident commander (IC) responsibilities

1. Declare the severity in `#incidents`.
2. Pick a scribe (anyone not directly mitigating).
3. Time-box mitigation investigations (15 min max before escalating).
4. Decide when to rollback vs. roll-forward.
5. Coordinate external comms with marketing / support.

## Comms template (internal)

```
SEV-<N> — <one-line summary>
Started: <UTC timestamp>
Impact:  <who is affected, what they see>
Current: <what we know and what we've tried>
Next:    <next concrete action, who owns, by when>
IC:      @name   Scribe: @name
Thread:  <link>
```

## Comms template (external — customers)

```
We're investigating an issue affecting <X>.  You may experience <Y>.
We'll share an update by <HH:MM UTC>.
```

Keep external updates lagged 10–15 min behind internal investigation
so we don't promise fixes we haven't verified.

## Post-incident

Within 48h, IC writes a blameless post-mortem in `docs/incidents/`
(create directory as needed).  Sections: timeline, impact, root cause,
contributing factors, action items with owners and due dates.
