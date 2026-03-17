# Run: FastAPI Backend Rollout

## Tasks

### api_scaffold
Title: T001 FastAPI App Scaffold

Create the new `python/helaicopter_api/` package and establish the server skeleton. Add `server/main.py`, `server/config.py`, `server/lifespan.py`, `server/openapi.py`, `server/dependencies.py`, `server/route_classes.py`, `router/router.py`, and test scaffolding. Preserve the reference patterns from the local FastAPI example repo, but keep the implementation minimal and local-machine focused.

Acceptance criteria:
- `python/helaicopter_api/` exists with importable package modules
- `server/main.py` exports both `create_app()` and module-level `app`
- router aggregation exists even if most routers are still placeholders
- a basic API smoke test can create the app and hit a health endpoint

Notes:
- do not port demo-only websocket, callback, or webhook features
- keep docs/openapi toggles settings-driven

### api_shared_schemas
Title: T002 Shared API Schemas
Depends on: api_scaffold

Create the initial Pydantic schema layout for common response envelopes, paging/filter parameters where needed, conversation summaries, plan summaries, DAG summaries, analytics payloads, database status, evaluation records, orchestration runs, and subscription settings. Keep these models backend-facing and independent from the existing TypeScript UI type file.

Acceptance criteria:
- `python/helaicopter_api/schema/` is created with focused modules
- common envelope and error response models exist
- each planned router family has at least an initial schema module
- schema imports do not depend on FastAPI router modules

Notes:
- do not mirror the current `src/lib/types.ts` blindly
- optimize for stable backend contracts, not frontend convenience names

### api_bootstrap_and_runtime
Title: T003 Bootstrap, Middleware, And Internal Ops
Depends on: api_scaffold

Implement explicit backend bootstrap wiring for settings, local caches, SQLite handles, subprocess runners, request ID propagation, timing headers, CORS, gzip, and a small internal ops surface. Keep all concrete construction in `bootstrap/` and `server/`, not in route modules.

Acceptance criteria:
- `bootstrap/` assembles the concrete backend services
- request ID and timing middleware are installed and tested
- health/internal ops endpoints exist
- backend startup is explicit and does not rely on hidden module initialization

Notes:
- mounted sub-app is optional; a prefixed internal router is acceptable if it keeps ownership simple
- local-machine assumptions are acceptable for now

### frontend_api_client_base
Title: T004 Frontend API Client Base
Depends on: api_shared_schemas

Create the frontend-side API client seam in `src/lib/client/` and update hooks to depend on that seam instead of directly assuming `src/app/api/*` endpoints will exist forever. Keep this change transport-oriented only; do not cut over feature routes yet.

Acceptance criteria:
- `src/lib/client/` exists with endpoint and fetch helpers
- hooks can be switched over incrementally without large rewrites
- frontend code no longer hardcodes Next route assumptions in reusable client helpers
- no product feature behavior changes yet

Notes:
- keep this task out of backend implementation details
- this task should not delete existing Next API handlers

### claude_artifact_adapters
Title: T005 Claude Filesystem Adapters
Depends on: api_bootstrap_and_runtime

Port or rewrite the Claude filesystem readers into FastAPI-side adapters for conversations, plans, and history. Separate raw file access from processing logic so later application tasks consume capabilities instead of reaching into the filesystem directly.

Acceptance criteria:
- `adapters/claude_fs/` contains focused readers
- raw artifact loading is isolated from higher-level use cases
- adapter tests cover missing files and malformed input behavior
- adapters are wired through ports/bootstrap, not imported directly by routers

Notes:
- preserve current local directory assumptions
- keep file cache ownership explicit

### codex_and_sqlite_adapters
Title: T006 Codex And App SQLite Adapters
Depends on: api_bootstrap_and_runtime

Create adapters for Codex session/plan reads and app-local SQLite access, including historical conversation data, evaluation persistence, prompt storage, and subscription settings storage. Untangle the current Node-side `better-sqlite3` responsibilities into backend-owned Python adapters.

Acceptance criteria:
- `adapters/codex_sqlite/` and `adapters/app_sqlite/` exist
- backend stores can read Codex metadata and app-local tables
- subscription, prompt, and evaluation persistence are no longer tied to Node runtime code
- adapter tests cover missing DB files and minimal happy paths

Notes:
- keep store contracts focused on capabilities, not table-by-table wrappers
- do not introduce a generic service locator

