CREATE TABLE IF NOT EXISTS {{database}}.conversation_metadata_agg
(
    provider LowCardinality(String),
    conversation_id String,
    session_id_state AggregateFunction(argMax, String, Tuple(DateTime64(3, 'UTC'), UInt32)),
    project_path_state AggregateFunction(argMax, String, Tuple(DateTime64(3, 'UTC'), UInt32)),
    project_name_state AggregateFunction(argMax, String, Tuple(DateTime64(3, 'UTC'), UInt32)),
    git_branch_state AggregateFunction(argMax, String, Tuple(DateTime64(3, 'UTC'), UInt32)),
    latest_model_state AggregateFunction(argMax, String, Tuple(DateTime64(3, 'UTC'), UInt32)),
    started_at_state AggregateFunction(min, DateTime64(3, 'UTC')),
    last_event_at_state AggregateFunction(max, DateTime64(3, 'UTC')),
    ended_at_state AggregateFunction(max, DateTime64(3, 'UTC')),
    terminal_event_seen_state AggregateFunction(max, UInt8),
    last_event_type_state AggregateFunction(argMax, String, Tuple(DateTime64(3, 'UTC'), UInt32)),
    updated_at_state AggregateFunction(max, DateTime64(3, 'UTC'))
)
ENGINE = AggregatingMergeTree
ORDER BY (provider, conversation_id)
