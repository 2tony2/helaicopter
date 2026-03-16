CREATE MATERIALIZED VIEW IF NOT EXISTS {{database}}.subagent_usage_rollups_mv
TO {{database}}.subagent_usage_rollups_agg
AS
SELECT
    event_date AS usage_date,
    provider,
    project_path,
    subagent_type,
    argMaxState(project_name, started_at) AS project_name_state,
    uniqExactState(conversation_id) AS conversation_count_state,
    sumState(toUInt64(1)) AS subagent_count_state,
    sumState(input_tokens) AS input_tokens_state,
    sumState(output_tokens) AS output_tokens_state,
    sumState(estimated_total_cost) AS estimated_total_cost_state,
    maxState(ingested_at) AS updated_at_state
FROM {{database}}.tool_events
WHERE subagent_type != ''
GROUP BY usage_date, provider, project_path, subagent_type
