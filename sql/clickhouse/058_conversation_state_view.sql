CREATE VIEW IF NOT EXISTS {{database}}.conversation_state
AS
SELECT
    conversation_keys.provider,
    conversation_keys.conversation_id,
    metadata.session_id,
    metadata.project_path,
    metadata.project_name,
    metadata.git_branch,
    metadata.latest_model,
    nullIf(metadata.started_at, toDateTime64('1970-01-01 00:00:00', 3, 'UTC')) AS started_at,
    nullIf(metadata.last_event_at, toDateTime64('1970-01-01 00:00:00', 3, 'UTC')) AS last_event_at,
    if(
        metadata.terminal_event_seen > 0,
        nullIf(metadata.ended_at, toDateTime64('1970-01-01 00:00:00', 3, 'UTC')),
        NULL
    ) AS ended_at,
    nullIf(messages.first_message_time, toDateTime64('1970-01-01 00:00:00', 3, 'UTC')) AS first_message_time,
    nullIf(messages.last_message_time, toDateTime64('1970-01-01 00:00:00', 3, 'UTC')) AS last_message_time,
    messages.first_message_text,
    messages.last_message_text,
    messages.message_count,
    tools.tool_call_count,
    tools.subagent_count,
    usage.total_input_tokens,
    usage.total_output_tokens,
    usage.total_cache_write_tokens,
    usage.total_cache_read_tokens,
    usage.total_reasoning_tokens,
    usage.estimated_input_cost,
    usage.estimated_output_cost,
    usage.estimated_cache_write_cost,
    usage.estimated_cache_read_cost,
    usage.estimated_total_cost,
    metadata.last_event_type,
    greatest(metadata.updated_at, messages.updated_at, tools.updated_at, usage.updated_at) AS updated_at
FROM
(
    SELECT provider, conversation_id
    FROM {{database}}.conversation_metadata_agg
    GROUP BY provider, conversation_id
    UNION DISTINCT
    SELECT provider, conversation_id
    FROM {{database}}.conversation_message_rollup_agg
    GROUP BY provider, conversation_id
    UNION DISTINCT
    SELECT provider, conversation_id
    FROM {{database}}.conversation_tool_rollup_agg
    GROUP BY provider, conversation_id
    UNION DISTINCT
    SELECT provider, conversation_id
    FROM {{database}}.conversation_usage_rollup_agg
    GROUP BY provider, conversation_id
) AS conversation_keys
LEFT JOIN
(
    SELECT
        provider,
        conversation_id,
        argMaxMerge(session_id_state) AS session_id,
        argMaxMerge(project_path_state) AS project_path,
        argMaxMerge(project_name_state) AS project_name,
        argMaxMerge(git_branch_state) AS git_branch,
        argMaxMerge(latest_model_state) AS latest_model,
        minMerge(started_at_state) AS started_at,
        maxMerge(last_event_at_state) AS last_event_at,
        maxMerge(ended_at_state) AS ended_at,
        maxMerge(terminal_event_seen_state) AS terminal_event_seen,
        argMaxMerge(last_event_type_state) AS last_event_type,
        maxMerge(updated_at_state) AS updated_at
    FROM {{database}}.conversation_metadata_agg
    GROUP BY provider, conversation_id
) AS metadata USING (provider, conversation_id)
LEFT JOIN
(
    SELECT
        provider,
        conversation_id,
        minMerge(first_message_time_state) AS first_message_time,
        maxMerge(last_message_time_state) AS last_message_time,
        argMinMerge(first_message_text_state) AS first_message_text,
        argMaxMerge(last_message_text_state) AS last_message_text,
        sumMerge(message_count_state) AS message_count,
        maxMerge(updated_at_state) AS updated_at
    FROM {{database}}.conversation_message_rollup_agg
    GROUP BY provider, conversation_id
) AS messages USING (provider, conversation_id)
LEFT JOIN
(
    SELECT
        provider,
        conversation_id,
        sumMerge(tool_call_count_state) AS tool_call_count,
        sumMerge(subagent_count_state) AS subagent_count,
        maxMerge(updated_at_state) AS updated_at
    FROM {{database}}.conversation_tool_rollup_agg
    GROUP BY provider, conversation_id
) AS tools USING (provider, conversation_id)
LEFT JOIN
(
    SELECT
        provider,
        conversation_id,
        sumMerge(total_input_tokens_state) AS total_input_tokens,
        sumMerge(total_output_tokens_state) AS total_output_tokens,
        sumMerge(total_cache_write_tokens_state) AS total_cache_write_tokens,
        sumMerge(total_cache_read_tokens_state) AS total_cache_read_tokens,
        sumMerge(total_reasoning_tokens_state) AS total_reasoning_tokens,
        sumMerge(estimated_input_cost_state) AS estimated_input_cost,
        sumMerge(estimated_output_cost_state) AS estimated_output_cost,
        sumMerge(estimated_cache_write_cost_state) AS estimated_cache_write_cost,
        sumMerge(estimated_cache_read_cost_state) AS estimated_cache_read_cost,
        sumMerge(estimated_total_cost_state) AS estimated_total_cost,
        maxMerge(updated_at_state) AS updated_at
    FROM {{database}}.conversation_usage_rollup_agg
    GROUP BY provider, conversation_id
) AS usage USING (provider, conversation_id)
