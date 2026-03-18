# Prefect-Native Oats Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Oats' local runtime orchestration with a Prefect-native control plane, keep Oats as a thin Markdown-first compiler/CLI, and surface Prefect state throughout Helaicopter.

**Architecture:** Oats will parse the existing Markdown run specs and `.oats/config.toml`, normalize them into a canonical run-definition model, and compile that model into Prefect deployments and flow runs. The self-hosted Prefect control plane runs locally via Docker Compose for server services and `launchd` + `caffeinate` for the macOS worker, while Helaicopter proxies Prefect's REST API and joins it with repo-local Oats metadata.

**Tech Stack:** Python 3.13, Prefect 3, FastAPI, Next.js 16, Postgres, Redis, Docker Compose, launchd, node:test + tsx, pytest.

---

## File Structure Map

### Existing files to modify

- `pyproject.toml`
- `.oats/config.toml` (only if repo config defaults need explicit Prefect-aware comments or guardrails; avoid behavioral churn)
- `python/oats/cli.py`
- `python/oats/parser.py`
- `python/oats/models.py`
- `python/oats/planner.py`
- `python/oats/pr.py`
- `python/helaicopter_api/bootstrap/services.py`
- `python/helaicopter_api/server/config.py`
- `python/helaicopter_api/router/router.py`
- `src/lib/client/endpoints.ts`
- `src/lib/client/normalize.ts`
- `src/lib/types.ts`
- `src/hooks/use-conversations.ts`
- `src/components/orchestration/orchestration-hub.tsx`
- `src/components/orchestration/overnight-oats-panel.tsx`
- `src/app/orchestration/page.tsx`

### New Oats files

- `python/oats/run_definition.py`
- `python/oats/run_definition_loader.py`
- `python/oats/prefect/__init__.py`
- `python/oats/prefect/models.py`
- `python/oats/prefect/settings.py`
- `python/oats/prefect/client.py`
- `python/oats/prefect/compiler.py`
- `python/oats/prefect/deployments.py`
- `python/oats/prefect/flows.py`
- `python/oats/prefect/tasks.py`
- `python/oats/prefect/worktree.py`
- `python/oats/prefect/artifacts.py`

### New backend files

- `python/helaicopter_api/ports/prefect.py`
- `python/helaicopter_api/adapters/prefect_http.py`
- `python/helaicopter_api/application/prefect_orchestration.py`
- `python/helaicopter_api/schema/prefect_orchestration.py`
- `python/helaicopter_api/router/prefect_orchestration.py`

### New ops and docs files

- `ops/prefect/docker-compose.yml`
- `ops/prefect/.env.example`
- `ops/launchd/com.helaicopter.prefect-worker.plist.template`
- `ops/scripts/prefect-worker.sh`
- `docs/prefect-local-ops.md`
- `docs/oats-prefect-cutover.md`

### New tests

- `tests/oats/test_prefect_settings.py`
- `tests/oats/test_launchd_assets.py`
- `tests/oats/test_run_definition_loader.py`
- `tests/oats/test_prefect_compiler.py`
- `tests/oats/test_prefect_deployments.py`
- `tests/oats/test_prefect_flows.py`
- `tests/oats/test_prefect_worktree.py`
- `tests/test_api_prefect_orchestration.py`
- `src/lib/client/prefect-normalize.test.ts`

## Sequencing Rules

- Do not start Prefect runtime work before the Markdown-first canonical run-definition boundary exists.
- Do not cut over the orchestration dashboard until the backend Prefect proxy exists.
- Keep Markdown input as the only supported run-definition input for this plan.
- Keep schedule, queue, and work-pool defaults in `.oats/config.toml` plus deploy-time CLI overrides; do not put those fields into Markdown v1.
- Treat validation defaults, retry, timeout, and branch/worktree execution defaults as repo-config or CLI-driven in v1; do not invent new Markdown syntax for them.
- Use one shared Prefect flow implementation fed by compiled runtime payloads; do not generate per-spec flow modules.
- Keep the worker on the host for the first rollout.
- Preserve the current `.oats/config.toml` discovery behavior unless there is a strong reason to change it.
- Keep legacy `.oats/runtime/` and `.oats/runs/` history readable in Helaicopter during the cutover; no historical backfill into Prefect is required.
- Treat Prefect-native retry/rerun as the only v1 resume path; local artifact checkpoints are not a second orchestration engine.
- Treat live Prefect-backed backend endpoints as the source of truth for the Helaicopter dashboard; `oats sync` only refreshes supplementary local metadata.

