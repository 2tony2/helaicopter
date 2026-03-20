# Conversation Canonical Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace opaque conversation URLs and query-param tab state with immutable canonical conversation refs and path-based tab routes, while redirecting all legacy conversation URLs into the new structure.

**Architecture:** Add backend-owned conversation ref generation and resolution first, persist immutable `route_slug` values in the OLTP conversation store, then switch the Next.js conversation area to a catch-all route that resolves canonical refs and rewrites legacy paths. Keep the existing data-fetch model keyed by `project_path` and `session_id`, but pass `parent_session_id` where live Claude subagent threads still require parent-scoped lookup.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/Alembic, Next.js 16 App Router, React 19, TypeScript 5, SWR, Node test runner, pytest.

---

## File Map

- `python/alembic/versions/20260320_0010_conversation_route_refs.py`
  Add `route_slug` to `conversations`, backfill existing rows, and preserve downgrade safety.
- `python/helaicopter_db/models/oltp.py`
  Persist immutable `route_slug` on `ConversationRecord`.
- `python/helaicopter_db/refresh.py`
  Derive `route_slug` once during refresh and keep it stable on reingest.
- `python/helaicopter_api/ports/app_sqlite.py`
  Surface persisted `route_slug` through historical summary/detail models.
- `python/helaicopter_api/adapters/app_sqlite/store.py`
  Read `route_slug` from SQLite and keep test fixture DDL aligned.
- `python/helaicopter_api/application/conversation_refs.py`
  Central backend helper for slug derivation, `conversation_ref` building, and parsing.
- `python/helaicopter_api/schema/conversations.py`
  Add canonical route fields, embedded conversation-plan canonical link fields, and resolver response contracts.
- `python/helaicopter_api/schema/plans.py`
  Add canonical conversation link data used by plan backlinks.
- `python/helaicopter_api/application/conversations.py`
  Shape canonical route fields on list/detail/DAG/subagent responses, add canonical link fields on embedded conversation plans, and support resolver + parent-aware tab fetches.
- `python/helaicopter_api/application/evaluations.py`
  Accept optional `parent_session_id` when live child-thread evaluations need parent context.
- `python/helaicopter_api/application/plans.py`
  Populate canonical conversation link fields on plan responses.
- `python/helaicopter_api/application/orchestration.py`
  Emit canonical conversation URLs for backend-owned orchestration links.
- `python/helaicopter_api/ports/claude_fs.py`
  Expand the live Claude task-reader contract for parent-aware child-thread task lookup.
- `python/helaicopter_api/adapters/claude_fs/tasks.py`
  Implement the parent-aware live Claude task lookup path.
- `tests/test_claude_fs_adapters.py`
  Verify the low-level Claude file-task adapter still resolves child-thread tasks correctly when `parent_session_id` is supplied.
- `python/helaicopter_api/router/conversations.py`
  Expose `/conversations/by-ref/{conversation_ref}` and optional parent-aware query params.
- `python/helaicopter_api/router/evaluations.py`
  Accept optional `parent_session_id` for child-thread evaluation reads/creates.
- `python/helaicopter_api/router/tasks.py`
  Accept optional `parent_session_id` for child-thread task reads.
- `python/helaicopter_api/application/orchestration.py`
  Emit canonical conversation URLs in backend-generated links.
- `python/helaicopter_api/server/openapi_artifacts.py`
  Add the resolver route to the filtered frontend API surface.
- `python/helaicopter_api/pure/conversation_dag.py`
  Emit canonical conversation paths on DAG nodes.
- `src/lib/types.ts`
  Add `conversationRef`, `routeSlug`, resolver DTOs, canonical link fields on plans/subagents, shared canonical conversation link fields for embedded conversation plans, and nullable DAG node paths for unresolved child threads.
- `src/lib/client/endpoints.ts`
  Add the canonical resolver endpoint and optional `parentSessionId` query params to existing conversation/evaluation/task endpoints.
- `src/lib/client/normalize.ts`
  Normalize canonical route fields, embedded conversation-plan link fields, nullable DAG node paths, and resolver responses.
- `src/hooks/use-conversations.ts`
  Add canonical-ref resolution hooks and optional `parentSessionId` support.
- `src/lib/routes.ts`
  Replace query-param-centric helpers with canonical path builders, legacy translators, and catch-all parsers.
- `src/lib/routes.test.ts`
  Lock canonical parsing, legacy redirect translation, nested-route-to-tab-root behavior, and precedence rules.
