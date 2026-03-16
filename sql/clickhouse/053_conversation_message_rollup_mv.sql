CREATE MATERIALIZED VIEW IF NOT EXISTS {{database}}.conversation_message_rollup_mv
TO {{database}}.conversation_message_rollup_agg
AS
SELECT
    provider,
    conversation_id,
    minState(message_time) AS first_message_time_state,
    maxState(message_time) AS last_message_time_state,
    argMinState(content_text, tuple(message_time, message_index)) AS first_message_text_state,
    argMaxState(content_text, tuple(message_time, message_index)) AS last_message_text_state,
    sumState(toUInt64(1)) AS message_count_state,
    maxState(ingested_at) AS updated_at_state
FROM {{database}}.message_events
GROUP BY provider, conversation_id
