# Ticket 07: Move Conversation Summaries Off The Today Historical Split

## Mission

Serve conversation summaries from one backend path instead of merging historical SQLite rows with today's raw parser output.

## Architecture Context

- Read `docs/clickhouse-kappa-architecture.md` first.
- `src/lib/claude-data.ts:listConversations()` currently merges historical SQLite summaries with today's raw parser path.
- This split exists because historical data is warehouse-backed but live data is not.
- Earlier tickets should have introduced live ingestion and ClickHouse latest-state tables.

## Required Outcome

When the feature flag is enabled, conversation summaries are served from one backend path backed by ClickHouse latest-state data rather than the current today-versus-before-today merge.

## Requirements

- Add ClickHouse-backed conversation summary reads for the list page.
- Preserve SQLite point-lookups for conversation detail if they are still helpful.
- Remove the today historical merge logic from the enabled path.
- Keep a safe fallback path until the unified summary path is validated.

## Validation

- The conversation list shows historical and current sessions from one backend path under the feature flag.
- Provider filters and date filters still behave correctly.
- The list updates quickly when new sessions or messages arrive.

## Runner Contract

- You are already on a runner-created branch based on `main`.
- Do not create or switch branches.
- Do not create PRs or merge anything.
- Implement the ticket end-to-end and run the required validation before finishing.