- `src/app/conversations/[...segments]/page.tsx`
  Catch-all conversation page that resolves canonical refs, redirects legacy paths, and renders 404 for invalid canonical shapes.
- `src/app/conversations/[...segments]/page.test.ts`
  Verify page-level redirect and `notFound()` behavior for canonical, legacy, and invalid conversation paths.
- `src/lib/server/backend-api.ts`
  Minimal server-side backend fetch helper for route resolution in App Router pages, using uncached requests for live conversation safety.
- `src/app/conversations/[projectPath]/[sessionId]/page.tsx`
  Delete after catch-all route takes over.
- `src/app/conversations/[projectPath]/[sessionId]/subagents/[agentId]/page.tsx`
  Delete after catch-all route handles the legacy nested alias.
- `src/components/conversation/conversation-viewer.tsx`
  Use path segments for tab changes and nested selections.
- `src/components/conversation/conversation-list.tsx`
  Link summaries with `conversationRef`.
- `src/components/conversation/conversation-dag-list.tsx`
  Link DAG list cards with `conversationRef`.
- `src/components/conversation/conversation-dag-view.tsx`
  Disable direct navigation for DAG nodes whose child conversation cannot be resolved to a canonical route.
- `src/components/conversation/conversation-dag-node.tsx`
  Reflect the disabled navigation state for unresolved DAG nodes without pretending they are clickable.
- `src/components/plans/plan-panel.tsx`
  Use canonical conversation backlinks from plan payloads.
- `tests/test_api_database.py`
  Verify migration/backfill and refresh immutability for `route_slug`.
- `tests/test_sqlite_adapters.py`
  Keep DDL fixtures in sync and verify `route_slug` reaches adapter outputs.
- `tests/test_claude_fs_adapters.py`
  Verify low-level parent-aware file-task reads for live child-thread fallback.
- `tests/test_api_conversations.py`
  Verify resolver, canonical fields, redirects, and parent-aware live subagent behavior.
- `tests/test_api_evaluations.py`
  Verify optional `parent_session_id` behavior for live child-thread evaluations.
- `tests/test_api_plans.py`
  Verify canonical conversation link data on plan payloads and embedded conversation plans.
- `tests/test_api_orchestration.py`
  Verify orchestration payloads emit canonical conversation links.
- `src/lib/client/normalize.test.ts`
  Verify canonical route fields normalize correctly.
- `public/openapi/helaicopter-api.json`
- `public/openapi/helaicopter-api.yaml`
- `public/openapi/helaicopter-frontend-app-api.json`
  Regenerated committed OpenAPI artifacts.

### Task 1: Persist immutable conversation route slugs

**Files:**
- Create: `python/alembic/versions/20260320_0010_conversation_route_refs.py`
- Create: `python/helaicopter_api/application/conversation_refs.py`
- Modify: `python/helaicopter_db/models/oltp.py`
- Modify: `python/helaicopter_db/refresh.py`
- Modify: `python/helaicopter_api/ports/app_sqlite.py`
- Modify: `python/helaicopter_api/adapters/app_sqlite/store.py`
- Test: `tests/test_api_database.py`
- Test: `tests/test_sqlite_adapters.py`

- [ ] **Step 1: Write the failing persistence tests**
  Add backend tests that prove:
  - migrated conversations expose a stored `route_slug`
  - Alembic backfill produces the same slug output as `derive_route_slug(...)` for edge-case titles that exercise punctuation collapse, trimming, ASCII fallback, and the `conversation` default
  - refresh backfills `route_slug` from `first_message`
  - a second refresh with a changed `firstMessage` keeps the original `route_slug`
  - adapter summary/detail reads include the new field

- [ ] **Step 2: Add the shared slug helper shape**
  Create `python/helaicopter_api/application/conversation_refs.py` first, even if the initial version only covers slug derivation and ref building:
  ```py
  def derive_route_slug(first_message: str) -> str: ...
  def build_conversation_ref(route_slug: str, provider: str, session_id: str) -> str: ...
  ```
  Match the approved spec exactly:
  - lowercase ASCII
  - non-alphanumeric runs collapse to `-`
  - trim to 80 chars
  - fallback to `conversation`

