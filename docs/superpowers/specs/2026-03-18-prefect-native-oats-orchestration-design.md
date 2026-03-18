# Prefect-Native Oats Orchestration Design

## Executive Summary

Helaicopter currently vendors Oats as a local orchestration CLI that persists runtime state under `.oats/runtime/` and exposes those artifacts in the orchestration dashboard. That model is interruption-aware, but it is still a foreground local subprocess model. The new target state is a Prefect-native orchestration system where Prefect owns scheduling, state, retries, queues, workers, and long-lived orchestration metadata. Oats becomes a thin Markdown-first compiler/CLI that translates repo-local run specs into Prefect deployments and flow runs, manages repo-specific execution helpers, and retains local artifacts that are useful outside Prefect.

The first rollout is explicitly local and self-hosted:
- Prefect control-plane services run locally via Docker Compose.
- The Prefect worker runs directly on macOS under `launchd`, wrapped in `caffeinate`.
- The worker executes against local repository worktrees, not inside containers.
- Helaicopter reads Prefect state through backend-owned REST integrations, not browser-direct calls.

This design preserves the current repo-local workflow while replacing Oats' bespoke orchestration runtime with an industry-standard orchestration layer.

## Goals

- Make Prefect the single source of truth for orchestration state, scheduling, retries, and worker health.
- Keep Oats as the repo-aware UX layer: parse run specs, compile deployments, trigger runs, inspect status, and manage repo-specific helpers.
- Keep input Markdown-first for the first rollout.
- Support phased implementation in one large migration plan that can be executed as sequenced Oats tasks.
- Surface Prefect orchestration state in Helaicopter's backend and frontend.
- Keep the long-running orchestrator on the main checkout while implementation work happens in isolated worktrees and branches.

## Non-Goals

- YAML-first run definitions in the first rollout.
- Cloud-hosted Prefect.
- Containerizing the worker in the first rollout.
- Replacing repo-local artifacts with Prefect-only storage.
- Solving true execution-through-sleep beyond best-effort local mitigation with `caffeinate`.

## Current State

### Oats

- Oats is a Typer CLI under `python/oats/cli.py`.
- Run definitions are currently Markdown files parsed by `python/oats/parser.py`.
- Planning and execution are modeled locally in `python/oats/models.py`, `python/oats/planner.py`, `python/oats/runner.py`, and `python/oats/runtime_state.py`.
- The repo config lives at `.oats/config.toml`; alternate repo config paths are not supported.

### Helaicopter

- The backend exposes orchestration data through `python/helaicopter_api/application/orchestration.py`, `python/helaicopter_api/schema/orchestration.py`, and `python/helaicopter_api/router/orchestration.py`.
- Those backend surfaces currently read Oats runtime artifacts from disk via `python/helaicopter_api/adapters/oats_artifacts/`.
- The frontend orchestration dashboard is centered around `src/components/orchestration/overnight-oats-panel.tsx`.

## Settled Design Decisions

### 1. Prefect owns orchestration

Prefect is the primary control plane. Scheduling, work pools, queues, retries, run state, worker state, and observable orchestration status belong to Prefect. Oats no longer owns that lifecycle as a local runtime-state machine.

### 2. Oats becomes a thin compiler and repo adapter

Oats remains valuable as the repo-local UX and integration layer. It will:
- parse Markdown run specs and repo config
- normalize them into a canonical run definition
- compile that definition into Prefect deployment and flow payloads
- trigger, inspect, sync, and later cut over the default run/status commands onto Prefect-backed runs
- provide shared helpers for git/worktree management, provider invocation, artifact writing, and repo-specific policy

### 3. Markdown-first input

The first rollout must keep Markdown run specs as the input surface because that is what the repo already uses. The compiler boundary must be designed so additional input adapters can exist later, but YAML is explicitly out of scope for the first implementation wave.

For v1, execution-hint sources are intentionally narrow:
1. task-level validation overrides authored in Markdown
2. repo defaults from `.oats/config.toml` for validation defaults, task retry, task timeout, branch behavior, and deployment-routing defaults
3. explicit CLI overrides for deploy-time concerns such as schedule enablement, work pool, queue, tags, schedule timezone, and selected runtime knobs like timeout
4. built-in code defaults

Markdown remains responsible for the task graph and task instructions. It does not gain new syntax in v1 for retry, timeout, schedule, queue, or work-pool authorship.

### 4. Self-hosted local topology

