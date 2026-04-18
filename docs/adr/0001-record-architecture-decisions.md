# 1. Record architecture decisions

- Status: accepted
- Date: 2026-04-17

## Context

We need a lightweight, durable way to capture significant architecture and product decisions across phases and agents so that future agents (and humans) understand why the system looks the way it does.

## Decision

Use MADR-style Architecture Decision Records stored in `/docs/adr`, numbered sequentially (`NNNN-title.md`). Every change to the frozen stack or product logic in `PROJECT.md` requires a new ADR. Security and crypto choices always require an ADR.

## Consequences

- Clear audit trail of decisions and trade-offs.
- Slight overhead per decision, acceptable given the multi-agent workflow.

## Alternatives considered

- Free-form notes in PROJECT.md — rejected: doesn't scale, hard to audit.
- Wiki / external tool — rejected: keeps decisions away from the code.