- [ ] **Step 3: Add `route_slug` to persistence**
  Update:
  - `ConversationRecord` in `python/helaicopter_db/models/oltp.py`
  - the Alembic migration to add and backfill the column
  - `HistoricalConversationSummary` / `HistoricalConversationRecord` in `python/helaicopter_api/ports/app_sqlite.py`
  - adapter queries in `python/helaicopter_api/adapters/app_sqlite/store.py`
  Make the migration backfill call the shared slug helper or a byte-for-byte equivalent slugging routine so persisted backfills and live-derived refs cannot drift.

- [ ] **Step 4: Make refresh immutable**
  In `python/helaicopter_db/refresh.py`, set:
  ```py
  if existing_conversation is None or not conversation.route_slug:
      conversation.route_slug = derive_route_slug(summary["firstMessage"])
  ```
  Never overwrite an existing non-empty `route_slug`.

- [ ] **Step 5: Run the targeted backend tests**
  Run:
  ```bash
  uv run --group dev pytest -q tests/test_api_database.py tests/test_sqlite_adapters.py
  ```
  Expected: PASS, including the new refresh-immutability assertions.

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add python/alembic/versions/20260320_0010_conversation_route_refs.py python/helaicopter_api/application/conversation_refs.py python/helaicopter_db/models/oltp.py python/helaicopter_db/refresh.py python/helaicopter_api/ports/app_sqlite.py python/helaicopter_api/adapters/app_sqlite/store.py tests/test_api_database.py tests/test_sqlite_adapters.py
  git commit -m "feat: persist immutable conversation route slugs"
  ```

### Task 2: Expose canonical refs and the resolver endpoint

**Files:**
- Modify: `python/helaicopter_api/application/conversation_refs.py`
- Modify: `python/helaicopter_api/schema/conversations.py`
- Modify: `python/helaicopter_api/schema/plans.py`
- Modify: `python/helaicopter_api/application/conversations.py`
- Modify: `python/helaicopter_api/application/plans.py`
- Modify: `python/helaicopter_api/router/conversations.py`
- Modify: `python/helaicopter_api/server/openapi_artifacts.py`
- Test: `tests/test_api_conversations.py`
- Test: `tests/test_api_evaluations.py`
- Test: `tests/test_api_plans.py`

- [ ] **Step 1: Write the failing API-contract tests**
  Cover:
  - conversation summaries include `route_slug` and `conversation_ref`
  - conversation detail includes `route_slug` and `conversation_ref`
  - merged live summaries/details also include `route_slug` and `conversation_ref` for non-persisted conversations
  - embedded `ConversationPlanResponse` entries on conversation detail include canonical conversation link fields used by `PlanPanel`
  - child subagents expose `conversation_ref` when resolvable
  - plan responses expose canonical conversation link data
  - `GET /conversations/by-ref/{conversation_ref}` resolves persisted and live conversations by stable provider/session identity even when the incoming slug portion is stale or wrong
  - `GET /conversations/by-ref/{conversation_ref}` returns 404 for an unknown but well-formed ref
  - OpenAPI includes the new resolver path in the frontend surface

- [ ] **Step 2: Add focused backend route-ref helpers**
  Put the parsing and formatting rules in `python/helaicopter_api/application/conversation_refs.py`:
  ```py
  @dataclass(frozen=True)
  class ConversationRouteTarget:
      provider: str
      session_id: str
      route_slug: str
      conversation_ref: str
  ```
  Keep the parse rule explicit in this module:
  - split on the last `--`
  - require a known provider prefix in the suffix
  - treat everything after the provider prefix as the opaque `session_id`
  Keep all string parsing in one place so `application/conversations.py`, `application/plans.py`, and `application/orchestration.py` do not reimplement it.

- [ ] **Step 3: Expand response schemas**
  Add canonical fields to:
  - `ConversationSummaryResponse`
  - `ConversationDetailResponse`
  - `ConversationSubagentResponse`
  - `ConversationPlanResponse` in `python/helaicopter_api/schema/conversations.py`
  - `ConversationDagNodeResponse.path` in `python/helaicopter_api/schema/conversations.py` as `str | None`
  - resolver response schema in `python/helaicopter_api/schema/conversations.py`
  - `PlanSummaryResponse` and `PlanDetailResponse` in `python/helaicopter_api/schema/plans.py`
  This schema expansion makes the nullable DAG path legal in the API contract now; the path-generation behavior itself is implemented and tested in Task 4.

- [ ] **Step 4: Add the resolver route**
  Add a new FastAPI route:
  ```py
  @conversations_router.get("/by-ref/{conversation_ref}")
  async def conversation_by_ref(...)
  ```
  Declare this route before `/{project_path}/{session_id}` in `python/helaicopter_api/router/conversations.py` so FastAPI does not shadow it. Parse the incoming ref, resolve the conversation by stable `provider + session_id`, and always return the current canonical ref built from the persisted `route_slug` rather than requiring an exact incoming slug match. This route should return:
  - `conversation_ref`
  - `route_slug`
  - `project_path`
  - `session_id`
  - `thread_type`
  - `parent_session_id` when needed for live child-thread lookup

- [ ] **Step 5: Shape canonical link fields in plan payloads everywhere**
  Update both `python/helaicopter_api/application/plans.py` and `python/helaicopter_api/application/conversations.py` so:
  - top-level plan payloads carry canonical conversation link data
  - embedded `ConversationPlanResponse` entries carry the same field names
  - `PlanPanel` can consume one shared canonical conversation-link shape regardless of whether it renders a plan page or a conversation-detail plan

- [ ] **Step 6: Run the targeted API tests**
  Run:
  ```bash
  uv run --group dev pytest -q tests/test_api_conversations.py tests/test_api_evaluations.py tests/test_api_plans.py
  npm run api:openapi
  ```
  Expected: PASS, plus updated committed OpenAPI artifacts.

- [ ] **Step 7: Commit**
  Run:
  ```bash
  git add python/helaicopter_api/application/conversation_refs.py python/helaicopter_api/schema/conversations.py python/helaicopter_api/schema/plans.py python/helaicopter_api/application/conversations.py python/helaicopter_api/application/plans.py python/helaicopter_api/router/conversations.py python/helaicopter_api/server/openapi_artifacts.py tests/test_api_conversations.py tests/test_api_evaluations.py tests/test_api_plans.py public/openapi/helaicopter-api.json public/openapi/helaicopter-api.yaml public/openapi/helaicopter-frontend-app-api.json
  git commit -m "feat: add canonical conversation refs to backend contracts"
  ```

### Task 3: Add parent-aware support for live subagent child-thread tabs

**Files:**
- Modify: `python/helaicopter_api/ports/claude_fs.py`
- Modify: `python/helaicopter_api/adapters/claude_fs/tasks.py`
- Modify: `python/helaicopter_api/router/conversations.py`
- Modify: `python/helaicopter_api/router/evaluations.py`
- Modify: `python/helaicopter_api/router/tasks.py`
- Modify: `python/helaicopter_api/application/conversations.py`
- Modify: `python/helaicopter_api/application/evaluations.py`
- Test: `tests/test_api_conversations.py`
- Test: `tests/test_api_evaluations.py`
- Test: `tests/test_claude_fs_adapters.py`

- [ ] **Step 1: Write failing live-subagent tab tests**
  Add tests that prove a canonical child-thread route can still load:
  - detail/messages on `GET /conversations/{project_path}/{session_id}?parent_session_id=...`
  - DAG
  - evaluations read
  - evaluation creation via `POST /conversations/{project_path}/{session_id}/evaluations?parent_session_id=...`
  - tasks
  when only the live Claude fallback can resolve the child transcript through `parent_session_id`.

- [ ] **Step 2: Thread `parent_session_id` through the router layer**
  Accept optional query params on the backend endpoints that power child-thread tabs:
  ```py
  parent_session_id: str | None = Query(default=None)
  ```
  Apply this to:
  - `/conversations/{project_path}/{session_id}`
  - `/conversations/{project_path}/{session_id}/dag`
  - both GET and POST `/conversations/{project_path}/{session_id}/evaluations`
  - `/tasks/{session_id}`

- [ ] **Step 3: Extend the live Claude task reader contract**
  Make the task lookup buildable for child threads by updating the Claude task-reader interface and adapter, for example:
  ```py
  def read_tasks(session_id: SessionId, *, parent_session_id: SessionId | None = None) -> list[ClaudeTaskPayload]: ...
  ```
  Use `parent_session_id` only for the live child-thread fallback path.

- [ ] **Step 4: Preserve direct behavior for persisted and Codex conversations**
  In the application layer, only use `parent_session_id` when the live Claude fallback needs it. Persisted and Codex records should continue to resolve directly by `project_path` + `session_id` for both evaluation reads and evaluation creation.

- [ ] **Step 5: Wire the main detail/messages load explicitly**
  Update the conversation-detail loader in `python/helaicopter_api/application/conversations.py` so the default `/messages` tab path also accepts and uses `parent_session_id` when a live Claude child thread needs parent-scoped lookup.

- [ ] **Step 6: Call out the DAG application path explicitly**
  Update the DAG-loading branch in `python/helaicopter_api/application/conversations.py` so root child-thread DAG fetches also receive `parent_session_id` when the live Claude fallback requires it.

- [ ] **Step 7: Keep the parent-aware branch explicit**
  Use helper signatures like:
  ```py
  def get_tasks(..., session_id: str, parent_session_id: str | None = None) -> TaskListResponse: ...
  ```
  Avoid leaking special-case branching across unrelated code paths.

- [ ] **Step 8: Run the targeted parent-aware tests**
  Run:
  ```bash
  uv run --group dev pytest -q tests/test_api_conversations.py tests/test_api_evaluations.py tests/test_claude_fs_adapters.py
  ```
  Expected: PASS, including the new live child-thread tab coverage and evaluation-creation coverage.

- [ ] **Step 9: Commit**
  Run:
  ```bash
  git add python/helaicopter_api/ports/claude_fs.py python/helaicopter_api/adapters/claude_fs/tasks.py python/helaicopter_api/router/conversations.py python/helaicopter_api/router/evaluations.py python/helaicopter_api/router/tasks.py python/helaicopter_api/application/conversations.py python/helaicopter_api/application/evaluations.py tests/test_api_conversations.py tests/test_api_evaluations.py tests/test_claude_fs_adapters.py
  git commit -m "feat: support canonical child-thread tabs for live subagents"
  ```

### Task 4: Migrate backend-owned link surfaces to canonical conversation URLs

**Files:**
- Modify: `python/helaicopter_api/pure/conversation_dag.py`
- Modify: `python/helaicopter_api/application/orchestration.py`
- Test: `tests/test_api_conversations.py`
- Test: `tests/test_api_orchestration.py`

- [ ] **Step 1: Write the failing link-surface tests**
  Add assertions that:
  - DAG node `path` values use canonical conversation refs for resolvable root and child nodes
  - unresolved child-thread DAG nodes return `path = null` rather than a legacy fallback URL
  - orchestration task/planner links no longer emit `/conversations/{project_path}/{session_id}`

- [ ] **Step 2: Update DAG node path generation**
  In `python/helaicopter_api/pure/conversation_dag.py`, stop rebuilding legacy paths from `project_path` and `session_id`. Use canonical conversation refs from the shaped conversation/subagent payloads instead. If a child conversation cannot be resolved to a canonical ref, keep the node in the DAG but emit `path = None` so the frontend can render it as non-clickable instead of linking to a non-canonical fallback.

- [ ] **Step 3: Update orchestration link generation**
  In `python/helaicopter_api/application/orchestration.py`, replace legacy conversation-path assembly with canonical refs, preserving `None` when the orchestration record has no conversation context.

- [ ] **Step 4: Run the targeted backend link tests**
  Run:
  ```bash
  uv run --group dev pytest -q tests/test_api_conversations.py tests/test_api_orchestration.py
  ```
  Expected: PASS with canonical DAG and orchestration links.

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add python/helaicopter_api/pure/conversation_dag.py python/helaicopter_api/application/orchestration.py tests/test_api_conversations.py tests/test_api_orchestration.py
  git commit -m "feat: emit canonical conversation links from backend surfaces"
  ```

