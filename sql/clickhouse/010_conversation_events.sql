CREATE TABLE IF NOT EXISTS {{database}}.conversation_events
(
    provider LowCardinality(String),
    conversation_id String,
    session_id String,
    event_id String,
    event_time DateTime64(3, 'UTC'),
    event_date Date MATERIALIZED toDate(event_time),
    ordinal UInt32,
    event_type LowCardinality(String),
    project_path String DEFAULT '',
    project_name String DEFAULT '',
    git_branch String DEFAULT '',
    model LowCardinality(String) DEFAULT '',
    message_id String DEFAULT '',
    message_index UInt32 DEFAULT 0,
    message_role LowCardinality(String) DEFAULT '',
    tool_call_id String DEFAULT '',
    tool_name LowCardinality(String) DEFAULT '',
    tool_status LowCardinality(String) DEFAULT '',
    subagent_id String DEFAULT '',
    subagent_type LowCardinality(String) DEFAULT '',
    usage_input_tokens Int64 DEFAULT 0,
    usage_output_tokens Int64 DEFAULT 0,
    usage_cache_write_tokens Int64 DEFAULT 0,
    usage_cache_read_tokens Int64 DEFAULT 0,
    usage_reasoning_tokens Int64 DEFAULT 0,
    estimated_input_cost Decimal(18, 8) DEFAULT 0,
    estimated_output_cost Decimal(18, 8) DEFAULT 0,
    estimated_cache_write_cost Decimal(18, 8) DEFAULT 0,
    estimated_cache_read_cost Decimal(18, 8) DEFAULT 0,
    estimated_total_cost Decimal(18, 8) DEFAULT 0,
    is_terminal_event UInt8 DEFAULT 0,
    payload_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (provider, conversation_id, event_time, ordinal, event_id)
