CREATE TABLE IF NOT EXISTS {{database}}.conversation_tool_rollup_agg
(
    provider LowCardinality(String),
    conversation_id String,
    tool_call_count_state AggregateFunction(sum, UInt64),
    subagent_count_state AggregateFunction(sum, UInt64),
    last_tool_time_state AggregateFunction(max, DateTime64(3, 'UTC')),
    updated_at_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
ORDER BY (provider, conversation_id)