## Task 1: Prefect Local Platform Foundation

**Files:**
- Modify: `pyproject.toml`
- Modify: `.oats/config.toml`
- Modify: `python/oats/models.py`
- Create: `python/oats/prefect/settings.py`
- Create: `ops/prefect/docker-compose.yml`
- Create: `ops/prefect/.env.example`
- Create: `tests/oats/test_prefect_settings.py`

- [ ] **Step 1: Write the failing settings tests**

Create `tests/oats/test_prefect_settings.py` covering:
- env parsing for Prefect API base URL
- default work-pool and queue names
- default tags plus default task retry/timeout values
- default validation-command fallback surface needed by the canonical loader/runtime
- reuse of existing `[validation]`, `[git]`, and `[repo]` config sections alongside the new `[prefect]` section
- repo-config parsing for Prefect schedule/routing defaults
- v1 cron schedule parsing with timezone
- Compose file path helpers

- [ ] **Step 2: Run the new test to verify it fails**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_settings.py`
Expected: FAIL because `oats.prefect.settings` does not exist yet.

- [ ] **Step 3: Add the runtime dependency and settings module**

Update `pyproject.toml`, extend `.oats/config.toml` with a new `[prefect]` section while reusing the existing `[validation]`, `[git]`, and `[repo]` sections, update `python/oats/models.py` for the new Prefect config surface, and create `python/oats/prefect/settings.py` with a focused settings object similar to:

```python
class PrefectSettings(BaseModel):
    api_url: str
    work_pool: str = "local-macos"
    default_queue: str = "scheduled"
    default_tags: list[str] = []
    default_validation_commands: list[str] = []
    default_task_retry_count: int = 0
    default_task_timeout_seconds: int | None = None
    default_schedule_enabled: bool = True
    default_schedule_cron: str | None = None
    default_schedule_timezone: str = "Europe/Amsterdam"
    compose_file: Path
    env_example_file: Path
```

- [ ] **Step 4: Add the Compose assets**

Create `ops/prefect/docker-compose.yml` and `ops/prefect/.env.example` for:
- `postgres`
- `redis`
- `prefect-server`
- `prefect-services`

Do not add the worker container in v1.

- [ ] **Step 5: Re-run validation**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_settings.py`
Run: `docker compose -f ops/prefect/docker-compose.yml config >/dev/null`
Expected: tests pass and Compose config exits 0.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .oats/config.toml python/oats/models.py python/oats/prefect/settings.py ops/prefect/docker-compose.yml ops/prefect/.env.example tests/oats/test_prefect_settings.py
git commit -m "feat: add prefect local platform foundation"
```

## Task 2: launchd Worker and Local Ops Assets

**Files:**
- Create: `ops/launchd/com.helaicopter.prefect-worker.plist.template`
- Create: `ops/scripts/prefect-worker.sh`
- Create: `docs/prefect-local-ops.md`
- Create: `tests/oats/test_launchd_assets.py`

- [ ] **Step 1: Write failing tests for launchd asset rendering**

Create `tests/oats/test_launchd_assets.py` to assert:
- the plist template references the worker wrapper script
- the wrapper invokes `caffeinate`
- the wrapper bootstraps or starts the Prefect worker against the configured work pool using `--type process`

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --group dev pytest -q tests/oats/test_launchd_assets.py`
Expected: FAIL because the assets do not exist yet.

- [ ] **Step 3: Implement the worker wrapper script**

Create `ops/scripts/prefect-worker.sh` that:
- exports any required local env vars
- runs `caffeinate`
- ensures the work pool exists, or starts the worker with `--type process` so the pool can be created safely
- starts `prefect worker start --pool local-macos --type process`

- [ ] **Step 4: Add the launchd template and runbook**

Document load/unload/log paths in `docs/prefect-local-ops.md` and create a `.plist.template` that points at the wrapper script rather than hard-coding machine-local paths directly into docs. Include an explicit work-pool bootstrap path in the runbook.

