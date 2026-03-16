CREATE TABLE IF NOT EXISTS {{database}}.daily_usage_metrics_agg
(
    usage_date Date,
    provider LowCardinality(String),
    project_path String,
    model LowCardinality(String),
    project_name_state AggregateFunction(argMax, String, DateTime64(3, 'UTC')),
    conversation_count_state AggregateFunction(uniqExact, String),
    input_tokens_state AggregateFunction(sum, Int64),
    output_tokens_state AggregateFunction(sum, Int64),
    cache_write_tokens_state AggregateFunction(sum, Int64),
    cache_read_tokens_state AggregateFunction(sum, Int64),
    reasoning_tokens_state AggregateFunction(sum, Int64),
    estimated_total_cost_state AggregateFunction(sum, Decimal(18, 8)),
    updated_at_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(usage_date)
ORDER BY (usage_date, provider, model, project_path)
