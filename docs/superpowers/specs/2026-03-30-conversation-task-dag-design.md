# Conversation Task DAG Design

## Goal

Replace the raw JSON task dump in conversation detail with a graph-native task view that uses the app's existing DAG presentation style. The Tasks tab should render Claude/OpenClaw task payloads when available and should also show Codex task structure by deriving nodes from Codex `update_plan` steps.

## Decisions

### Task source resolution

- Use persisted/live `/tasks` payloads as the primary source for conversation tasks.
- For Codex conversations, if the task payload is empty, derive a synthetic task list from the latest available conversation plan.
- Keep the raw payload available below the graph for debugging instead of removing it completely.

### DAG shaping

- Normalize task-like objects into a shared frontend shape with `taskId`, `title`, `status`, and `dependsOn`.
- Prefer explicit dependency fields when present: `dependsOn`, `depends_on`, `dependencies`, and `dependents`.
- When no dependency metadata exists, preserve author intent by linking tasks in their listed order as a simple linear DAG.
- For Codex plans, each step becomes one task node and the graph is a linear ordered chain.

### UI

- Add a dedicated conversation task DAG component that reuses the existing React Flow + dagre layout pattern already used by conversation and orchestration DAGs.
- Show a compact summary strip plus graph canvas first, then a structured task list / raw JSON fallback underneath.
- Keep the tab resilient: if parsing yields no meaningful tasks, show a friendly empty state instead of broken graph chrome.

## Testing

- Add pure unit tests for task normalization and DAG edge inference.
- Add a conversation viewer test that verifies the Tasks tab renders graph content for Codex plan-only conversations and no longer relies on a raw JSON-only presentation.