- [ ] **Step 5: Validate assets**

Run: `uv run --group dev pytest -q tests/oats/test_launchd_assets.py`
Run: `plutil -lint ops/launchd/com.helaicopter.prefect-worker.plist.template`
Expected: tests pass and the plist validates.

- [ ] **Step 6: Commit**

```bash
git add ops/launchd/com.helaicopter.prefect-worker.plist.template ops/scripts/prefect-worker.sh docs/prefect-local-ops.md tests/oats/test_launchd_assets.py
git commit -m "feat: add launchd worker assets"
```

## Task 3: Markdown-First Canonical Run Definition Layer

**Files:**
- Create: `python/oats/run_definition.py`
- Create: `python/oats/run_definition_loader.py`
- Modify: `python/oats/parser.py`
- Modify: `python/oats/models.py`
- Create: `tests/oats/test_run_definition_loader.py`

- [ ] **Step 1: Write failing normalization tests**

Create `tests/oats/test_run_definition_loader.py` covering:
- loading an existing Markdown run spec from `examples/`
- translating it into a canonical task graph
- preserving the repo-relative `source_path` needed for deterministic deployment identity
- preserving acceptance criteria, notes, and validation overrides
- attaching normalized repo-execution, retry/timeout, routing, and display metadata from repo config
- reusing existing `[validation]`, `[git]`, and `[repo]` sections instead of duplicating those defaults under Prefect-specific keys
- rejecting non-Markdown inputs for this rollout

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest -q tests/oats/test_run_definition_loader.py`
Expected: FAIL because the canonical run-definition layer does not exist.

- [ ] **Step 3: Implement the canonical models**

Create `python/oats/run_definition.py` with models in the shape:

```python
class CanonicalTaskDefinition(BaseModel):
    task_id: str
    title: str
    prompt: str
    depends_on: list[str] = []
    acceptance_criteria: list[str] = []
    notes: list[str] = []
    validation_commands: list[str] = []
    retry_count: int = 0
    timeout_seconds: int | None = None

class CanonicalDeploymentRouting(BaseModel):
    work_pool: str
    queue: str
    tags: list[str] = []
    schedule_enabled: bool = False
    schedule_cron: str | None = None
    schedule_timezone: str | None = None

class CanonicalRepoExecutionHints(BaseModel):
    worktree_root: PurePosixPath = PurePosixPath(".oats-worktrees")
    integration_branch_template: str | None = None
    task_branch_template: str | None = None

class CanonicalDisplayMetadata(BaseModel):
    run_slug: str
    source_label: str

class CanonicalRunDefinition(BaseModel):
    title: str
    source_path: PurePosixPath
    repo_root: Path
    tasks: list[CanonicalTaskDefinition]
    deployment_routing: CanonicalDeploymentRouting
    repo_execution_hints: CanonicalRepoExecutionHints
    display_metadata: CanonicalDisplayMetadata
```

- [ ] **Step 4: Implement the Markdown loader**

Create `python/oats/run_definition_loader.py` so the canonical loader wraps the current Markdown parser behavior, explicitly errors on unsupported non-Markdown inputs, preserves a repo-relative POSIX `source_path` for deployment identity while still being able to resolve the absolute file on disk for parsing, and normalizes execution/display defaults by merging the Markdown graph with `[validation]`, `[git]`, `[repo]`, and `[prefect]` config inputs.

- [ ] **Step 5: Update parser/model boundaries only as needed**

Keep `python/oats/parser.py` focused on Markdown parsing. Do not turn it into a Prefect module.

- [ ] **Step 6: Validate**

Run: `uv run --group dev pytest -q tests/oats/test_run_definition_loader.py tests/test_parser.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python/oats/run_definition.py python/oats/run_definition_loader.py python/oats/parser.py python/oats/models.py tests/oats/test_run_definition_loader.py tests/test_parser.py
git commit -m "feat: add markdown-first canonical run definition"
```

## Task 4: Prefect Compiler and Deployment Payload Builder

**Files:**
- Create: `python/oats/prefect/models.py`
- Create: `python/oats/prefect/compiler.py`
- Create: `tests/oats/test_prefect_compiler.py`

- [ ] **Step 1: Write failing compiler tests**

Create `tests/oats/test_prefect_compiler.py` covering:
- canonical run-definition to Prefect graph translation
- dependency preservation
- tag/queue/work-pool mapping from repo config plus deploy-time overrides
- cron schedule translation from repo config/CLI override into deployment payloads
- default tags, validation defaults, retry, and timeout entering the compiled payload from repo config and overrides
- deterministic deployment key/name derived from the repo-relative run-spec path
- deterministic deployment naming
- stable shared-flow entrypoint reference carried in the compiled deployment spec

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_compiler.py`
Expected: FAIL because the compiler does not exist.