### conversation_read_api
Title: T007 Conversations, Projects, History, And Tasks API
Depends on: claude_artifact_adapters, codex_and_sqlite_adapters, api_shared_schemas

Implement the read-oriented conversation API surface in FastAPI, including conversation summaries, detail fetches, project lists, history, and task lists. Use application modules plus ports/adapters instead of direct router-level data access.

Acceptance criteria:
- conversation, project, history, and task routers exist and are tested
- the new endpoints return stable schema-based responses
- application modules own orchestration, not route files
- backend reads work for both Claude and Codex data sources

Notes:
- keep route modules thin
- avoid frontend-specific response shaping in the backend if it hides real data semantics

### plans_api
Title: T008 Plans API
Depends on: claude_artifact_adapters, codex_and_sqlite_adapters, api_shared_schemas

Implement plan listing and plan detail endpoints in FastAPI, backed by the new adapters and schema modules. Preserve provider distinctions and preview/detail behavior.

Acceptance criteria:
- plans router exists with list and detail coverage
- application module encapsulates plan loading and preview shaping
- backend handles both Claude and Codex plan sources
- endpoint tests cover missing slug behavior

Notes:
- keep plan-specific parsing close to the backend, not the frontend

### dags_api
Title: T009 Conversation DAG API
Depends on: conversation_read_api, api_shared_schemas

Port the DAG summary and detail API surface to FastAPI. Reuse or rewrite the deterministic DAG-building logic so it lives in backend pure/application modules, not inside frontend code or route wrappers.

Acceptance criteria:
- DAG list and detail endpoints exist
- DAG layout/building logic is owned by backend modules
- endpoint tests cover filter and detail behavior
- no router directly manipulates raw DAG graph structures beyond response mapping

Notes:
- keep graph-building logic deterministic and testable
- prefer pure helper modules over framework-shaped code

### analytics_core
Title: T010 Analytics Core Port
Depends on: claude_artifact_adapters, codex_and_sqlite_adapters, api_shared_schemas

Implement the backend analytics core: time windows, pricing integration, provider splits, and aggregation logic. The goal is to move the real analytics computation out of the Node server libraries and into the Python backend in a testable form.

Acceptance criteria:
- analytics computation lives in backend `pure/` and `application/` modules
- provider/day filtering is explicit and tested
- pricing and token attribution behavior are preserved or documented when changed
- no FastAPI route file contains analytics math

Notes:
- keep current behavior compatibility where feasible
- document any intentional response-shape or calculation changes

### analytics_api
Title: T011 Analytics API
Depends on: analytics_core

Expose the analytics core through a FastAPI router with stable request parameters and typed responses. Support the current dashboard use cases without carrying over the old backend-selector pattern.

Acceptance criteria:
- analytics router exists and is tested
- days/provider filters are supported
- response schemas are explicit
- there is no fake backend registry or selector abstraction

Notes:
- comparison/debug modes can be deferred if they block the core migration

### database_ops_api
Title: T012 Database Status And Refresh API
Depends on: api_bootstrap_and_runtime, codex_and_sqlite_adapters

Implement database status and refresh endpoints in FastAPI by delegating to the existing Python database package where appropriate. Treat refresh as a backend-owned capability rather than a Node route shelling out to Python.

Acceptance criteria:
- database status endpoint exists in FastAPI
- refresh trigger endpoint exists in FastAPI
- cache invalidation behavior is explicit on the backend side
- endpoint tests cover success and failure reporting

Notes:
- job semantics are acceptable here if synchronous refresh is too coarse
- do not re-implement the full refresh pipeline inside the route module

### subscriptions_api
Title: T013 Subscription Settings API
Depends on: codex_and_sqlite_adapters, api_shared_schemas

Implement subscription settings reads and updates in FastAPI, backed by the new app SQLite adapters. Preserve the current product behavior while moving persistence ownership to Python.

Acceptance criteria:
- subscription settings router exists with get/update coverage
- the persistence logic is backend-owned
- request and response models are explicit
- tests cover validation and update behavior

Notes:
- keep this task separate from evaluation prompt/evaluation job work

### evaluation_prompts_api
Title: T014 Evaluation Prompt API
Depends on: codex_and_sqlite_adapters, api_shared_schemas

Implement evaluation prompt management in FastAPI, including listing, creating, and updating prompts. Separate prompt persistence from evaluation execution.

