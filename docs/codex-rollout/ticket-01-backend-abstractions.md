# Ticket 01: Introduce Backend Abstractions And Feature Flags

## Mission

Create clean seams for the ClickHouse migration without changing current behavior by default.

## Architecture Context

- The current architecture note is in `docs/clickhouse-kappa-architecture.md`.
- `src/app/api/analytics/route.ts` directly calls the in-process analytics path.
- `src/app/api/conversations/route.ts` directly calls the merged conversation path.
- `src/lib/claude-data.ts` mixes historical SQLite reads and live parser reads.
- `src/lib/conversation-db.ts` is tightly coupled to the current SQLite historical path.

## Required Outcome

Add a backend abstraction layer and feature flags so later tickets can plug in ClickHouse reads without a flag-day rewrite.

## Requirements

- Add configuration flags for:
  - ClickHouse analytics reads
  - ClickHouse conversation summary reads
  - live ingestion mode
- Add a query/backend abstraction so API routes do not call the hardcoded implementation directly.
- Keep existing behavior as the default path.
- Add concise developer documentation for the new flags and how they affect runtime behavior.

## Validation

- Existing APIs still work with all new flags disabled.
- `npm run lint` passes.

## Runner Contract

- You are already on a runner-created branch based on `main`.
- Do not create or switch branches.
- Do not create PRs or merge anything.
- Implement the ticket end-to-end and run the required validation before finishing.