The first deployment topology is:
- Docker Compose for `postgres`, `redis`, `prefect-server`, and `prefect-services`
- `launchd` for the local macOS Prefect worker
- `caffeinate` wrapping the worker process
- local worktree execution against the checked-out repo

This follows Prefect's self-hosted and daemonization guidance while staying practical for a local Mac.

### 5. Helaicopter integrates through the Prefect REST API

The browser should not call Prefect directly. Helaicopter's FastAPI backend should proxy Prefect's REST API, normalize the pieces Helaicopter needs, and join Prefect state with repo-local Oats artifacts and git metadata.

### 6. One large phased program

The migration spans local infra, compiler work, Prefect runtime integration, backend API changes, and frontend changes. It will remain one large plan and one top-level Oats run spec, but it will be implemented in phases and subdivided into ten sequenced tasks.

## Target Architecture

The target architecture combines three layers:
- a Markdown-first Oats compiler layer
- a self-hosted local Prefect control plane
- a Helaicopter backend/frontend integration layer that reads Prefect state while preserving useful local Oats artifacts

### Component Model

### Oats Compiler Layer

New Oats responsibilities:
- load Markdown run specs plus `.oats/config.toml`
- build a canonical run definition independent of input format
- compile canonical run definitions into Prefect deployment parameter payloads for one shared flow implementation
- provide CLI commands such as `oats deploy`, `oats trigger`, `oats inspect`, and `oats sync` during migration

### Prefect Runtime Layer

Prefect responsibilities:
- deployment storage
- schedule execution
- work pool and queue routing
- retry semantics
- flow/task state
- worker state and health
- logs and run metadata

### Repo Execution Layer

Repo-specific execution remains inside Oats-owned library code invoked by Prefect tasks:
- create or reuse worktrees
- create integration and task branches
- run Codex/Claude invocations
- run validation commands
- write `.oats/` artifacts
- collect structured status for Helaicopter

### Helaicopter Control-Plane Integration

Helaicopter will add Prefect-focused application, schema, adapter, and router layers. The orchestration dashboard will read Prefect deployments, flow runs, workers, and work pools via backend-managed API calls.

## Runtime Flow

1. A human authors or updates a Markdown run spec.
2. `oats deploy` or `oats trigger` parses the Markdown and repo config.
3. Oats normalizes the input into a canonical run definition.
4. Oats compiles the definition into Prefect deployment metadata.
5. Oats registers or updates the deployment in Prefect.
6. A schedule or manual trigger creates a Prefect flow run.
7. The local macOS worker picks the run from the configured work pool/queue.
8. The shared Prefect flow materializes real Prefect task runs that correspond to canonical Oats nodes.
9. Those Prefect task runs call into Oats repo-execution helpers for worktree setup, provider invocation, validation, and artifact handling.
10. Helaicopter backend proxies Prefect state and joins it with repo-local artifacts for UI consumption.

For v1:
- `oats deploy` upserts the deployment only
- `oats trigger <run-spec>` compiles the run spec, upserts the deployment, and then creates a flow run
- direct trigger-by-run-spec is required and is just a deploy-plus-trigger convenience path, not a second runtime architecture

## Input and Compilation Model

### Canonical Run Definition

The compiler boundary needs a canonical model that is independent of input syntax and independent of Prefect. It should represent:
- run metadata
- task nodes
- dependency edges
- validation commands
- normalized repo execution hints
- normalized retry/timeout hints
- normalized deployment-routing hints
- display metadata for Helaicopter

Scheduling and routing metadata are intentionally not authored in Markdown for v1. The canonical run definition should stay focused on the execution graph plus repo execution semantics. Schedule defaults, work-pool names, queue names, and deployment-routing policy come from `.oats/config.toml` and optional CLI overrides at deploy time. The Prefect compiler merges:
- the canonical Markdown-derived run definition
- repo-level Prefect defaults from `.oats/config.toml`
- explicit CLI overrides for one-off deploys

In v1, the canonical run definition may carry normalized execution hints after loading, but those hints are compiler inputs derived from repo config and CLI overrides rather than new Markdown-authored fields. The only task-level execution hint authored in Markdown for v1 is `Validation override:`.

For v1, the schedule model is intentionally narrow:
- zero or one schedule per deployment
- schedule type: cron only
- required schedule fields when enabled: cron expression and timezone
- if schedule is disabled or absent, the deployment is manual-only

### v1 canonical field matrix

