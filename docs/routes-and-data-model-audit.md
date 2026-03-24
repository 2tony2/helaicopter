# Route And Data Model Audit

## Scope

This audit covers the deeper conversation route graph, the orchestration and embedded legacy orchestration UI route shape, and the persisted conversation entity model that backs the API.

Date: `2026-03-19`

## Route Inventory

### Backend API

- `GET /conversations`
  Lists main and subagent conversation summaries.
- `GET /conversations/{project_path}/{session_id}`
  Returns one conversation detail.
- `GET /conversations/{project_path}/{session_id}/dag`
  Returns the backend-owned conversation DAG for a root or subagent thread.
- `GET /conversations/{project_path}/{session_id}/subagents/{agent_id}`
  Nested alias for loading a subagent transcript in conversation context. For persisted rows and Codex sessions, `agent_id` resolves as the child session identifier; `session_id` is primarily contextual today.
- `GET|POST /conversations/{project_path}/{session_id}/evaluations`
  Lists and creates evaluation jobs scoped to a conversation.
- `GET /conversation-dags`
  Lists root conversations that have DAG descendants.
- `GET /subagents/{project_path}/{session_id}/{agent_id}`
  Legacy flat alias for subagent detail. Kept for compatibility.
- `GET /orchestration/oats`
  Returns backend-shaped local Oats runtime artifacts.
- `GET /orchestration/legacy-orchestration/{deployments|flow-runs|workers|work-pools}`
  Returns backend-owned legacy orchestration control-plane data.

### Next App

- `/conversations/[projectPath]/[sessionId]`
  Root conversation detail page. Now accepts `tab`, `plan`, and `subagent` query params.
- `/conversations/[projectPath]/[sessionId]/subagents/[agentId]`
  Native nested alias for deep links. Redirects to the parent conversation with `?tab=subagents&subagent=...`.
- `/orchestration`
  Orchestration page. Now accepts `tab`, `flowRunId`, and `legacy-orchestrationPath`.

## Key Findings

### 1. Deeper conversation routes previously stopped at the root detail page

Before this change, the app had one native conversation page and rendered all deeper state in component-local state. That meant:

- DAG node clicks could only land on a top-level conversation page.
- Selected plan and selected subagent were not URL-addressable.
- Shared links lost the active tab and selected nested entity.

What changed:

- Conversation detail tab state is now URL-backed.
- Plan selection is now URL-backed.
- Subagent selection is now URL-backed.
- Nested app routes now exist for subagents and redirect into the canonical parent page state.
- DAG node paths now point at the nested subagent route for child nodes.
- Query-param state now resynchronizes from the URL, so browser back/forward navigation no longer leaves the active tab or selected nested entity stale in the UI.

### 2. legacy orchestration embed had a weak boundary between native app routing and iframe routing

Before this change, the legacy orchestration tab only embedded `http://127.0.0.1:4200` and the selected flow run lived in local state. That meant:

- Copying an orchestration URL did not preserve the selected flow run.
- The embedded legacy orchestration tab could not target a specific legacy orchestration page.
- Moving between the native dashboard and the iframe lost context.

What changed:

- Orchestration tab state is now URL-backed.
- Selected legacy orchestration flow run is now URL-backed.
- The embedded legacy orchestration iframe accepts a `legacy-orchestrationPath` query param so the app can preserve a native link to a specific legacy orchestration page.
- The legacy orchestration flow-run detail now exposes an in-app link to the embedded legacy orchestration UI for that run.

### 3. Persisted conversation entities had stable IDs, but the grain was implicit

The OLTP layer already used unique, deterministic IDs, but the code mostly built them inline. The entity boundaries were easy to miss:

- conversation
- message
- message block
- plan row
- subagent row
- task row
- context bucket
- context step

What changed:

- The domain layer now names these persisted identifiers explicitly.
- The DB utility layer now owns the ID builders instead of scattering string concatenation through the refresh pipeline.
- The refresh pipeline uses those builders directly, making the entity grain visible where rows are created.

## Entity And ID Grain

### Canonical conversation identity

- `conversation_id`
  Canonical persisted conversation key: `{provider}:{session_id}`
- `session_id`
  Provider-native thread/session identifier

### Persisted child entities

- `conversation_message_id`
  `{conversation_id}:message:{ordinal}`
- `conversation_message_block_id`
  `{conversation_message_id}:block:{block_index}`
- `conversation_plan_row_id`
  `{conversation_id}:plan:{ordinal}`
- `conversation_subagent_row_id`
  `{conversation_id}:subagent:{ordinal}`
- `conversation_task_row_id`
  `{conversation_id}:task:{ordinal}`
- `conversation_context_bucket_id`
  `{conversation_id}:bucket:{ordinal}`
- `conversation_context_step_id`
  `{conversation_id}:step:{ordinal}`

These are deterministic composite IDs, not random UUIDs. The raw provider event UUIDs still exist at the source-event grain, but the persisted app model now makes the app-owned entity grain explicit and unique.

One important exception remains: context-step `message_id` still carries the source/provider message identifier from analytics payloads rather than the persisted `conversation_message_id`. That mixed grain is now called out explicitly in code and should be normalized in a follow-up if we want full row-key consistency across every child entity.

## Remaining Weak Spots

- The legacy flat subagent API route is still present. It should be removed after clients stop depending on it.
- The nested subagent API route is only strictly parent-scoped for the Claude live-file fallback. Persisted rows and Codex sessions currently resolve by child session ID, so the parent segment is contextual rather than enforced.
- legacy orchestration iframe deep links currently assume the local legacy orchestration UI path shape remains stable. If legacy orchestration changes its frontend routing, the `legacy-orchestrationPath` links will need a small update.
- The conversation viewer highlights only directly selected subagents at the top level. Deep nested descendants still open through the correct parent route, but the UI does not yet render a full breadcrumb trail for nested subagent focus.

## Recommended Follow-Ups

- Deprecate `/subagents/{project_path}/{session_id}/{agent_id}` after the frontend and any external clients have moved to the nested conversation route.
- Decide whether `/conversations/{project_path}/{session_id}/subagents/{agent_id}` should become truly parent-validated. If yes, enforce parent-child checks in the application layer; if not, document the contextual parent segment as intentional API shape.
- Add explicit source-event identifiers to the response schemas if downstream consumers need to distinguish provider UUIDs from app-owned persisted entity IDs.
- Normalize context-step message linkage by either storing persisted `conversation_message_id` values or renaming the field to make its source-native semantics unambiguous.
- Add a lightweight route-state utility test around the conversation viewer and orchestration hub if these query-param contracts continue to expand.
