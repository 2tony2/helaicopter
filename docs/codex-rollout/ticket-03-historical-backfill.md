# Ticket 03: Implement Historical Backfill Into ClickHouse

## Mission

Reuse the existing export pipeline to load historical conversation data into ClickHouse idempotently.

## Architecture Context

- Read `docs/clickhouse-kappa-architecture.md` first.
- `scripts/export-parsed-data.ts` already emits normalized conversation envelopes from raw logs.
- `python/helaicopter_db/refresh.py` currently rebuilds SQLite detail data and DuckDB aggregates.
- This ticket should keep SQLite OLTP detail writes intact while adding ClickHouse backfill.

## Required Outcome

Historical conversations before today can be inserted into ClickHouse through a repeatable backfill path.

## Requirements

- Reuse or adapt the current export pipeline so historical conversations can feed ClickHouse.
- Make the backfill idempotent using stable event identifiers or deterministic replacement semantics.
- Preserve current SQLite OLTP artifact generation unless a small refactor is required.
- Keep DuckDB fallback behavior in place for now.
- Update refresh bookkeeping so backfill success or failure is visible.

## Validation

- Running the backfill twice does not create duplicate analytical rows.
- Historical ClickHouse aggregates are directionally consistent with the current analytics output for the same time window.
- Any new scripts or commands are documented.

## Runner Contract

- You are already on a runner-created branch based on `main`.
- Do not create or switch branches.
- Do not create PRs or merge anything.
- Implement the ticket end-to-end and run the required validation before finishing.