| Field | Required | Source | New Markdown syntax needed in v1? | Notes |
|---|---|---|---|---|
| `run_title` | yes | Markdown H1 | no | same behavior as current parser |
| `source_path` | yes | loader/runtime | no | repo-relative path retained for deployment identity |
| `tasks` | yes | Markdown task blocks | no | same `## Tasks` / `### task_id` layout |
| `task_id` | yes | Markdown task heading | no | same behavior as current parser |
| `task_title` | optional | Markdown `Title:` or derived fallback | no | preserve current fallback behavior |
| `prompt` | yes | Markdown body paragraphs | no | preserve current parser semantics |
| `depends_on` | optional | Markdown `Depends on:` | no | preserve current parser semantics |
| `acceptance_criteria` | optional | Markdown `Acceptance criteria:` | no | preserve current parser semantics |
| `notes` | optional | Markdown `Notes:` | no | preserve current parser semantics |
| `validation_commands` | optional | Markdown `Validation override:` else `.oats/config.toml` | no | task-level override wins over repo defaults |
| `repo_execution_hints` | optional | `.oats/config.toml` | no | branch naming and execution defaults; worktree root is fixed to `.oats-worktrees/` in v1 |
| `retry_policy` | optional | `.oats/config.toml` | no | attached during load/compile; maps to task-level Prefect retries in v1 |
| `timeout_seconds` | optional | `.oats/config.toml` and CLI override | no | attached during load/compile; maps to task-level repo-execution timeout in v1 |
| `deployment_routing` | optional | `.oats/config.toml` and CLI override | no | pool, queue, tags, schedule |
| `display_metadata` | optional | compiler/runtime derived | no | used for Helaicopter summaries |

Markdown compatibility target for v1 is full compatibility with the current parser surface already present in `python/oats/parser.py` and the example run specs in `examples/`. The first rollout must not require new Markdown syntax to produce valid canonical run definitions; new deployment-routing and runtime defaults belong in `.oats/config.toml` and CLI overrides.

### Markdown Input Adapter

The first input adapter wraps the existing Markdown parser. It should preserve current behavior where possible, but it should output the canonical run definition instead of a runtime-state-specific model. The existing parser may remain as the Markdown ingestion layer, or it may be refactored behind a new loader module. Either way, the canonical boundary must stay independent from Prefect and independent from local runtime-state persistence.

### Prefect Compiler

The compiler translates the canonical run definition into:
- a parameter payload for one shared Prefect flow implementation
- Prefect task/subflow relationships where each canonical Oats node becomes a real Prefect task run inside the shared flow
- deployment metadata
- schedule and queue configuration derived from repo config and deploy-time overrides, not from Markdown task bodies
- tags and timeout/retry settings

This is a hard v1 decision: the compiler will not generate bespoke Python flow modules per run spec. It emits deployment data plus a runtime payload that one reusable flow implementation consumes.

In v1:
- `retry_policy` maps to task-level Prefect retry settings on the task runs that wrap canonical Oats nodes
- `timeout_seconds` maps to task-level repo-execution timeout used by those task wrappers
- flow-level retry/timeouts are out of scope
- Prefect concurrency limits are deferred beyond v1; the single-worker, sequential-repo-mutation model is sufficient for the first rollout

### Deployment identity

Deployment identity must be deterministic for safe upserts and for backend/frontend joins. In v1:
- the stable deployment key is the repo-relative run-spec path in POSIX form, for example `examples/prefect_native_oats_orchestration_run.md`
- the deployment name is a slugified form of that repo-relative path without the file extension, for example `examples--prefect-native-oats-orchestration-run`
- the shared Prefect flow implementation stays constant; deployment identity varies by run-spec-derived key
- local Oats artifacts should store both the deployment key and the resulting Prefect deployment ID when available

The first rollout assumes one repo checkout per self-hosted Prefect server/worker pair. That keeps repo-relative run-spec path unique enough for v1 deployment identity, and Helaicopter recovers `repo_root` from local application configuration rather than from Prefect alone.

## Deployment and Service Topology

### Compose-managed services

Compose is responsible for:
- Postgres
- Redis
- Prefect server
- Prefect services

This makes the control plane reproducible and keeps local bootstrap predictable.

### Host-managed worker

The worker stays on the host because it needs:
- direct access to local repositories
- direct access to local git and CLI auth state
- direct access to worktree paths
- direct use of macOS power-management mitigation (`caffeinate`)

`launchd` should manage worker restarts, and `caffeinate` should be part of the worker wrapper script.

## Post-v1 Roadmap Notes

