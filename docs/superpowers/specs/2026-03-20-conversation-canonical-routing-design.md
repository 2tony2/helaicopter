# Conversation Canonical Routing Design

## Executive Summary

This design replaces the current conversation URL scheme with a canonical, human-readable route identity and gives every conversation tab its own path. Today the app uses `/conversations/<encoded-project-path>/<sessionId>` plus query params like `?tab=subagents&subagent=...`, which produces opaque URLs and makes most deep links feel incidental rather than first-class.

The new model introduces an immutable public conversation ref shaped as `<route-slug>--<provider>-<session-id>`. All frontend links move to `/conversations/<conversationRef>/<tab>/...`, every primary tab gets a real route segment, and legacy URLs redirect into the canonical shape. The backend remains the source of truth for conversation identity and route resolution so the frontend does not guess or reconstruct URLs from mutable labels.

## Goals

- Make conversation URLs human-readable and structurally consistent.
- Give every primary conversation tab a real route.
- Make nested selections first-class routes where the selection identifies a durable entity.
- Keep the public route identity stable even if displayed titles or labels change later.
- Redirect existing conversation URLs into the canonical route instead of breaking links.
- Keep frontend and backend route generation aligned so lists, DAG nodes, plans, and orchestration surfaces link to the same canonical paths.

## Non-Goals

- Changing the underlying canonical database identity for conversations.
- Redesigning the conversations UI beyond the routing and deep-link model required for this change.
- Removing existing backend APIs keyed by `project_path` and `session_id` in the same slice.
- Adding canonical routes for unrelated top-level app areas.

## Current State

The current route model has three major weaknesses:

- Conversation detail uses `/conversations/<projectPath>/<sessionId>`, where the project segment is URL-safe but not meaningfully readable to a human.
- Most detail state is encoded as query params, especially `tab`, `plan`, `subagent`, and `message`.
- The app already has one nested subagent route, but it immediately redirects back into query-param state instead of acting as a first-class canonical route.

The current implementation spans:

- frontend route helpers in `src/lib/routes.ts`
- conversation page entrypoints in `src/app/conversations/[projectPath]/[sessionId]/...`
- conversation detail state management in `src/components/conversation/conversation-viewer.tsx`
- backend conversation summaries and detail responses in `python/helaicopter_api/application/conversations.py` and `python/helaicopter_api/schema/conversations.py`

The backend already has a stable internal conversation identity, `conversation_id = <provider>:<session_id>`, but that identity is not exposed as the public route identity today.

## Design Decisions

### 1. Canonical public identity is an immutable conversation ref

Every conversation gets a canonical public ref:

`<route-slug>--<provider>-<session-id>`

Examples:

- `review-the-backend-rollout--claude-claude-session-1`
- `compare-caching-strategies--codex-550e8400-e29b-41d4-a716-446655440000`

This ref has two parts:

- `route_slug`: a persisted immutable slug generated once from the conversation's first user-facing title source
- `provider-session-id`: a stable unique key that keeps the route resolvable even when slugs collide or a user edits the slug manually

The combined ref is the public route identity. The slug is for humans. The key is for durability.

### 2. The slug is persisted, not recomputed forever

The user requirement is that the slug be immutable. That is stronger than "usually derived from the same field." To meet that requirement, the OLTP `conversations` table gains a `route_slug` column.

Rules:

- new conversations set `route_slug` once at ingest time
- existing conversations are backfilled in an Alembic migration using the same slugging rules
- refreshes do not rewrite `route_slug` after it has been set
- empty or unusable titles fall back to `conversation`

Persisting the slug avoids future route drift if display labels, title heuristics, or slugification rules change later.

### 3. Every primary tab becomes a path segment

Canonical route shapes:

- `/conversations/<conversationRef>`
- `/conversations/<conversationRef>/messages`
- `/conversations/<conversationRef>/messages/<messageId>`
- `/conversations/<conversationRef>/plans`
- `/conversations/<conversationRef>/plans/<planId>`
- `/conversations/<conversationRef>/evaluations`
- `/conversations/<conversationRef>/failed`
- `/conversations/<conversationRef>/context`
- `/conversations/<conversationRef>/dag`
- `/conversations/<conversationRef>/subagents`
- `/conversations/<conversationRef>/subagents/<agentId>`
- `/conversations/<conversationRef>/tasks`
- `/conversations/<conversationRef>/raw`

Behavior rules:

- `/conversations/<conversationRef>` redirects to `/conversations/<conversationRef>/messages`
- primary tab selection never depends on query params
- durable nested selections use nested path segments
- query params are reserved for non-canonical UI state only

### 4. Legacy conversation URLs redirect into the canonical route

Legacy URLs must continue to work, but only as redirect entrypoints:

- `/conversations/<projectPath>/<sessionId>`
- `/conversations/<projectPath>/<sessionId>?tab=...`
- `/conversations/<projectPath>/<sessionId>/subagents/<agentId>`

Redirect behavior:

- resolve the legacy conversation using the existing `project_path` and `session_id`
- map legacy query-param state into the new route shape
- redirect immediately to the canonical route

Examples:

- `/conversations/-Users-tony-Code-helaicopter/session-1` -> `/conversations/review-the-backend-rollout--claude-session-1/messages`
- `/conversations/-Users-tony-Code-helaicopter/session-1?tab=plans&plan=plan-7` -> `/conversations/review-the-backend-rollout--claude-session-1/plans/plan-7`
- `/conversations/-Users-tony-Code-helaicopter/session-1/subagents/agent-1` -> `/conversations/review-the-backend-rollout--claude-session-1/subagents/agent-1`