### Task 5: Extend frontend client contracts for canonical routing

**Files:**
- Modify: `src/lib/types.ts`
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/client/mutations.ts`
- Modify: `src/hooks/use-conversations.ts`
- Modify: `src/components/conversation/evaluation-dialog.tsx`
- Test: `src/lib/client/normalize.test.ts`
- Test: `src/lib/client/mutations.test.ts`

- [ ] **Step 1: Write failing frontend contract tests**
  Add coverage for:
  - summary/detail `conversationRef` normalization
  - subagent `conversationRef` normalization
  - DAG node `path` normalization allowing `null` for unresolved child routes
  - embedded `ConversationPlan` canonical conversation link normalization
  - plan canonical conversation link normalization
  - resolver endpoint normalization
  - endpoint builders that append `parentSessionId` only when needed

- [ ] **Step 2: Add the new frontend DTOs**
  Extend `src/lib/types.ts` with focused fields rather than adding `Record<string, unknown>` escape hatches:
  ```ts
  interface ConversationRouteResolution {
    conversationRef: string;
    routeSlug: string;
    projectPath: string;
    sessionId: string;
    threadType: "main" | "subagent";
    parentSessionId?: string;
  }
  ```
  Also add:
  - one shared canonical conversation-link shape that both `ConversationPlan` and `PlanDetail` expose so `PlanPanel` can build links the same way in both contexts
  - `path?: string | null` on DAG nodes so unresolved child routes stay representable without fake links

- [ ] **Step 3: Add canonical endpoint builders**
  In `src/lib/client/endpoints.ts`, add:
  - `conversationByRef(conversationRef: string)`
  - optional `parentSessionId` support for `conversation`, `conversationDag`, `conversationEvaluations`, and `tasks`

- [ ] **Step 4: Thread parent context through evaluation creation**
  Update `src/lib/client/mutations.ts` and `src/components/conversation/evaluation-dialog.tsx` so live child-thread evaluation POSTs include `parentSessionId` whenever the resolved route locator requires it.

- [ ] **Step 5: Keep hooks backward-compatible where practical**
  Update `src/hooks/use-conversations.ts` to accept optional `parentSessionId` without forcing all existing callers to change in the same commit. Add a dedicated resolver hook rather than overloading unrelated hooks.

- [ ] **Step 6: Run the targeted frontend tests**
  Run:
  ```bash
  node --test src/lib/client/normalize.test.ts
  node --test src/lib/client/mutations.test.ts
  ```
  Expected: PASS with the new canonical fields and resolver coverage.

- [ ] **Step 7: Commit**
  Run:
  ```bash
  git add src/lib/types.ts src/lib/client/endpoints.ts src/lib/client/normalize.ts src/lib/client/mutations.ts src/hooks/use-conversations.ts src/components/conversation/evaluation-dialog.tsx src/lib/client/normalize.test.ts src/lib/client/mutations.test.ts
  git commit -m "feat: add canonical conversation routing data to frontend client layer"
  ```

### Task 6: Rewrite route helpers around path segments and legacy translation

**Files:**
- Modify: `src/lib/routes.ts`
- Test: `src/lib/routes.test.ts`

- [ ] **Step 1: Write failing canonical-route tests first**
  Cover:
  - canonical base routes redirecting from `/conversations/<conversationRef>` to `/messages`
  - building `/conversations/<conversationRef>/<tab>`
  - building nested routes for `/messages/<messageId>`, `/plans/<planId>`, and `/subagents/<agentId>`
  - parsing canonical catch-all segments
  - translating legacy query params into canonical targets
  - translating the legacy nested subagent route `/conversations/<projectPath>/<sessionId>/subagents/<agentId>`
  - deterministic precedence for mixed legacy entity params
  - unknown legacy `tab` values falling back to `/messages`
  - `404` treatment for invalid canonical tabs
  - wrong-slug canonical paths redirecting to the resolver’s canonical ref
  - invalid nested `messageId`, `planId`, and `agentId` producing 404 decisions rather than falling back to a tab root

- [ ] **Step 2: Add canonical route builders**
  Replace the old query-param helper shape with segment-based builders such as:
  ```ts
  buildConversationTabRoute(conversationRef, "plans")
  buildConversationMessageRoute(conversationRef, messageId)
  buildConversationPlanRoute(conversationRef, planId)
  buildConversationSubagentTabRoute(parentConversationRef, agentId)
  ```

- [ ] **Step 3: Add a single catch-all parser**
  The parser should return one normalized result type:
  ```ts
  type ConversationRouteParseResult =
    | { kind: "canonical"; conversationRef: string; tab: ConversationDetailTab; ... }
    | { kind: "legacy"; projectPath: string; sessionId: string; ... }
    | { kind: "invalid" };
  ```
  Detection precedence should be explicit:
  - canonical only if the entire segment shape is valid: a parseable `conversationRef`, an optional known tab segment, and an allowed nested-segment count for that tab
  - otherwise legacy if the segment count matches one of the old shapes
  - otherwise invalid

- [ ] **Step 4: Drop nested entity segments when switching tabs**
  Make route-helper behavior deterministic:
  - switching away from `/messages/<messageId>` goes to `/<newTab>`
  - switching away from `/plans/<planId>` goes to `/<newTab>`
  - switching away from `/subagents/<agentId>` goes to `/<newTab>`

- [ ] **Step 5: Run the route tests**
  Run:
  ```bash
  node --test src/lib/routes.test.ts
  ```
  Expected: PASS with canonical, legacy, and invalid-path coverage.

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add src/lib/routes.ts src/lib/routes.test.ts
  git commit -m "feat: add canonical conversation route helpers"
  ```