- A future secondary deployment mode may package the shared flow runtime using Dockerized `.serve()`-style execution.
- That roadmap item is explicitly out of scope for the first implementation plan.

## Branch and Worktree Strategy

- The long-lived Oats CLI and control-plane config remain on the main checkout.
- Implementation work executes in isolated worktrees rooted under `.oats-worktrees/` in v1. That root is fixed for the first rollout rather than repo-configurable.
- Each Prefect flow run creates one run-scoped integration branch.
- Each executable task gets its own task-scoped worktree under `.oats-worktrees/<flow-run-id>/<task-id>/` and its own task branch derived from the run-scoped integration branch.
- Prefect still records one real task run per canonical Oats node, but local repo-mutating execution is sequential in topological order for v1. Same-run parallel repo writes are explicitly out of scope for the first rollout.
- Branch and worktree creation are explicit early tasks in the flow, not incidental side effects.

This satisfies the requirement that Oats can keep running from the main checkout while code changes happen elsewhere.

## Helaicopter Integration Design

### Backend

The backend should add a Prefect API client and new orchestration application surfaces that expose:
- deployments
- flow runs
- flow-run detail
- workers
- work pools and queues
- task-run summaries and schedule/health summaries required for the orchestration dashboard

The backend is also the correct place to join Prefect run IDs with:
- local run-spec paths
- repo roots
- worktree paths
- branch names
- `.oats/` artifacts

Live Prefect-backed backend endpoints are the source of truth for the Helaicopter orchestration dashboard in v1. Local `.oats/` metadata is supplementary correlation data, not the primary serving path for live orchestration state.

### Frontend

The orchestration UI should evolve from a disk-artifact Oats panel to a control-plane dashboard that can show:
- scheduled, running, failed, and completed flow runs
- deployment health and schedules
- worker health
- queue and pool placement
- task graph progress
- stale worker/flow states
- links from flow runs back to local artifacts and branches

Transcript links and rich log exploration are explicitly deferred beyond v1 unless they fall out naturally from existing data.

## Cutover and Compatibility Policy

The rollout should be explicit about what remains supported while migration is in progress.

- New orchestration executions move to the Prefect-backed path as soon as the relevant deployment/runtime tasks land.
- Existing `.oats/runtime/` and `.oats/runs/` artifacts remain visible in Helaicopter as historical, read-only legacy data during the rollout.
- Helaicopter may temporarily dual-read legacy Oats artifact history and Prefect-backed live state, but it does not need a backfill job that rewrites old Oats history into Prefect.
- Legacy local-runtime CLI commands remain available during migration, but they should be marked as legacy and stop being the recommended path.
- The cutover phase is complete when Prefect is the default execution path, legacy runtime surfaces are clearly labeled historical/legacy, and no new orchestration work depends on the old local-runtime state machine.

### v1 CLI command map

During migration, v1 introduces a non-conflicting command set:
- `oats deploy` -> compile Markdown + repo config and upsert a Prefect deployment
- `oats trigger` -> create a Prefect flow run from a deployment or run spec
- `oats inspect` -> inspect Prefect-backed run/deployment state
- `oats sync` -> reconcile local artifacts and metadata against Prefect state

Existing `oats run`, `resume`, `status`, and `watch` remain legacy while Tasks 1-9 land.

During the final cutover phase:
- `oats run` becomes the human-friendly alias for the Prefect-backed trigger path
- `oats status` becomes the human-friendly alias for the Prefect-backed inspect path
- legacy local-runtime commands move under explicit legacy names such as `oats legacy-run`, `oats legacy-status`, `oats legacy-resume`, and `oats legacy-watch`

### v1 resume semantics

v1 does not implement bespoke local checkpoint resume that restarts a partially executed flow from `.oats/` artifacts. Recovery uses Prefect-native retry/rerun mechanics plus idempotent repo execution helpers. Local artifact checkpoints exist for observability, correlation, and safe reruns, not as a second orchestration engine.

### v1 sync semantics

`oats sync` is a one-way reconciliation command from Prefect into local `.oats/` metadata and artifact indexes. In v1 it is responsible for:
- refreshing normalized run-definition snapshots
- refreshing local deployment/run linkage metadata
- refreshing git/worktree metadata and branch linkage for completed or in-flight runs
- refreshing cached local summaries used for repo-local inspection, offline inspection, or supplemental backend joins
- recording last-seen task-run summaries and state snapshots

`oats sync` is not a prerequisite for the Helaicopter dashboard to show current state. The dashboard should render from live Prefect-backed backend endpoints even if local sync has not been run recently.

