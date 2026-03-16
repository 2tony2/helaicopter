CREATE TABLE IF NOT EXISTS {{database}}.daily_usage_tool_agg
(
    usage_date Date,
    provider LowCardinality(String),
    project_path String,
    model LowCardinality(String),
    tool_call_count_state AggregateFunction(sum, UInt64),
    subagent_count_state AggregateFunction(sum, UInt64),
    updated_at_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(usage_date)
ORDER BY (usage_date, provider, model, project_path)
