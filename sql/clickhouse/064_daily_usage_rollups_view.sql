CREATE VIEW IF NOT EXISTS {{database}}.daily_usage_rollups
AS
SELECT
    rollup_keys.usage_date,
    rollup_keys.provider,
    rollup_keys.project_path,
    metrics.project_name,
    rollup_keys.model,
    metrics.conversation_count,
    metrics.input_tokens,
    metrics.output_tokens,
    metrics.cache_write_tokens,
    metrics.cache_read_tokens,
    metrics.reasoning_tokens,
    tooling.tool_call_count,
    tooling.subagent_count,
    metrics.estimated_total_cost,
    greatest(metrics.updated_at, tooling.updated_at) AS updated_at
FROM
(
    SELECT usage_date, provider, project_path, model
    FROM {{database}}.daily_usage_metrics_agg
    GROUP BY usage_date, provider, project_path, model
    UNION DISTINCT
    SELECT usage_date, provider, project_path, model
    FROM {{database}}.daily_usage_tool_agg
    GROUP BY usage_date, provider, project_path, model
) AS rollup_keys
LEFT JOIN
(
    SELECT
        usage_date,
        provider,
        project_path,
        model,
        argMaxMerge(project_name_state) AS project_name,
        uniqExactMerge(conversation_count_state) AS conversation_count,
        sumMerge(input_tokens_state) AS input_tokens,
        sumMerge(output_tokens_state) AS output_tokens,
        sumMerge(cache_write_tokens_state) AS cache_write_tokens,
        sumMerge(cache_read_tokens_state) AS cache_read_tokens,
        sumMerge(reasoning_tokens_state) AS reasoning_tokens,
        sumMerge(estimated_total_cost_state) AS estimated_total_cost,
        maxMerge(updated_at_state) AS updated_at
    FROM {{database}}.daily_usage_metrics_agg
    GROUP BY usage_date, provider, project_path, model
) AS metrics USING (usage_date, provider, project_path, model)
LEFT JOIN
(
    SELECT
        usage_date,
        provider,
        project_path,
        model,
        sumMerge(tool_call_count_state) AS tool_call_count,
        sumMerge(subagent_count_state) AS subagent_count,
        maxMerge(updated_at_state) AS updated_at
    FROM {{database}}.daily_usage_tool_agg
    GROUP BY usage_date, provider, project_path, model
) AS tooling USING (usage_date, provider, project_path, model)