It is not responsible for:
- mutating Prefect state
- repairing git/worktree state
- replaying missing execution
- acting as a second orchestrator

## v1 Config and Override Surface

The minimum v1 Prefect config surface should live under `.oats/config.toml` with CLI override precedence.

Config ownership in v1 is:
- existing `[validation]` remains authoritative for default validation commands
- existing `[git]` remains authoritative for task/integration branch prefixes and PR targets
- existing `[repo]` remains authoritative for repo execution defaults, including `worktree_dir`, which must remain `.oats-worktrees` for the first rollout
- existing `repo.default_concurrency` is preserved for backward compatibility with current planning code but is not mapped to Prefect concurrency primitives in v1
- new `[prefect]` config holds:
  - `api_url`
  - `work_pool`
  - `default_queue`
  - `default_tags`
  - `default_task_retry_count`
  - `default_task_timeout_seconds`
  - `default_schedule_enabled`
  - `default_schedule_cron`
  - `default_schedule_timezone`

Precedence:
1. explicit CLI override
2. `.oats/config.toml` defaults from `[prefect]` plus the existing `[validation]`, `[git]`, and `[repo]` sections
3. built-in code defaults

Markdown run specs remain graph/task definitions only in v1.

## Failure Model and Idempotency

Local orchestration still has real interruption modes:
- worker crash
- machine reboot
- machine sleep
- CLI auth expiration
- git worktree drift

The design therefore needs:
- idempotent worktree/bootstrap tasks
- resumable deployment registration
- retry-safe provider invocation wrappers
- explicit artifact checkpoints
- backend UI states for stale worker and stale flow conditions

The design does not assume that local work continues during actual machine sleep; it assumes that the system can recover cleanly after interruption.

The shared Prefect flow may contain a small fixed set of infrastructure tasks such as run-context initialization and final artifact flush. Those tasks are outside the canonical Oats task graph. Canonical Oats task nodes still map 1:1 to real Prefect task runs, and backend/frontend task summaries should distinguish infrastructure tasks from canonical work nodes.

## Data and Artifact Ownership

Prefect should own orchestration metadata. Oats should retain repo-local artifacts that are valuable for repo inspection and Helaicopter correlation, including:
- normalized run-definition snapshots
- run-to-deployment linkage metadata
- repo-local reports
- git/worktree metadata
- mapped flow-run identifiers

The old `.oats/runtime/` machine is not the long-term source of truth, but selected local artifacts remain useful and should not be discarded prematurely.

## Testing Strategy

The implementation must be test-first where feasible and should add coverage in the following groups:
- Oats run-definition normalization tests
- Oats Prefect compiler and deployment registration tests
- Oats flow/task runtime tests with mocked Prefect contexts and provider invocations
- launchd/Compose asset smoke validation
- FastAPI Prefect orchestration API tests
- frontend endpoint/normalization tests for Prefect payloads

Manual smoke checks are still required for:
- Compose startup
- `launchd` service loading
- worker registration
- scheduled flow execution
- Helaicopter dashboard rendering against a live local Prefect server

## Ten Implementation Tasks

The implementation plan and Oats run spec should use this stable ten-task breakdown:

1. Prefect local platform foundation
2. launchd worker and local ops assets
3. Markdown-first canonical run-definition layer
4. Prefect compiler and deployment payload builder
5. Prefect client, deployment registration, and thin CLI commands
6. Prefect-native flow runtime and artifact checkpoints
7. Worktree, branch, and repo execution integration
8. Helaicopter backend Prefect API proxy
9. Helaicopter frontend Prefect dashboard
10. Cutover, compatibility cleanup, and end-to-end verification

These ten implementation tasks may be grouped into broader phases for human communication, but the task list above is the authoritative migration breakdown.

## Risks

- The migration touches infrastructure, CLI behavior, backend contracts, and frontend orchestration views.
- Prefect integration can sprawl if the canonical run-definition boundary is weak.
- Local-only workers still depend on the machine staying awake enough to execute the run.
- Attempting to support too many input or deployment modes in v1 would dilute the first rollout.

## Success Criteria

The design is successful when:
- a Markdown run spec can be deployed into Prefect through Oats
- a local self-hosted Prefect control plane can schedule and execute the run
- execution happens in isolated worktrees while the orchestrator remains on the main checkout
- Helaicopter can display Prefect-driven orchestration state
- the old local-runtime orchestration path is no longer the primary execution path
