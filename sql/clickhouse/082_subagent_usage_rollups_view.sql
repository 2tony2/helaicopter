CREATE VIEW IF NOT EXISTS {{database}}.subagent_usage_rollups
AS
SELECT
    usage_date,
    provider,
    project_path,
    argMaxMerge(project_name_state) AS project_name,
    subagent_type,
    uniqExactMerge(conversation_count_state) AS conversation_count,
    sumMerge(subagent_count_state) AS subagent_count,
    sumMerge(input_tokens_state) AS input_tokens,
    sumMerge(output_tokens_state) AS output_tokens,
    sumMerge(estimated_total_cost_state) AS estimated_total_cost,
    maxMerge(updated_at_state) AS updated_at
FROM {{database}}.subagent_usage_rollups_agg
GROUP BY usage_date, provider, project_path, subagent_type
