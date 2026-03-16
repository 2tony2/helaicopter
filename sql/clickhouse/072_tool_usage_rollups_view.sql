CREATE VIEW IF NOT EXISTS {{database}}.tool_usage_rollups
AS
SELECT
    usage_date,
    provider,
    project_path,
    argMaxMerge(project_name_state) AS project_name,
    tool_name,
    uniqExactMerge(conversation_count_state) AS conversation_count,
    sumMerge(tool_call_count_state) AS tool_call_count,
    sumMerge(error_count_state) AS error_count,
    sumMerge(total_duration_ms_state) AS total_duration_ms,
    sumMerge(input_tokens_state) AS input_tokens,
    sumMerge(output_tokens_state) AS output_tokens,
    sumMerge(estimated_total_cost_state) AS estimated_total_cost,
    maxMerge(updated_at_state) AS updated_at
FROM {{database}}.tool_usage_rollups_agg
GROUP BY usage_date, provider, project_path, tool_name