- [ ] **Step 3: Implement Prefect-facing models**

Create `python/oats/prefect/models.py` for deployment payloads, task graph metadata, tags, run parameters, and an explicit compile-overrides model for pool, queue, tags, schedule, and timeout inputs. Keep these models separate from the canonical input models.

- [ ] **Step 4: Implement the compiler**

Create `python/oats/prefect/compiler.py` with a public function like:

```python
def compile_run_definition(
    run_definition: CanonicalRunDefinition,
    repo_config: RepoConfig,
    repo_root: Path,
    overrides: PrefectCompileOverrides | None = None,
) -> PrefectDeploymentSpec:
    ...
```

The compiler must not generate bespoke Python files per run.
It must also merge routing defaults from `.oats/config.toml` without pushing those concerns into Markdown, preserve the repo-relative source path as the stable deployment key, and emit a stable shared-flow entrypoint reference that Task 5 can register before Task 6 fills in the full runtime behavior.

- [ ] **Step 5: Validate**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_compiler.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add python/oats/prefect/models.py python/oats/prefect/compiler.py tests/oats/test_prefect_compiler.py
git commit -m "feat: add prefect compiler"
```

## Task 5: Prefect Client, Deployment Registration, and Thin CLI Commands

**Files:**
- Create: `python/oats/prefect/client.py`
- Create: `python/oats/prefect/deployments.py`
- Create: `python/oats/prefect/artifacts.py`
- Create: `python/oats/prefect/flows.py`
- Modify: `python/oats/cli.py`
- Create: `tests/oats/test_prefect_deployments.py`

- [ ] **Step 1: Write failing deployment/CLI tests**

Create `tests/oats/test_prefect_deployments.py` covering:
- deployment upsert behavior
- triggering from an existing deployment identifier
- manual run trigger behavior from a run-spec path with implicit deployment upsert
- CLI command wiring for `deploy`, `trigger`, `inspect`, and `sync`
- schedule upsert behavior for the v1 one-cron-per-deployment model
- `oats inspect` and `oats sync` contract behavior
- one-way local artifact/linkage metadata refresh
- `oats sync` not being required for live dashboard/backend Prefect reads
- registration against the stable shared-flow entrypoint contract from Task 4
- explicit use of Markdown run specs as the CLI input path

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_deployments.py`
Expected: FAIL because the Prefect client/deployment layer is missing.

- [ ] **Step 3: Implement the HTTP client**

Create `python/oats/prefect/client.py` as a focused wrapper around Prefect's API surface needed for:
- deployment upsert
- flow-run creation
- deployment lookup
- work-pool lookup
- flow-run status inspection

- [ ] **Step 4: Implement deployment registration**

Create `python/oats/prefect/deployments.py` to convert compiled specs into Prefect deployment requests, including schedule creation/upsert for the v1 cron schedule model. Create `python/oats/prefect/artifacts.py` to hold normalized run-definition snapshots, deployment/run linkage metadata, git/worktree metadata, last-seen task summaries, and one-way sync helpers used by `oats inspect` and `oats sync`. Create `python/oats/prefect/flows.py` with a minimal shared Prefect flow entrypoint that matches the compiler's stable entrypoint reference so deployment registration has a concrete target before the richer runtime lands in Task 6.

- [ ] **Step 5: Rework the CLI surface**

Modify `python/oats/cli.py` so new commands route through the Prefect-backed compiler/client path:
- `oats deploy`
- `oats trigger`
- `oats inspect`
- `oats sync`