### 5. The backend owns route resolution

The frontend should not infer canonical refs from mutable labels or partial data. The backend must expose:

- `route_slug`
- `conversation_ref`

on conversation summary and detail responses.

The backend also adds a resolver API for canonical refs. The resolver returns the conversation locator needed by the frontend route layer:

- `conversation_ref`
- `route_slug`
- `project_path`
- `session_id`
- `thread_type`

The frontend can then resolve a canonical ref once and continue to use the existing data APIs that are keyed by `project_path` and `session_id`.

This keeps the implementation incremental:

- route resolution becomes canonical immediately
- existing detail, DAG, evaluations, and subagent APIs do not need to be duplicated in the same slice

### 6. The Next app uses a catch-all conversation route

The canonical shape `/conversations/<conversationRef>/<tab>` collides structurally with the legacy shape `/conversations/<projectPath>/<sessionId>`. The app-router solution is to replace the current detail route folders with a single catch-all route for conversation detail paths:

- keep `/conversations/page.tsx` for the list page
- add `src/app/conversations/[...segments]/page.tsx` for all non-list conversation paths

The catch-all parser handles:

- canonical routes
- legacy routes
- legacy nested subagent routes

It decides whether to render directly or redirect based on segment shape:

- canonical first segment parses as `<slug>--<provider>-<session-id>`
- canonical second segment is a known tab
- legacy shapes are mapped and redirected

This avoids ambiguous route folder conflicts while preserving old links.

### 7. Route helpers become segment-based

`src/lib/routes.ts` changes from query-param-centric helpers to canonical route builders and parsers:

- build canonical conversation tab routes
- build canonical nested message, plan, and subagent routes
- parse catch-all segments into a normalized conversation route state
- translate legacy query-param state into canonical tab/entity targets

The old helper surface can be retained briefly as compatibility wrappers during the migration, but the canonical helpers should become the primary API used by the frontend.

## Data Flow

### Canonical navigation

1. Conversation lists, DAG nodes, plan backlinks, and other surfaces receive `conversation_ref` from API responses.
2. Links point directly to `/conversations/<conversationRef>/<tab>/...`.
3. The catch-all route parses the canonical path and resolves `conversationRef` through the backend resolver.
4. The page passes the resolved `project_path` and `session_id` into the existing client hooks.
5. The viewer uses canonical route builders for tab changes and nested selection changes.

### Legacy navigation

1. A user visits an old route keyed by `projectPath` and `sessionId`.
2. The catch-all route recognizes the legacy segment shape.
3. The page translates query-param state or legacy nested segments into a canonical tab/entity target.
4. The page resolves the conversation and issues a redirect to the canonical route.

## Component and API Changes

### Backend

- add `route_slug` to the OLTP conversation model and Alembic migration
- add helpers to build and parse `conversation_ref`
- backfill `route_slug` for existing records
- expose `route_slug` and `conversation_ref` on conversation summary/detail schemas
- add a canonical-ref resolver endpoint
- update DAG node `path` generation to use canonical conversation refs
- update any generated conversation links in backend-owned responses, including orchestration links

### Frontend

- replace `[projectPath]/[sessionId]` conversation routes with `[...segments]`
- update conversation page parsing to accept canonical segments and legacy redirect input
- update `ConversationViewer` to navigate with path segments instead of `?tab=...`
- update conversation lists, DAG lists, plan backlinks, and subagent links to use `conversation_ref`
- keep existing data hooks keyed by `projectPath` and `sessionId` after server-side resolution

## Error Handling

- valid key with wrong slug: redirect to canonical slug
- unknown `conversation_ref`: render 404
- invalid canonical tab segment: redirect to `/messages`
- nested entity not found within a valid conversation:
  - `/messages/<messageId>` -> render messages tab with a not-found state or 404 depending on current app preference
  - `/plans/<planId>` -> render plans tab with a not-found state or 404
  - `/subagents/<agentId>` -> render subagents tab with a not-found state or 404

The important rule is consistency: invalid canonical shapes should not silently fall back to arbitrary unrelated tabs.

## Testing Strategy

### Backend tests

- slug generation and fallback behavior
- immutable `route_slug` behavior during refresh
- Alembic migration and backfill behavior
- `conversation_ref` build and parse helpers
- canonical-ref resolver behavior
- summary/detail response shaping includes `conversation_ref`
- DAG node and orchestration link generation emit canonical routes

### Frontend tests

- canonical route builder and parser coverage in `src/lib/routes.test.ts`
- legacy query-param translation into canonical routes
- catch-all route parsing for canonical and legacy inputs
- viewer navigation updates the pathname, not `?tab=...`
- message, plan, and subagent selection links produce nested canonical paths

### Integration coverage

- loading a canonical conversation route reaches the correct conversation
- visiting a legacy conversation URL redirects to the canonical path
- nested subagent legacy URLs redirect to canonical subagent routes
- canonical routes survive browser navigation and deep linking across all primary tabs

## Rollout Notes

- keep legacy backend APIs and frontend redirect handling long enough to preserve external links and bookmarks
- once canonical links are fully adopted, the old route helpers and legacy nested subagent route folder can be removed
- the canonical ref format should be treated as a stable public contract after release

## Open Risks

- the catch-all route parser must be precise enough to distinguish legacy paths from canonical ones without accidental false positives
- the backend resolver becomes a critical part of first-load routing and should remain lightweight
- historic conversations with weak or empty `first_message` values will produce generic slugs, so the stable key portion must remain prominent and reliable