### Task 7: Replace the conversation detail entrypoints with a catch-all route

**Files:**
- Create: `src/lib/server/backend-api.ts`
- Create: `src/app/conversations/[...segments]/page.tsx`
- Test: `src/app/conversations/[...segments]/page.test.ts`
- Delete: `src/app/conversations/[projectPath]/[sessionId]/page.tsx`
- Delete: `src/app/conversations/[projectPath]/[sessionId]/subagents/[agentId]/page.tsx`

- [ ] **Step 1: Write the page-level route tests first**
  Add `src/app/conversations/[...segments]/page.test.ts` that exercises the actual catch-all page behavior with injected backend-fetch, `redirect`, and `notFound` dependencies. Cover:
  - canonical render paths
  - canonical base redirect to `/messages`
  - wrong-slug redirect to the resolver’s canonical ref
  - resolver 404 for an unknown but well-formed canonical ref mapping to `notFound()`
  - legacy redirects
  - invalid canonical 404s
  - invalid nested entity 404s
  Keep `src/lib/routes.test.ts` as helper-level coverage, but use `page.test.ts` to verify the App Router decision branches themselves.

- [ ] **Step 2: Add a tiny server-side backend fetch helper**
  Create `src/lib/server/backend-api.ts` for route-resolution fetches only:
  ```ts
  export async function requestBackendJson<T>(path: string): Promise<T> { ... }
  ```
  Use `NEXT_PUBLIC_API_BASE_URL` when present, otherwise fall back to `http://127.0.0.1:30000` for the local viewer.
  Make the helper explicitly uncached for live conversations, for example with `cache: "no-store"` or an equivalent force-dynamic setup that prevents stale canonical resolution and stale detail payloads.

