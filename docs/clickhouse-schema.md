# ClickHouse Schema Bootstrap

This schema is the first tracked ClickHouse footprint for the kappa migration. It introduces:

- append-only raw conversation events
- append-only flattened message, tool, and usage event tables
- aggregate-backed views for latest conversation state
- aggregate-backed views for daily, tool, and subagent rollups

It does not replace the current SQLite or DuckDB runtime paths yet.

## Local Bootstrap

Start or reuse a local ClickHouse server and apply the tracked schema:

```bash
npm run db:bootstrap:clickhouse:local
```

If you already have ClickHouse running, apply the tracked schema with:

```bash
npm run db:bootstrap:clickhouse
```

The bootstrap is idempotent:

- it uses `CREATE DATABASE IF NOT EXISTS`
- every table and materialized view uses `IF NOT EXISTS`
- every derived view uses `CREATE OR REPLACE VIEW`
- re-running the bootstrap only reapplies the same tracked assets

The local helper defaults to:

- image: `clickhouse/clickhouse-server:25.3`
- host: `127.0.0.1`
- HTTP port: `8123`
- native port: `9000`
- user: `helaicopter`
- password: `helaicopter`
- database created by the DDL: `helaicopter`

Override it with:

```bash
HELAICOPTER_CLICKHOUSE_HOST=127.0.0.1
HELAICOPTER_CLICKHOUSE_PORT=8123
HELAICOPTER_CLICKHOUSE_DATABASE=helaicopter
HELAICOPTER_CLICKHOUSE_USER=helaicopter
HELAICOPTER_CLICKHOUSE_PASSWORD=helaicopter
HELAICOPTER_CLICKHOUSE_SECURE=0
HELAICOPTER_CLICKHOUSE_VERIFY_TLS=1
HELAICOPTER_CLICKHOUSE_CONNECT_TIMEOUT_SECONDS=5
HELAICOPTER_CLICKHOUSE_SEND_RECEIVE_TIMEOUT_SECONDS=30
```

The bootstrap loader lives in [python/helaicopter_db/clickhouse_bootstrap.py](/Users/tony/Code/helaicopter/python/helaicopter_db/clickhouse_bootstrap.py), the local helper script lives in [scripts/bootstrap-clickhouse-local.sh](/Users/tony/Code/helaicopter/scripts/bootstrap-clickhouse-local.sh), and the ordered DDL files live in [sql/clickhouse](/Users/tony/Code/helaicopter/sql/clickhouse).

## Layout

### Append-Only Event Tables

`conversation_events`

- Purpose: provider-agnostic raw event envelope for replay and backfill.
- Grain: one immutable event row per discovered conversation artifact.
- Partition: monthly on `event_date`.
- Sort key: `(provider, conversation_id, event_time, ordinal, event_id)`.

`message_events`

- Purpose: flattened message-level rows ready for read-optimized analytics.
- Grain: one immutable row per normalized message.
- Partition: monthly on `message_date`.
- Sort key: `(provider, conversation_id, message_time, message_index, message_id, event_id)`.

`tool_events`

- Purpose: flattened tool invocation/result records, including subagent metadata when a tool fans out into a spawned agent.
- Grain: one immutable row per normalized tool execution.
- Partition: monthly on `event_date`.
- Sort key: `(provider, conversation_id, started_at, tool_name, tool_call_id)`.

`usage_events`

- Purpose: token and cost deltas ready for aggregation without replaying raw payload JSON.
- Grain: one immutable usage delta row.
- Partition: monthly on `usage_date`.
- Sort key: `(usage_date, provider, conversation_id, event_time, ordinal, event_id)`.

### Latest Conversation State

The user-facing latest-state view is `conversation_state`. It is backed by four aggregate tables:

- `conversation_metadata_agg`
- `conversation_message_rollup_agg`
- `conversation_tool_rollup_agg`
- `conversation_usage_rollup_agg`

Each aggregate table is populated by a materialized view from exactly one append-only source table. That keeps the schema additive and avoids cross-table mutation logic.

`conversation_state`

- Purpose: latest per-conversation summary for future conversation list and analytics read paths.
- Primary key: `(provider, conversation_id)`.
- Partitioning: none. The aggregate inputs stay compact enough that monthly partitioning is not needed yet.
- Sort order of backing tables: `(provider, conversation_id)`.
- Derived fields:
  - latest project/model/session metadata from `conversation_events`
  - first and last message timing/text from `message_events`
  - tool and subagent counts from `tool_events`
  - token and cost totals from `usage_events`

### Daily Usage Rollups

The user-facing `daily_usage_rollups` view joins two backing aggregates:

- `daily_usage_metrics_agg` from `usage_events`
- `daily_usage_tool_agg` from `tool_events`

`daily_usage_rollups`

- Purpose: daily provider/model/project usage trends.
- Grain: one row per `(usage_date, provider, project_path, model)`.
- Partitioning of backing tables: monthly on `usage_date`.
- Sort order of backing tables: `(usage_date, provider, model, project_path)`.
- Metrics:
  - distinct conversation count
  - input/output/cache/reasoning tokens
  - estimated total cost
  - tool call count
  - subagent count

### Tool Usage Rollups

`tool_usage_rollups`

- Purpose: daily tool-level performance and volume summaries.
- Grain: one row per `(usage_date, provider, project_path, tool_name)`.
- Backing table: `tool_usage_rollups_agg`.
- Partitioning: monthly on `usage_date`.
- Sort order: `(usage_date, provider, tool_name, project_path)`.
- Metrics:
  - distinct conversation count
  - tool call count
  - error count
  - total duration
  - input/output tokens
  - estimated total cost

