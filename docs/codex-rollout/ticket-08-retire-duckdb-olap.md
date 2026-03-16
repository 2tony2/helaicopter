# Ticket 08: Retire DuckDB OLAP And Update Operational Surfaces

## Mission

Finish the migration by removing DuckDB-first OLAP assumptions and updating the operational surfaces to represent SQLite plus ClickHouse accurately.

## Architecture Context

- Read `docs/clickhouse-kappa-architecture.md` first.
- `python/helaicopter_db/settings.py`, `python/helaicopter_db/status.py`, and the database dashboard still describe DuckDB as the OLAP engine.
- This ticket should happen only after ClickHouse-backed reads and live ingestion are working.

## Required Outcome

The app no longer presents DuckDB as the primary OLAP backend, and the runtime/docs/status surfaces align with the actual ClickHouse-backed architecture.

## Requirements

- Remove or demote DuckDB OLAP from the primary path.
- Update status endpoints and the database dashboard to reflect SQLite plus ClickHouse accurately.
- Update setup docs and troubleshooting notes.
- Remove dead code only after the ClickHouse-backed paths are stable.

## Validation

- The app no longer claims DuckDB is the active OLAP backend.
- Status and docs match the real runtime architecture.
- Core analytics no longer depend on DuckDB.

## Runner Contract

- You are already on a runner-created branch based on `main`.
- Do not create or switch branches.
- Do not create PRs or merge anything.
- Implement the ticket end-to-end and run the required validation before finishing.
