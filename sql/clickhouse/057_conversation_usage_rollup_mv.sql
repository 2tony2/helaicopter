CREATE MATERIALIZED VIEW IF NOT EXISTS {{database}}.conversation_usage_rollup_mv
TO {{database}}.conversation_usage_rollup_agg
AS
SELECT
    provider,
    conversation_id,
    sumState(input_tokens) AS total_input_tokens_state,
    sumState(output_tokens) AS total_output_tokens_state,
    sumState(cache_write_tokens) AS total_cache_write_tokens_state,
    sumState(cache_read_tokens) AS total_cache_read_tokens_state,
    sumState(reasoning_tokens) AS total_reasoning_tokens_state,
    sumState(estimated_input_cost) AS estimated_input_cost_state,
    sumState(estimated_output_cost) AS estimated_output_cost_state,
    sumState(estimated_cache_write_cost) AS estimated_cache_write_cost_state,
    sumState(estimated_cache_read_cost) AS estimated_cache_read_cost_state,
    sumState(estimated_total_cost) AS estimated_total_cost_state,
    maxState(event_time) AS last_usage_at_state,
    maxState(ingested_at) AS updated_at_state
FROM {{database}}.usage_events
GROUP BY provider, conversation_id
