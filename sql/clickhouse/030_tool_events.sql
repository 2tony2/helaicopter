CREATE TABLE IF NOT EXISTS {{database}}.tool_events
(
    provider LowCardinality(String),
    conversation_id String,
    session_id String,
    event_id String,
    tool_call_id String,
    tool_name LowCardinality(String),
    started_at DateTime64(3, 'UTC'),
    event_date Date MATERIALIZED toDate(started_at),
    finished_at Nullable(DateTime64(3, 'UTC')),
    duration_ms UInt64 DEFAULT 0,
    ordinal UInt32,
    project_path String DEFAULT '',
    project_name String DEFAULT '',
    git_branch String DEFAULT '',
    model LowCardinality(String) DEFAULT '',
    parent_message_id String DEFAULT '',
    parent_message_index UInt32 DEFAULT 0,
    tool_status LowCardinality(String) DEFAULT '',
    subagent_id String DEFAULT '',
    subagent_type LowCardinality(String) DEFAULT '',
    input_payload_json String DEFAULT '',
    output_payload_json String DEFAULT '',
    error_text String DEFAULT '',
    input_tokens Int64 DEFAULT 0,
    output_tokens Int64 DEFAULT 0,
    cache_write_tokens Int64 DEFAULT 0,
    cache_read_tokens Int64 DEFAULT 0,
    reasoning_tokens Int64 DEFAULT 0,
    estimated_total_cost Decimal(18, 8) DEFAULT 0,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (provider, conversation_id, started_at, tool_name, tool_call_id)
