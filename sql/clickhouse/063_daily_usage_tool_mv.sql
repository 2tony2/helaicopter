CREATE MATERIALIZED VIEW IF NOT EXISTS {{database}}.daily_usage_tool_mv
TO {{database}}.daily_usage_tool_agg
AS
SELECT
    event_date AS usage_date,
    provider,
    project_path,
    model,
    sumState(toUInt64(1)) AS tool_call_count_state,
    sumState(toUInt64(if(subagent_type = '', 0, 1))) AS subagent_count_state,
    maxState(ingested_at) AS updated_at_state
FROM {{database}}.tool_events
GROUP BY usage_date, provider, project_path, model
