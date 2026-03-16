CREATE TABLE IF NOT EXISTS {{database}}.tool_usage_rollups_agg
(
    usage_date Date,
    provider LowCardinality(String),
    project_path String,
    tool_name LowCardinality(String),
    project_name_state AggregateFunction(argMax, String, DateTime64(3, 'UTC')),
    conversation_count_state AggregateFunction(uniqExact, String),
    tool_call_count_state AggregateFunction(sum, UInt64),
    error_count_state AggregateFunction(sum, UInt64),
    total_duration_ms_state AggregateFunction(sum, UInt64),
    input_tokens_state AggregateFunction(sum, Int64),
    output_tokens_state AggregateFunction(sum, Int64),
    estimated_total_cost_state AggregateFunction(sum, Decimal(18, 8)),
    updated_at_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(usage_date)
ORDER BY (usage_date, provider, tool_name, project_path)
