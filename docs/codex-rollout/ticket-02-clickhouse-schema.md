# Ticket 02: Define And Bootstrap The ClickHouse Schema

## Mission

Add the first ClickHouse schema and local bootstrap workflow needed for the kappa migration.

## Architecture Context

- Read `docs/clickhouse-kappa-architecture.md` first.
- `python/helaicopter_db/models/olap.py` models the current DuckDB-oriented OLAP layer.
- `python/helaicopter_db/settings.py` and `python/helaicopter_db/status.py` currently assume the OLAP engine is DuckDB.
- This ticket should introduce ClickHouse schema assets, not fully migrate query serving yet.

## Required Outcome

Create tracked DDL and bootstrap scripts for an append-only ClickHouse event model plus derived rollups.

## Requirements

- Add ClickHouse DDL for:
  - raw conversation events
  - flattened message events
  - tool events
  - usage events
  - latest conversation state
  - daily usage rollups
  - tool usage rollups
  - subagent usage rollups
- Add local bootstrap instructions and a script or scripts to initialize the schema.
- Add configuration plumbing for ClickHouse connection settings.
- Do not remove or break the existing SQLite or DuckDB paths yet.

## Validation

- The ClickHouse schema can be initialized idempotently in local development.
- New docs explain the schema layout, keys, partitions, and sort orders.
- `npm run lint` passes for any TypeScript changes.

## Runner Contract

- You are already on a runner-created branch based on `main`.
- Do not create or switch branches.
- Do not create PRs or merge anything.
- Implement the ticket end-to-end and run the required validation before finishing.