Define the v1 override surface explicitly:
- `oats deploy <run-spec> [--pool ...] [--queue ...] [--tag ...] [--schedule-cron ...] [--schedule-timezone ...] [--no-schedule] [--timeout-seconds ...]`
- `oats trigger <run-spec>` for compile-plus-upsert-plus-trigger
- `oats trigger --deployment <deployment-key>` for triggering an existing deployment directly

Keep the old local runtime commands available until Task 10, but mark them as legacy in help text.
For v1, `oats trigger <run-spec>` must compile the Markdown, upsert the deployment, and then create the flow run.
For v1, `oats inspect` must read deployment/run state from Prefect, and `oats sync` must perform one-way metadata reconciliation from Prefect into local `.oats/` artifacts.
Do not make the live backend/frontend path depend on `oats sync`.

- [ ] **Step 6: Validate**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_deployments.py`
Run: `uv run oats --help`
Expected: tests pass and CLI help includes the new Prefect-backed commands.

- [ ] **Step 7: Commit**

```bash
git add python/oats/prefect/client.py python/oats/prefect/deployments.py python/oats/prefect/artifacts.py python/oats/prefect/flows.py python/oats/cli.py tests/oats/test_prefect_deployments.py
git commit -m "feat: add prefect deployment cli"
```

## Task 6: Prefect-Native Flow Runtime and Artifact Checkpoints

**Files:**
- Modify: `python/oats/prefect/flows.py`
- Create: `python/oats/prefect/tasks.py`
- Create: `tests/oats/test_prefect_flows.py`

- [ ] **Step 1: Write failing flow-runtime tests**

Create `tests/oats/test_prefect_flows.py` covering:
- compiled task graph execution order
- a small fixed set of infrastructure tasks being distinct from canonical Oats-node task runs
- dynamic Prefect task creation where canonical Oats nodes become real Prefect task runs
- retry-safe task wrappers
- provider invocation and validation command execution inside Prefect tasks
- local artifact checkpoint writes
- run metadata linking Prefect flow-run IDs back to `.oats/`
- absence of bespoke local-checkpoint resume behavior in v1

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_flows.py`
Expected: FAIL because the flow runtime does not exist.

- [ ] **Step 3: Implement the shared flow entry point**

Extend the minimal shared flow entry point in `python/oats/prefect/flows.py` so it executes compiled run payloads rather than only existing as a registration target. Keep one reusable Prefect flow entry point instead of generating bespoke flow modules, and make its fixed infrastructure tasks explicit so canonical Oats task runs remain separately identifiable.

- [ ] **Step 4: Implement task wrappers and artifact checkpoints**

Create `python/oats/prefect/tasks.py` so individual graph nodes can:
- execute real work via the existing repo/provider invocation path
- run validation commands in-task where appropriate
- emit structured local checkpoints using the artifact helpers introduced in Task 5
- record linked Prefect run metadata through that shared artifact layer
- be retried safely without corrupting local artifacts

- [ ] **Step 5: Validate**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_flows.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add python/oats/prefect/flows.py python/oats/prefect/tasks.py tests/oats/test_prefect_flows.py
git commit -m "feat: add prefect flow runtime"
```

## Task 7: Worktree, Branch, and Repo Execution Integration

**Files:**
- Create: `python/oats/prefect/worktree.py`
- Modify: `python/oats/pr.py`
- Create: `tests/oats/test_prefect_worktree.py`

- [ ] **Step 1: Write failing worktree tests**

Create `tests/oats/test_prefect_worktree.py` covering:
- idempotent worktree creation
- branch naming and integration-branch derivation
- fixed v1 worktree root under `.oats-worktrees/`
- one task worktree per flow-run/task pair
- safe reruns when a worktree already exists
- repo execution context attachment to Prefect task payloads
- handoff from worktree/bootstrap tasks into provider execution tasks
- no same-run parallel repo mutation in v1

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_worktree.py`
Expected: FAIL because the Prefect worktree layer does not exist.

- [ ] **Step 3: Implement worktree orchestration helpers**

Create `python/oats/prefect/worktree.py` for:
- worktree path resolution
- integration branch preparation
- task-branch preparation
- rerun-safe cleanup hooks

