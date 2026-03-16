CREATE MATERIALIZED VIEW IF NOT EXISTS {{database}}.daily_usage_metrics_mv
TO {{database}}.daily_usage_metrics_agg
AS
SELECT
    usage_date,
    provider,
    project_path,
    model,
    argMaxState(project_name, event_time) AS project_name_state,
    uniqExactState(conversation_id) AS conversation_count_state,
    sumState(input_tokens) AS input_tokens_state,
    sumState(output_tokens) AS output_tokens_state,
    sumState(cache_write_tokens) AS cache_write_tokens_state,
    sumState(cache_read_tokens) AS cache_read_tokens_state,
    sumState(reasoning_tokens) AS reasoning_tokens_state,
    sumState(estimated_total_cost) AS estimated_total_cost_state,
    maxState(ingested_at) AS updated_at_state
FROM {{database}}.usage_events
GROUP BY usage_date, provider, project_path, model
