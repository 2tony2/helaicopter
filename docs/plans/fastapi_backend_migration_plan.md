# FastAPI Backend Migration Plan

## Goal

Move `helaicopter` from a mixed `Next route handlers + Node server libraries + Python scripts` backend shape to a `Next frontend + FastAPI backend + existing Python packages` shape.

The desired steady state is:

- `src/` is frontend-only.
- `python/helaicopter_api/` is the primary API host.
- `python/helaicopter_db/` remains the database refresh/export package.
- `python/oats/` remains the orchestration runner used to plan and execute the migration itself.

## Safety Setup

Use these workspaces:

- Main-line clean clone: `/Users/tony/Code/helaicopter-main`
- Worktree root: `/Users/tony/Code/helaicopter-worktrees`
- Active planning worktree: `/Users/tony/Code/helaicopter-worktrees/fastapi-migration-plan`
- Current OATS snapshot branch on remote: `codex/oats-current-state`

Important note:

- The current `oats` config model supports `repo.worktree_dir`, but the present implementation does not yet actively create or manage task worktrees from that setting.
- Safety for this rollout therefore comes from running `oats` inside the dedicated planning worktree above, plus conservative git settings in `.oats/config.toml`.

## Architecture Target

### Frontend

- Keep `Next.js` for pages, components, hooks, and browser data fetching.
- Remove the long-term `src/app/api/*` backend surface after FastAPI cutover.
- Replace server-side local data access in `src/lib/*` with a frontend API client.

### Backend

Create `python/helaicopter_api/` with these top-level areas:

- `server/`: app factory, config, lifespan, dependencies, middleware, OpenAPI wiring
- `router/`: FastAPI route modules only
- `schema/`: Pydantic request/response models
- `application/`: use-case modules
- `ports/`: real external capability contracts
- `adapters/`: filesystem, SQLite, subprocess, cache, and oats integrations
- `bootstrap/`: concrete service assembly
- `pure/`: deterministic logic ported or rewritten from current TypeScript logic

### Existing Python Packages

- `python/helaicopter_db/` stays the owner of refresh/export/migration behavior.
- `python/oats/` stays the owner of planning and task/PR orchestration.

## Migration Principles

- Do not introduce a DI container.
- Keep FastAPI routes thin.
- Keep `application/` independent of FastAPI types.
- Keep file system, SQLite, and subprocess code inside `adapters/`.
- Prefer explicit bootstrap wiring over module-level singletons.
- Preserve local-machine assumptions for now; do not optimize for remote deployment yet.
- Treat `evaluations` and `database refresh` as job-style backend capabilities.

## Phase Plan

### Phase 1: Server foundation

Establish the FastAPI app skeleton, config, schemas, bootstrap, runtime notes, and frontend API client seam without cutting over any product behavior yet.

### Phase 2: Read-only API surface

Port read-heavy backend capabilities first:

- conversations
- projects
- history
- tasks
- plans
- DAGs
- analytics
- orchestration run summaries

### Phase 3: Mutable and long-running operations

Port the endpoints that manage local state or jobs:

- database status/refresh
- subscription settings
- evaluation prompts
- evaluation creation and status

### Phase 4: Frontend cutover

Switch the React hooks and pages to the FastAPI backend and remove direct dependency on Next route handlers.

### Phase 5: Cleanup and verification

Delete the old Next API surface, trim Node-only backend code that is no longer needed, and verify the new split end-to-end.

## Task Design Rules For OATS

The companion run spec uses 20 tasks with these goals:

- keep file ownership narrow enough for parallel work
- make dependencies explicit instead of implied
- separate backend foundation from feature ports
- keep frontend cutover late enough that backend contracts stabilize first

When a task edits one of these directories, it should avoid also editing another task's main ownership area unless the prompt explicitly says so:

- `python/helaicopter_api/server/`
- `python/helaicopter_api/router/`
- `python/helaicopter_api/schema/`
- `python/helaicopter_api/application/`
- `python/helaicopter_api/ports/`
- `python/helaicopter_api/adapters/`
- `src/hooks/`
- `src/lib/client/`
- `src/app/`

## Validation Strategy

Baseline validation during rollout:

- `npm run lint`
- `uv run --group dev pytest -q`

Final verification should also include:

- `npm run build`
- FastAPI endpoint tests for all migrated surfaces
- one frontend pass against the FastAPI backend

## Suggested Execution Rhythm

1. Review the generated OATS plan.
2. Run tasks in small batches, respecting dependencies.
3. Keep `auto_push` and PR automation disabled until the first backend foundation slice settles.
4. Re-enable automation only once the FastAPI app skeleton and frontend client seam are stable.

## Run Commands

From the planning worktree:

```bash
cd /Users/tony/Code/helaicopter-worktrees/fastapi-migration-plan
uv run oats plan examples/fastapi_backend_rollout.md
uv run oats pr-plan examples/fastapi_backend_rollout.md
uv run oats run examples/fastapi_backend_rollout.md
```

## Expected Outcome

At the end of this rollout:

- `helaicopter` uses FastAPI as the backend.
- Next is reduced to frontend concerns.
- backend composition becomes explicit and inspectable.
- the migration itself is managed through isolated work in the dedicated planning worktree.
