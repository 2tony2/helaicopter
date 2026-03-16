# ClickHouse Kappa Architecture Notes

## Current state in this repo

- Historical conversations are batch-exported from raw JSONL into:
  - SQLite OLTP for normalized detail records
  - DuckDB OLAP for aggregate facts and dimensions
- Today's conversations stay on the live parser path and are merged with historical data at read time.
- The main analytics API still computes aggregates in TypeScript by loading conversation summaries rather than querying the OLAP warehouse directly.

## What that means

The warehouse helps with artifact generation and historical storage, but it is not yet the serving layer for realtime analytics. The current bottlenecks are:

- repeated file walking and JSONL parsing for live data
- aggregation in Node for analytics responses
- a split serving model where historical and live data come from different paths
- batch refresh semantics for OLAP rather than append-only streaming semantics

## Recommendation

Use SQLite as the local/system-of-record metadata store and ClickHouse as the append-only event and analytics store.

That gives you:

- SQLite for lightweight app state, refresh status, settings, evaluations, and small transactional tables
- ClickHouse for high-ingest event logs, rollups, time-series queries, funnel analysis, tool latency, token usage, and provider/model breakdowns
- one serving path for both historical and near-realtime analytics

## Proposed kappa model

Treat every conversation artifact as an event stream:

- conversation discovered
- message appended
- tool call started
- tool call finished
- token usage updated
- plan emitted
- subagent spawned
- evaluation completed

Write those events into ClickHouse as immutable rows. Derive all analytics from those rows using materialized views and aggregate tables. Rebuild historical state by replaying the same source logs through the same ingestion path.

This is a better fit than the current "batch export + separate live parser merge" approach because both historical backfill and live updates use the same append-only model.

## Table shape

Suggested ClickHouse tables:

- `conversation_events`
  - one row per raw event from Claude/Codex logs
  - partition by event date
  - order by `(provider, session_id, event_time, ordinal)`
- `message_events`
  - flattened message-level records
- `tool_events`
  - one row per tool invocation/result pair
- `usage_events`
  - token and cost deltas
- `conversation_state`
  - materialized latest-state view per conversation
- `daily_usage_mv`
  - materialized rollup for daily analytics
- `tool_usage_mv`
  - materialized rollup for tool-level analytics
- `subagent_usage_mv`
  - materialized rollup for subagent analytics

Keep the raw-enough event tables. Do not only store final summaries, or you lose the main advantage of ClickHouse.

## SQLite role

SQLite should remain for:

- app-local settings and subscription config
- evaluation prompts and evaluation runs
- refresh bookkeeping
- small lookup tables or cached conversation metadata needed by the UI

SQLite should not be the primary analytics engine once you want fast, concurrent, multi-user or high-fanout queries.

## Go role

Go is a good fit for the ingestion and streaming side, not for replacing the whole app.

Use Go for:

- tailing conversation JSONL files
- watching filesystem changes
- parsing and normalizing raw events concurrently
- batching inserts to ClickHouse
- exposing SSE/WebSocket streams for live dashboard updates
- managing backpressure and retries cleanly

Keep Next.js for the UI and most API presentation logic unless you are already hitting Node CPU limits on parsing or fanout.

## Fast path design

Recommended flow:

1. Go watcher tails `~/.claude/` and `~/.codex/`.
2. Parsed events are normalized into a provider-agnostic event envelope.
3. Events are written to ClickHouse in batches every few hundred milliseconds.
4. Materialized views update aggregate tables automatically.
5. The UI queries ClickHouse-backed APIs for analytics and latest conversation state.
6. SQLite stays available for local metadata and control-plane state.

If you want a local-only deployment, run ClickHouse locally and keep SQLite in-process.

## Why this is faster

- ClickHouse is optimized for append-heavy analytical workloads and concurrent scans over wide event tables.
- Materialized views remove most repeated aggregation work from request time.
- The app no longer needs to recalculate analytics by replaying conversation summaries in Node.
- Live and historical data can be queried through one engine instead of merging two code paths.

## Migration path for this repo

1. Stop using `getAnalytics()` as an in-memory aggregation path.
2. Introduce ClickHouse-backed analytics queries behind the existing `/api/analytics` route.
3. Replace the historical DuckDB refresh job with an idempotent backfill into ClickHouse.
4. Add a live ingestion process for today's logs so "today" is no longer special.
5. Keep SQLite detail tables only where the UI still benefits from local point-lookups.
6. Remove the "historical before today vs live today" split once ClickHouse is trusted.

## Rollout flags

- `HELAICOPTER_USE_CLICKHOUSE_ANALYTICS_READS=1` switches `/api/analytics` to the ClickHouse query seam. Until the ClickHouse implementation lands, that backend falls through to the legacy in-process aggregator.
- `HELAICOPTER_USE_CLICKHOUSE_CONVERSATION_SUMMARIES=1` switches `/api/conversations` to the ClickHouse summary seam. Until the ClickHouse implementation lands, that backend falls through to the current SQLite-plus-live-parser merge.
- `HELAICOPTER_ENABLE_LIVE_INGESTION=1` marks runtime as expecting live data to come from ingestion rather than the special-case parser path. With the legacy read backends still selected, it has no effect.
- With all three flags unset or `0`, runtime behavior stays on the current default path.

## Cautions

- ClickHouse is not a replacement for every transactional need. Keep SQLite for small ACID metadata writes.
- Do not build the pipeline around full conversation rewrites; prefer append-only event ingestion plus derived latest-state tables.
- If you add Go, keep the boundary narrow: ingestion service, stream fanout, and ClickHouse writes.
- If local-only operation is mandatory, validate ClickHouse packaging and startup ergonomics before fully committing.
