CREATE MATERIALIZED VIEW IF NOT EXISTS {{database}}.tool_usage_rollups_mv
TO {{database}}.tool_usage_rollups_agg
AS
SELECT
    event_date AS usage_date,
    provider,
    project_path,
    tool_name,
    argMaxState(project_name, started_at) AS project_name_state,
    uniqExactState(conversation_id) AS conversation_count_state,
    sumState(toUInt64(1)) AS tool_call_count_state,
    sumState(toUInt64(if(error_text = '', 0, 1))) AS error_count_state,
    sumState(duration_ms) AS total_duration_ms_state,
    sumState(input_tokens) AS input_tokens_state,
    sumState(output_tokens) AS output_tokens_state,
    sumState(estimated_total_cost) AS estimated_total_cost_state,
    maxState(ingested_at) AS updated_at_state
FROM {{database}}.tool_events
GROUP BY usage_date, provider, project_path, tool_name
