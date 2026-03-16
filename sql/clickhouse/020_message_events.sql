CREATE TABLE IF NOT EXISTS {{database}}.message_events
(
    provider LowCardinality(String),
    conversation_id String,
    session_id String,
    event_id String,
    message_id String,
    message_index UInt32,
    message_time DateTime64(3, 'UTC'),
    message_date Date MATERIALIZED toDate(message_time),
    ordinal UInt32,
    project_path String DEFAULT '',
    project_name String DEFAULT '',
    git_branch String DEFAULT '',
    model LowCardinality(String) DEFAULT '',
    role LowCardinality(String) DEFAULT '',
    author_name String DEFAULT '',
    message_kind LowCardinality(String) DEFAULT '',
    content_text String DEFAULT '',
    content_json String DEFAULT '',
    input_tokens Int64 DEFAULT 0,
    output_tokens Int64 DEFAULT 0,
    cache_write_tokens Int64 DEFAULT 0,
    cache_read_tokens Int64 DEFAULT 0,
    reasoning_tokens Int64 DEFAULT 0,
    estimated_total_cost Decimal(18, 8) DEFAULT 0,
    has_tool_calls UInt8 DEFAULT 0,
    is_error UInt8 DEFAULT 0,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(message_date)
ORDER BY (provider, conversation_id, message_time, message_index, message_id, event_id)
