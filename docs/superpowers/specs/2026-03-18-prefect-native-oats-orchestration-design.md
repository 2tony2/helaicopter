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
- trigger, inspect, and optionally resume Prefect-backed runs
- provide shared helpers for git/worktree management, provider invocation, artifact writing, and repo-specific policy

### 3. Markdown-first input

The first rollout must keep Markdown run specs as the input surface because that is what the repo already uses. The compiler boundary must be designed so additional input adapters can exist later, but YAML is explicitly out of scope for the first implementation wave.

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

## Component Model

### Oats Compiler Layer

New Oats responsibilities:
- load Markdown run specs plus `.oats/config.toml`
- build a canonical run definition independent of input format
- compile canonical run definitions into Prefect flow/deployment payloads
- provide CLI commands such as `oats deploy`, `oats run`, `oats status`, and `oats sync`

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
2. `oats deploy` parses the Markdown and repo config.
3. Oats normalizes the input into a canonical run definition.
4. Oats compiles the definition into Prefect deployment metadata.
5. Oats registers or updates the deployment in Prefect.
6. A schedule or manual trigger creates a Prefect flow run.
7. The local macOS worker picks the run from the configured work pool/queue.
8. Prefect tasks call into Oats repo-execution helpers for worktree, provider, validation, and artifact handling.
9. Helaicopter backend proxies Prefect state and joins it with repo-local artifacts for UI consumption.

## Input and Compilation Model

### Canonical Run Definition

The compiler boundary needs a canonical model that is independent of input syntax and independent of Prefect. It should represent:
- run metadata
- task nodes
- dependency edges
- validation commands
- repo execution hints
- retry/timeouts/concurrency hints
- display metadata for Helaicopter

### Markdown Input Adapter

The first input adapter wraps the existing Markdown parser. It should preserve current behavior where possible, but it should output the canonical run definition instead of a runtime-state-specific model. The existing parser may remain as the Markdown ingestion layer, or it may be refactored behind a new loader module. Either way, the canonical boundary must stay independent from Prefect and independent from local runtime-state persistence.

### Prefect Compiler

The compiler translates the canonical run definition into:
- a Prefect flow function or parameter payload
- Prefect task/subflow relationships
- deployment metadata
- schedule and queue configuration
- tags and concurrency hints

The first rollout should prefer one reusable flow implementation that accepts compiled run-definition payloads at runtime, rather than generating bespoke Python source per run spec.

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

### Future deployment mode

The overall plan should explicitly leave room for a future secondary deployment mode using Dockerized `.serve()`-style flow execution. That belongs in the roadmap, but it is not the primary first implementation path.

## Branch and Worktree Strategy

- The long-lived Oats CLI and control-plane config remain on the main checkout.
- Implementation work executes in isolated worktrees rooted under `.oats-worktrees/` or a later equivalent path.
- Prefect flow runs create a run-scoped integration branch and task-scoped working branches in those worktrees.
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
- selected logs or task summaries

The backend is also the correct place to join Prefect run IDs with:
- local run-spec paths
- repo roots
- worktree paths
- branch names
- `.oats/` artifacts

### Frontend

The orchestration UI should evolve from a disk-artifact Oats panel to a control-plane dashboard that can show:
- scheduled, running, failed, and completed flow runs
- deployment health and schedules
- worker health
- queue and pool placement
- task graph progress
- links from flow runs back to local artifacts, branches, and transcripts

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

## Phased Program

The implementation should land in the following high-level phases:

1. local Prefect platform bootstrap
2. launchd/worker operations
3. canonical Markdown-first run-definition layer
4. Prefect compiler and deployment registration
5. Prefect-native runtime execution
6. worktree/branch execution model
7. Helaicopter backend Prefect integration
8. Helaicopter frontend orchestration UX
9. cutover and compatibility cleanup
10. verification and operational hardening

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
