CREATE MATERIALIZED VIEW IF NOT EXISTS {{database}}.conversation_tool_rollup_mv
TO {{database}}.conversation_tool_rollup_agg
AS
SELECT
    provider,
    conversation_id,
    sumState(toUInt64(1)) AS tool_call_count_state,
    sumState(toUInt64(if(subagent_type = '', 0, 1))) AS subagent_count_state,
    maxState(started_at) AS last_tool_time_state,
    maxState(ingested_at) AS updated_at_state
FROM {{database}}.tool_events
GROUP BY provider, conversation_id