### Subagent Usage Rollups

`subagent_usage_rollups`

- Purpose: daily spawned-agent breakdowns by project and subagent type.
- Grain: one row per `(usage_date, provider, project_path, subagent_type)`.
- Backing table: `subagent_usage_rollups_agg`.
- Partitioning: monthly on `usage_date`.
- Sort order: `(usage_date, provider, subagent_type, project_path)`.
- Metrics:
  - distinct conversation count
  - subagent count
  - input/output tokens
  - estimated total cost

## Why These Keys

- Conversation-heavy tables sort by `(provider, conversation_id, time, ordinal)` because replay, point-lookups, and timeline scans all follow that access path.
- Daily rollups sort by `(date, provider, dimension, project)` because the expected analytics filters start with time windows and provider scoping.
- Monthly partitions keep local retention and backfill operations bounded without producing a large number of tiny partitions in development.

## DDL Inventory

Tracked DDL files live in lexical apply order:

- [sql/clickhouse/000_create_database.sql](/Users/tony/Code/helaicopter/sql/clickhouse/000_create_database.sql)
- [sql/clickhouse/010_conversation_events.sql](/Users/tony/Code/helaicopter/sql/clickhouse/010_conversation_events.sql)
- [sql/clickhouse/020_message_events.sql](/Users/tony/Code/helaicopter/sql/clickhouse/020_message_events.sql)
- [sql/clickhouse/030_tool_events.sql](/Users/tony/Code/helaicopter/sql/clickhouse/030_tool_events.sql)
- [sql/clickhouse/040_usage_events.sql](/Users/tony/Code/helaicopter/sql/clickhouse/040_usage_events.sql)
- [sql/clickhouse/050_conversation_metadata_agg.sql](/Users/tony/Code/helaicopter/sql/clickhouse/050_conversation_metadata_agg.sql)
- [sql/clickhouse/051_conversation_metadata_mv.sql](/Users/tony/Code/helaicopter/sql/clickhouse/051_conversation_metadata_mv.sql)
- [sql/clickhouse/052_conversation_message_rollup_agg.sql](/Users/tony/Code/helaicopter/sql/clickhouse/052_conversation_message_rollup_agg.sql)
- [sql/clickhouse/053_conversation_message_rollup_mv.sql](/Users/tony/Code/helaicopter/sql/clickhouse/053_conversation_message_rollup_mv.sql)
- [sql/clickhouse/054_conversation_tool_rollup_agg.sql](/Users/tony/Code/helaicopter/sql/clickhouse/054_conversation_tool_rollup_agg.sql)
- [sql/clickhouse/055_conversation_tool_rollup_mv.sql](/Users/tony/Code/helaicopter/sql/clickhouse/055_conversation_tool_rollup_mv.sql)
- [sql/clickhouse/056_conversation_usage_rollup_agg.sql](/Users/tony/Code/helaicopter/sql/clickhouse/056_conversation_usage_rollup_agg.sql)
- [sql/clickhouse/057_conversation_usage_rollup_mv.sql](/Users/tony/Code/helaicopter/sql/clickhouse/057_conversation_usage_rollup_mv.sql)
- [sql/clickhouse/058_conversation_state_view.sql](/Users/tony/Code/helaicopter/sql/clickhouse/058_conversation_state_view.sql)
- [sql/clickhouse/060_daily_usage_metrics_agg.sql](/Users/tony/Code/helaicopter/sql/clickhouse/060_daily_usage_metrics_agg.sql)
- [sql/clickhouse/061_daily_usage_metrics_mv.sql](/Users/tony/Code/helaicopter/sql/clickhouse/061_daily_usage_metrics_mv.sql)
- [sql/clickhouse/062_daily_usage_tool_agg.sql](/Users/tony/Code/helaicopter/sql/clickhouse/062_daily_usage_tool_agg.sql)
- [sql/clickhouse/063_daily_usage_tool_mv.sql](/Users/tony/Code/helaicopter/sql/clickhouse/063_daily_usage_tool_mv.sql)
- [sql/clickhouse/064_daily_usage_rollups_view.sql](/Users/tony/Code/helaicopter/sql/clickhouse/064_daily_usage_rollups_view.sql)
- [sql/clickhouse/070_tool_usage_rollups_agg.sql](/Users/tony/Code/helaicopter/sql/clickhouse/070_tool_usage_rollups_agg.sql)
- [sql/clickhouse/071_tool_usage_rollups_mv.sql](/Users/tony/Code/helaicopter/sql/clickhouse/071_tool_usage_rollups_mv.sql)
- [sql/clickhouse/072_tool_usage_rollups_view.sql](/Users/tony/Code/helaicopter/sql/clickhouse/072_tool_usage_rollups_view.sql)
- [sql/clickhouse/080_subagent_usage_rollups_agg.sql](/Users/tony/Code/helaicopter/sql/clickhouse/080_subagent_usage_rollups_agg.sql)
- [sql/clickhouse/081_subagent_usage_rollups_mv.sql](/Users/tony/Code/helaicopter/sql/clickhouse/081_subagent_usage_rollups_mv.sql)
- [sql/clickhouse/082_subagent_usage_rollups_view.sql](/Users/tony/Code/helaicopter/sql/clickhouse/082_subagent_usage_rollups_view.sql)