- [ ] **Step 3: Implement the catch-all page**
  In `src/app/conversations/[...segments]/page.tsx`:
  - export the page logic through a small factory or injectable helper so `page.test.ts` can drive the real redirect and `notFound()` branches without spinning up Next
  - mark the route dynamic or otherwise disable static caching for this page so live conversations and canonical ref resolution stay fresh
  - parse segments with the new helper
  - for canonical paths, resolve the locator through `/conversations/by-ref/{conversation_ref}`
  - if the resolver returns 404 for a well-formed canonical ref, call `notFound()` instead of redirecting or surfacing a backend error
  - for legacy paths, fetch the existing detail endpoint by `project_path` + `session_id` to obtain `conversationRef` before redirecting
  - redirect `/conversations/<conversationRef>` to `/messages`
  - redirect any valid-but-wrong-slug path to the resolver’s canonical ref
  - redirect legacy paths to the canonical route
  - `notFound()` invalid canonical paths
  - fetch the resolved conversation detail before rendering nested canonical routes and `notFound()` when the requested `messageId`, `planId`, or `agentId` is absent
  - pass the resolved locator into `ConversationViewer`

- [ ] **Step 4: Preserve breadcrumb quality**
  Keep the current readable breadcrumbs by continuing to use `projectDirToDisplayName` plus the resolved session info. The canonical ref should not replace the human breadcrumb labels.