Acceptance criteria:
- evaluation prompt router exists and is tested
- prompt store logic is isolated from evaluation job execution
- default prompt seeding/lookup behavior is explicit
- route handlers stay thin

Notes:
- do not couple prompt CRUD to the conversation evaluation endpoint

### evaluation_jobs_api
Title: T015 Evaluation Job API
Depends on: conversation_read_api, evaluation_prompts_api, api_bootstrap_and_runtime

Implement evaluation creation and listing endpoints in FastAPI, backed by local subprocess runners and persistence stores. Treat evaluations as backend jobs and keep subprocess ownership explicit.

Acceptance criteria:
- evaluation create/list endpoints exist and are tested
- local CLI subprocess execution is hidden behind an adapter/runner port
- evaluation records persist status and outputs
- job orchestration lives outside the route module

Notes:
- local-machine subprocess execution is acceptable for v1
- keep the API synchronous on submission and asynchronous in effect

### orchestration_api
Title: T016 OATS Run Summary API
Depends on: api_bootstrap_and_runtime, api_shared_schemas

Implement the FastAPI endpoint for orchestration run summaries, backed by a focused adapter for local OATS artifacts or persisted run metadata. Preserve the current orchestration dashboard use case without dragging the frontend into file parsing details.

Acceptance criteria:
- orchestration router exists and is tested
- application code owns summary shaping
- local oats runtime data access is adapter-backed
- route handlers contain no direct artifact parsing logic

Notes:
- keep this task scoped to summary/list behavior, not live task control

### frontend_read_cutover
Title: T017 Frontend Read Endpoint Cutover
Depends on: frontend_api_client_base, conversation_read_api, plans_api, dags_api, analytics_api, orchestration_api

Cut the frontend over from Next API routes to the FastAPI backend for all read-only surfaces: conversations, plans, dags, analytics, projects, history, tasks, and orchestration. Update hooks and pages, but avoid deleting old route handlers until the cutover is complete.

Acceptance criteria:
- frontend hooks/pages fetch from the FastAPI client seam
- read-only pages work without depending on Next API handlers
- no feature regressions are introduced in the primary UI flows
- frontend code no longer imports server-only Node backend helpers

Notes:
- keep the migration reversible until the old Next routes are removed
- favor narrow hook/page edits over sweeping UI rewrites

### frontend_mutation_cutover
Title: T018 Frontend Mutation Cutover
Depends on: frontend_api_client_base, database_ops_api, subscriptions_api, evaluation_jobs_api

Cut the frontend over to FastAPI for mutable and job-style operations: database refresh, subscription settings, evaluation prompt management, and evaluation creation/listing. Preserve the current UX while moving backend ownership fully to FastAPI.

Acceptance criteria:
- mutation flows call the FastAPI backend
- refresh, prompt, subscription, and evaluation UI flows still work
- the frontend no longer depends on Next API handlers for these operations
- tests or smoke checks cover the main mutation paths

Notes:
- keep job polling/list refresh behavior explicit in the frontend

### remove_next_api_surface
Title: T019 Remove Next API Backend Surface
Depends on: frontend_read_cutover, frontend_mutation_cutover

Delete the superseded `src/app/api/*` backend routes and the Node-side backend modules that are no longer needed after the FastAPI cutover. Leave only frontend-focused code in `src/` and document any intentionally retained compatibility shims.

Acceptance criteria:
- obsolete Next API route handlers are removed
- dead Node backend modules are removed or clearly quarantined
- frontend builds and tests no longer depend on the old backend path
- repository structure now matches the planned frontend/backend split

Notes:
- keep any temporary compatibility shim small and explicitly documented
- do not delete code that is still used by the frontend at runtime

### verification_and_docs
Title: T020 Verification, Runbooks, And Migration Docs
Depends on: remove_next_api_surface

Finish the migration with verification, runbooks, and developer documentation. Update the README, document how to run the FastAPI backend locally, explain the backend/frontend split, and add any final test or build coverage needed for confidence.

Acceptance criteria:
- README and backend run instructions are updated
- local developer workflow for Next + FastAPI is documented
- final validation includes lint, pytest, and build coverage
- the migration plan/results are captured in repo docs

Validation override:
- npm run lint
- npm run build
- uv run --group dev pytest -q

Notes:
- document any known gaps that are intentionally deferred
