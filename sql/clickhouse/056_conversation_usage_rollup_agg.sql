CREATE TABLE IF NOT EXISTS {{database}}.conversation_usage_rollup_agg
(
    provider LowCardinality(String),
    conversation_id String,
    total_input_tokens_state AggregateFunction(sum, Int64),
    total_output_tokens_state AggregateFunction(sum, Int64),
    total_cache_write_tokens_state AggregateFunction(sum, Int64),
    total_cache_read_tokens_state AggregateFunction(sum, Int64),
    total_reasoning_tokens_state AggregateFunction(sum, Int64),
    estimated_input_cost_state AggregateFunction(sum, Decimal(18, 8)),
    estimated_output_cost_state AggregateFunction(sum, Decimal(18, 8)),
    estimated_cache_write_cost_state AggregateFunction(sum, Decimal(18, 8)),
    estimated_cache_read_cost_state AggregateFunction(sum, Decimal(18, 8)),
    estimated_total_cost_state AggregateFunction(sum, Decimal(18, 8)),
    last_usage_at_state AggregateFunction(max, DateTime64(3, 'UTC')),
    updated_at_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
ORDER BY (provider, conversation_id)