- [ ] **Step 5: Remove the old route files**
  Delete the old nested conversation pages after the catch-all route handles both canonical and legacy shapes, so App Router does not have competing detail-route definitions.

- [ ] **Step 6: Run the route-page verification**
  Run:
  ```bash
  node --test src/app/conversations/[...segments]/page.test.ts
  npm run lint -- src/app/conversations src/lib/server src/lib/routes.ts
  ```
  Expected: PASS with the catch-all page’s redirect and `notFound()` branches covered directly.

- [ ] **Step 7: Commit**
  Run:
  ```bash
  git add src/lib/server/backend-api.ts src/app/conversations/[...segments]/page.tsx src/app/conversations/[...segments]/page.test.ts src/lib/routes.ts src/lib/routes.test.ts
  git rm src/app/conversations/[projectPath]/[sessionId]/page.tsx src/app/conversations/[projectPath]/[sessionId]/subagents/[agentId]/page.tsx
  git commit -m "feat: add canonical catch-all conversation route"
  ```

### Task 8: Move the UI to canonical links and path-based navigation

**Files:**
- Modify: `src/components/conversation/conversation-viewer.tsx`
- Modify: `src/components/conversation/conversation-list.tsx`
- Modify: `src/components/conversation/conversation-dag-list.tsx`
- Modify: `src/components/conversation/conversation-dag-view.tsx`
- Modify: `src/components/conversation/conversation-dag-node.tsx`
- Modify: `src/components/plans/plan-panel.tsx`

