# Ticket 04: Serve Analytics From ClickHouse Behind A Flag

## Mission

Stop recalculating dashboard analytics in Node when the ClickHouse flag is enabled.

## Architecture Context

- Read `docs/clickhouse-kappa-architecture.md` first.
- `src/lib/claude-data.ts:getAnalytics()` is still an in-memory aggregation path.
- `src/app/api/analytics/route.ts` should keep the same response shape during migration.
- Earlier tickets should have introduced the backend abstraction and ClickHouse schema/backfill path.

## Required Outcome

The analytics API can serve the existing response shape from ClickHouse behind a feature flag, with the legacy path preserved as fallback.

## Requirements

- Implement ClickHouse-backed analytics queries for the existing `/api/analytics` contract.
- Preserve provider filtering and date-window behavior.
- Keep the current TypeScript implementation as the fallback path when the flag is off or ClickHouse is unavailable.
- Add comparison or debug support so the legacy and ClickHouse outputs can be checked during rollout.

## Validation

- `/api/analytics` returns the same shape as before.
- The dashboard works with the flag both on and off.
- For at least one representative date window, the new and old results are close enough to explain any intended differences.

## Runner Contract

- You are already on a runner-created branch based on `main`.
- Do not create or switch branches.
- Do not create PRs or merge anything.
- Implement the ticket end-to-end and run the required validation before finishing.
