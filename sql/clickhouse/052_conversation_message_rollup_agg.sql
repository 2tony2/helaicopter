CREATE TABLE IF NOT EXISTS {{database}}.conversation_message_rollup_agg
(
    provider LowCardinality(String),
    conversation_id String,
    first_message_time_state AggregateFunction(min, DateTime64(3, 'UTC')),
    last_message_time_state AggregateFunction(max, DateTime64(3, 'UTC')),
    first_message_text_state AggregateFunction(argMin, String, Tuple(DateTime64(3, 'UTC'), UInt32)),
    last_message_text_state AggregateFunction(argMax, String, Tuple(DateTime64(3, 'UTC'), UInt32)),
    message_count_state AggregateFunction(sum, UInt64),
    updated_at_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
ORDER BY (provider, conversation_id)