- [ ] **Step 1: Write failing link and navigation tests where coverage already exists**
  Extend:
  - `src/lib/routes.test.ts` for viewer navigation outputs
  - `src/lib/client/normalize.test.ts` for plan/subagent canonical link fields
  Do not add a new React test harness unless an existing test cannot express the route behavior.

- [ ] **Step 2: Teach `ConversationViewer` about resolved route identity**
  Update the viewer props to accept:
  - `conversationRef`
  - optional `parentSessionId`
  - canonical initial tab/entity state derived from the catch-all page
  Then replace `router.replace(...?tab=...)` with canonical path helpers.

- [ ] **Step 3: Keep data loads aligned with the resolved locator**
  Use the resolved `parentSessionId` only when the child-thread route needs parent-aware fetches. Root conversations and persisted child conversations should keep the direct data path.

- [ ] **Step 4: Update every link surface**
  Change:
  - `ConversationList` cards to use `conv.conversationRef`
  - `ConversationDagList` cards to use `conversation.conversationRef`
  - subagent child-thread links to use `agent.conversationRef` when present
  - DAG canvas nodes to push `node.path` only when it is present, and show a disabled "route unavailable" state when a child thread is unresolved
  - plan backlinks in `PlanPanel` to use the shared canonical conversation link fields present on both `ConversationPlan` and `PlanDetail`, instead of rebuilding `/conversations/${projectPath}/${sessionId}`

- [ ] **Step 5: Keep parent-tab and child-thread links distinct**
  Preserve both of these behaviors in the UI:
  - parent subagent tab selection -> `/conversations/<parentRef>/subagents/<agentId>`
  - standalone child thread -> `/conversations/<childRef>/messages`

- [ ] **Step 6: Run the targeted frontend tests**
  Run:
  ```bash
  node --test src/lib/routes.test.ts
  node --test src/lib/client/normalize.test.ts
  ```
  Expected: PASS with the canonical link fields and tab-switch behavior.

- [ ] **Step 7: Commit**
  Run:
  ```bash
  git add src/components/conversation/conversation-viewer.tsx src/components/conversation/conversation-list.tsx src/components/conversation/conversation-dag-list.tsx src/components/conversation/conversation-dag-view.tsx src/components/conversation/conversation-dag-node.tsx src/components/plans/plan-panel.tsx src/lib/routes.ts src/lib/routes.test.ts src/lib/client/normalize.ts src/lib/client/normalize.test.ts src/lib/types.ts
  git commit -m "feat: switch conversation UI to canonical routes"
  ```

### Task 9: Final verification and artifact refresh

**Files:**
- Modify: `public/openapi/helaicopter-api.json`
- Modify: `public/openapi/helaicopter-api.yaml`
- Modify: `public/openapi/helaicopter-frontend-app-api.json`

- [ ] **Step 1: Regenerate OpenAPI artifacts**
  Run:
  ```bash
  npm run api:openapi
  ```
  Expected: the committed API snapshots include the resolver route and any new query params.

- [ ] **Step 2: Run backend verification**
  Run:
  ```bash
  uv run --group dev pytest -q tests/test_api_conversations.py tests/test_api_evaluations.py tests/test_api_plans.py tests/test_api_orchestration.py tests/test_api_database.py tests/test_sqlite_adapters.py
  ```
  Expected: PASS

- [ ] **Step 3: Run frontend verification**
  Run:
  ```bash
  node --test src/app/conversations/[...segments]/page.test.ts
  node --test src/lib/routes.test.ts
  node --test src/lib/client/normalize.test.ts
  node --test src/lib/client/mutations.test.ts
  npm run lint
  npm run build
  ```
  Expected: PASS, including canonical-base redirects, wrong-slug redirects, and nested-entity 404 behavior through the App Router catch-all route.

- [ ] **Step 4: Commit**
  Run:
  ```bash
  git add public/openapi/helaicopter-api.json public/openapi/helaicopter-api.yaml public/openapi/helaicopter-frontend-app-api.json
  git commit -m "chore: verify canonical conversation routing rollout"
  ```
