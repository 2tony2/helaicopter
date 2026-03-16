CREATE TABLE IF NOT EXISTS {{database}}.usage_events
(
    provider LowCardinality(String),
    conversation_id String,
    session_id String,
    event_id String,
    event_time DateTime64(3, 'UTC'),
    usage_date Date MATERIALIZED toDate(event_time),
    ordinal UInt32,
    project_path String DEFAULT '',
    project_name String DEFAULT '',
    git_branch String DEFAULT '',
    model LowCardinality(String) DEFAULT '',
    message_id String DEFAULT '',
    message_index UInt32 DEFAULT 0,
    tool_call_id String DEFAULT '',
    usage_source LowCardinality(String) DEFAULT '',
    input_tokens Int64 DEFAULT 0,
    output_tokens Int64 DEFAULT 0,
    cache_write_tokens Int64 DEFAULT 0,
    cache_read_tokens Int64 DEFAULT 0,
    reasoning_tokens Int64 DEFAULT 0,
    estimated_input_cost Decimal(18, 8) DEFAULT 0,
    estimated_output_cost Decimal(18, 8) DEFAULT 0,
    estimated_cache_write_cost Decimal(18, 8) DEFAULT 0,
    estimated_cache_read_cost Decimal(18, 8) DEFAULT 0,
    estimated_total_cost Decimal(18, 8) DEFAULT 0,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(usage_date)
ORDER BY (usage_date, provider, conversation_id, event_time, ordinal, event_id)
