CREATE MATERIALIZED VIEW IF NOT EXISTS {{database}}.conversation_metadata_mv
TO {{database}}.conversation_metadata_agg
AS
SELECT
    provider,
    conversation_id,
    argMaxState(session_id, tuple(event_time, ordinal)) AS session_id_state,
    argMaxState(project_path, tuple(event_time, ordinal)) AS project_path_state,
    argMaxState(project_name, tuple(event_time, ordinal)) AS project_name_state,
    argMaxState(git_branch, tuple(event_time, ordinal)) AS git_branch_state,
    argMaxState(model, tuple(event_time, ordinal)) AS latest_model_state,
    minState(event_time) AS started_at_state,
    maxState(event_time) AS last_event_at_state,
    maxState(
        if(
            is_terminal_event = 1,
            event_time,
            toDateTime64('1970-01-01 00:00:00', 3, 'UTC')
        )
    ) AS ended_at_state,
    maxState(is_terminal_event) AS terminal_event_seen_state,
    argMaxState(event_type, tuple(event_time, ordinal)) AS last_event_type_state,
    maxState(ingested_at) AS updated_at_state
FROM {{database}}.conversation_events
GROUP BY provider, conversation_id