Use one task worktree per flow-run/task pair rooted under `.oats-worktrees/<flow-run-id>/<task-id>/`. Keep same-run repo mutation sequential in v1 even though Prefect records real task runs for each canonical node.

- [ ] **Step 4: Reuse existing git helpers where possible**

Modify `python/oats/pr.py` only where existing branch-name or PR-title helpers should be shared, not duplicated.

- [ ] **Step 5: Validate**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_worktree.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add python/oats/prefect/worktree.py python/oats/pr.py tests/oats/test_prefect_worktree.py
git commit -m "feat: add prefect worktree execution helpers"
```

## Task 8: Helaicopter Backend Prefect API Proxy

**Files:**
- Create: `python/helaicopter_api/ports/prefect.py`
- Create: `python/helaicopter_api/adapters/prefect_http.py`
- Create: `python/helaicopter_api/application/prefect_orchestration.py`
- Create: `python/helaicopter_api/schema/prefect_orchestration.py`
- Create: `python/helaicopter_api/router/prefect_orchestration.py`
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Modify: `python/helaicopter_api/server/config.py`
- Modify: `python/helaicopter_api/router/router.py`
- Create: `tests/test_api_prefect_orchestration.py`

- [ ] **Step 1: Write failing backend API tests**

Create `tests/test_api_prefect_orchestration.py` covering:
- list deployments
- list flow runs
- fetch a single flow-run detail
- show worker and work-pool state
- show queue placement and deployment schedule/health summaries
- show task-run summaries and stale worker/flow states
- join Prefect payloads with repo-local Oats metadata, git branches, and worktree context when available
- legacy Oats runtime history remains readable as historical data during migration

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest -q tests/test_api_prefect_orchestration.py`
Expected: FAIL because the Prefect backend surface does not exist.

- [ ] **Step 3: Implement the Prefect port and HTTP adapter**

The adapter should be backend-owned and hide raw Prefect HTTP shapes from the rest of the app.

- [ ] **Step 4: Implement backend application/schema/router layers**

Add a new backend orchestration family for Prefect rather than forcing Prefect data into the existing disk-artifact Oats schema.
Treat the live Prefect-backed backend surface as the primary source for dashboard state; local synced metadata is only supplemental join data.
Include explicit schema fields for repo root, worktree path, branch names, and local artifact references so the frontend contract is complete before UI work starts.

- [ ] **Step 5: Wire settings and services**

Add explicit Prefect API configuration to `python/helaicopter_api/server/config.py` and wire the client in `python/helaicopter_api/bootstrap/services.py`.

- [ ] **Step 6: Validate**

Run: `uv run --group dev pytest -q tests/test_api_prefect_orchestration.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python/helaicopter_api/ports/prefect.py python/helaicopter_api/adapters/prefect_http.py python/helaicopter_api/application/prefect_orchestration.py python/helaicopter_api/schema/prefect_orchestration.py python/helaicopter_api/router/prefect_orchestration.py python/helaicopter_api/bootstrap/services.py python/helaicopter_api/server/config.py python/helaicopter_api/router/router.py tests/test_api_prefect_orchestration.py
git commit -m "feat: add prefect orchestration backend api"
```

## Task 9: Helaicopter Frontend Prefect Dashboard and Normalization

**Files:**
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/types.ts`
- Modify: `src/hooks/use-conversations.ts`
- Modify: `src/components/orchestration/orchestration-hub.tsx`
- Modify: `src/components/orchestration/overnight-oats-panel.tsx`
- Modify: `src/app/orchestration/page.tsx`
- Create: `src/lib/client/prefect-normalize.test.ts`

- [ ] **Step 1: Write failing frontend normalization tests**

Create `src/lib/client/prefect-normalize.test.ts` using `node:test` to cover:
- new endpoint builders
- normalization of Prefect deployments and flow runs
- worker/work-pool/queue summaries
- deployment schedule/health summaries
- task-run summaries and stale-state indicators
- joined links back to local Oats artifacts, worktrees, and branch context

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --import tsx --test src/lib/client/prefect-normalize.test.ts`
Expected: FAIL because the endpoint builders and normalizers do not exist.

- [ ] **Step 3: Add endpoint/type/normalize support**

Extend the client and type layers to represent Prefect-backed orchestration objects explicitly, including branch/worktree metadata and local artifact links. Do not overload the old `OvernightOatsRunRecord` types if a new type family will keep the boundary cleaner.

- [ ] **Step 4: Update the orchestration UI**

Adapt the orchestration page and panels so they can display Prefect deployments, flow runs, worker health, queue placement, deployment schedules/health, task-run summaries, stale states, linked repo-local artifacts, and branch/worktree context for each run.
Do not require a prior `oats sync` for the dashboard to render current Prefect state.

- [ ] **Step 5: Validate**

Run: `node --import tsx --test src/lib/client/prefect-normalize.test.ts`
Run: `npm run lint -- src/components/orchestration src/lib/client src/hooks`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/lib/client/endpoints.ts src/lib/client/normalize.ts src/lib/types.ts src/hooks/use-conversations.ts src/components/orchestration/orchestration-hub.tsx src/components/orchestration/overnight-oats-panel.tsx src/app/orchestration/page.tsx src/lib/client/prefect-normalize.test.ts
git commit -m "feat: add prefect orchestration dashboard"
```

## Task 10: Cutover, Compatibility Cleanup, and End-to-End Verification

**Files:**
- Modify: `python/oats/cli.py`
- Modify: `python/helaicopter_api/application/orchestration.py`
- Modify: `python/helaicopter_api/router/orchestration.py`
- Create: `docs/oats-prefect-cutover.md`
- Update: `docs/prefect-local-ops.md`
- Update: `README.md`

- [ ] **Step 1: Write failing cutover/compatibility tests**

Add or extend tests so they assert:
- the new Prefect path is the primary orchestration surface
- legacy local-runtime commands are either deprecated or clearly labeled
- backend orchestration routes do not misrepresent Prefect-backed runs as legacy disk-state runs
- legacy `.oats/runtime/` and `.oats/runs/` history remains visible as historical read-only data without a backfill job
- `oats run` and `oats status` now point at Prefect-backed behavior while legacy runtime commands remain available under explicit legacy names

- [ ] **Step 2: Run the targeted tests to verify the gaps**

Run: `uv run --group dev pytest -q tests/oats/test_prefect_deployments.py tests/oats/test_prefect_flows.py tests/test_api_prefect_orchestration.py`
Expected: at least one FAIL before cutover changes land.

- [ ] **Step 3: Make the cutover explicit**

Update CLI help text, backend orchestration copy, and docs so Prefect is clearly the primary path and the old local runtime path is explicitly legacy. At this stage:
- `oats run` becomes an alias to the Prefect-backed trigger path
- `oats status` becomes an alias to the Prefect-backed inspect path
- legacy local runtime commands move under explicit `legacy-*` names

- [ ] **Step 4: Write the cutover runbook**

Create `docs/oats-prefect-cutover.md` covering:
- Compose startup
- launchd worker bootstrap
- `oats deploy`
- schedule creation
- Helaicopter orchestration UI expectations
- historical legacy Oats run visibility expectations
- rollback plan

- [ ] **Step 5: Run full verification**

Run: `uv run --group dev pytest -q`
Run: `node --import tsx --test src/lib/client/normalize.test.ts src/lib/client/prefect-normalize.test.ts`
Run: `npm run lint`
Manual smoke checks:
- start the Compose stack
- load the `launchd` worker
- verify worker registration in Prefect
- verify one scheduled run fires from the configured cron schedule
- verify the Helaicopter orchestration page renders live Prefect state
Expected: all targeted tests and lint pass.

- [ ] **Step 6: Commit**

```bash
git add python/oats/cli.py python/helaicopter_api/application/orchestration.py python/helaicopter_api/router/orchestration.py docs/oats-prefect-cutover.md docs/prefect-local-ops.md README.md
git commit -m "feat: cut over oats orchestration to prefect"
```

## Execution Notes

- Execute tasks in order unless a reviewer explicitly approves safe parallelization.
- Keep Markdown as the only supported run-definition input in this plan.
- Do not containerize the worker as part of this plan.
- When code and docs disagree, update the docs in the same task rather than creating drift.
- Use frequent commits exactly as scoped above; do not batch the whole migration into one commit.
