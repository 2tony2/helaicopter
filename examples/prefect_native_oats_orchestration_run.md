# Run: Prefect Native Oats Orchestration

## Tasks

### prefect_platform_foundation
Title: T001 Prefect Local Platform Foundation

Implement Task 1 from `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`. Add the Prefect dependency, add focused Prefect settings for Oats, and create the local Docker Compose stack for the self-hosted control plane. Keep run-definition input Markdown-first for this rollout and do not introduce YAML parsing.

Acceptance criteria:
- Prefect runtime dependency is added and importable
- `python/oats/prefect/settings.py` exists with tested defaults for API URL, pool, queue, and asset paths
- `ops/prefect/docker-compose.yml` and `ops/prefect/.env.example` exist and validate
- tests cover settings and Compose asset discovery

Notes:
- read `docs/superpowers/specs/2026-03-18-prefect-native-oats-orchestration-design.md` and the matching plan before editing
- do not containerize the worker in this task

Validation override:
- uv run --group dev pytest -q tests/oats/test_prefect_settings.py

### launchd_worker_assets
Title: T002 launchd Worker And Local Ops Assets
Depends on: prefect_platform_foundation

Implement Task 2 from `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`. Add the macOS worker wrapper and launchd assets that keep the worker long-lived locally, including `caffeinate` usage and a focused local-ops runbook.

Acceptance criteria:
- launchd plist template exists for the worker
- worker wrapper script exists and wraps `prefect worker start` in `caffeinate`
- local ops documentation covers load, unload, logs, and environment expectations
- tests validate the launchd and wrapper assets

Notes:
- follow the service model from the Prefect daemonization docs, but implement it with macOS launchd assets
- keep machine-specific absolute paths out of committed templates

Validation override:
- uv run --group dev pytest -q tests/oats/test_launchd_assets.py

### markdown_run_definition
Title: T003 Markdown-First Canonical Run Definition Layer
Depends on: prefect_platform_foundation

Implement Task 3 from `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`. Introduce the canonical run-definition model and loader that normalizes the existing Markdown run specs plus `.oats/config.toml` into a Prefect-agnostic task graph.

Acceptance criteria:
- canonical run-definition models exist
- the loader successfully converts current Markdown examples into canonical run definitions
- non-Markdown run-definition inputs are explicitly rejected for this rollout
- existing parser coverage still passes

Notes:
- preserve current Markdown semantics around task titles, dependencies, acceptance criteria, notes, and validation overrides
- do not let Prefect-specific fields leak into the canonical input layer

Validation override:
- uv run --group dev pytest -q tests/oats/test_run_definition_loader.py tests/test_parser.py

### prefect_compiler
Title: T004 Prefect Compiler And Deployment Payload Builder
Depends on: markdown_run_definition

Implement Task 4 from `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`. Create the Prefect-facing compiler that converts canonical run definitions into reusable flow/deployment payloads without generating bespoke Python files per run spec.

Acceptance criteria:
- Prefect compiler models exist and are tested
- dependency edges from the canonical graph are preserved
- work-pool, queue, tag, and naming decisions are deterministic
- compiled payloads are reusable by a shared flow entrypoint

Notes:
- prefer one shared flow runtime that accepts compiled payloads
- keep compiler output stable so redeploys are predictable

Validation override:
- uv run --group dev pytest -q tests/oats/test_prefect_compiler.py

### prefect_cli_deploy
Title: T005 Prefect Client, Deployment Registration, And Thin CLI Commands
Depends on: prefect_compiler, launchd_worker_assets

Implement Task 5 from `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`. Add the Prefect HTTP client, deployment registration layer, and thin Oats CLI commands for `deploy`, `run`, and `status` while preserving current legacy commands until cutover.

Acceptance criteria:
- Prefect HTTP client exists for deployment and flow-run operations
- deployment upsert logic is covered by tests
- CLI help includes the new Prefect-backed commands
- Markdown run specs are still the only accepted input path

Notes:
- keep old local-runtime commands available but clearly legacy
- do not remove legacy behavior in this task

Validation override:
- uv run --group dev pytest -q tests/oats/test_prefect_deployments.py

### prefect_flow_runtime
Title: T006 Prefect-Native Flow Runtime And Artifact Checkpoints
Depends on: prefect_cli_deploy

Implement Task 6 from `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`. Add the shared Prefect flow runtime, task wrappers, and local artifact checkpoints so Prefect owns orchestration while Oats retains useful repo-local metadata.

Acceptance criteria:
- shared Prefect flow entrypoint exists
- task wrappers preserve dependency order and retry-safe behavior
- local artifacts link Prefect flow-run identifiers back to `.oats/`
- flow runtime tests pass

Notes:
- keep the flow runtime generic to compiled payloads
- local artifacts should complement Prefect state, not replace it

Validation override:
- uv run --group dev pytest -q tests/oats/test_prefect_flows.py

### worktree_execution
Title: T007 Worktree, Branch, And Repo Execution Integration
Depends on: prefect_flow_runtime

Implement Task 7 from `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`. Add the worktree and branch execution layer so Prefect tasks run implementation work in isolated checkouts while the main checkout remains stable.

Acceptance criteria:
- worktree orchestration helpers exist and are idempotent
- integration-branch and task-branch setup is part of the runtime path
- reruns do not corrupt existing worktrees
- tests cover the worktree lifecycle

Notes:
- reuse existing branch-name helpers where possible instead of duplicating logic
- this task is what enforces “run Oats from main, do work elsewhere”

Validation override:
- uv run --group dev pytest -q tests/oats/test_prefect_worktree.py

### backend_prefect_api
Title: T008 Helaicopter Backend Prefect API Proxy
Depends on: prefect_cli_deploy

Implement Task 8 from `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`. Add a Prefect API client to the FastAPI backend and expose normalized endpoints for deployments, flow runs, workers, pools, and joined repo-local metadata.

Acceptance criteria:
- backend Prefect port, adapter, application, schema, and router layers exist
- backend config/service wiring supports Prefect API access
- tests cover deployments, flow runs, worker state, and local metadata joins
- router aggregation includes the new Prefect orchestration family

Notes:
- do not have the browser call Prefect directly
- keep raw Prefect HTTP payloads out of frontend-facing schema types

Validation override:
- uv run --group dev pytest -q tests/test_api_prefect_orchestration.py

### frontend_prefect_dashboard
Title: T009 Helaicopter Frontend Prefect Dashboard
Depends on: backend_prefect_api

Implement Task 9 from `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`. Extend the orchestration UI so Helaicopter can display Prefect deployments, flow runs, worker health, and linked repo-local Oats artifacts.

Acceptance criteria:
- frontend endpoint builders and types cover Prefect orchestration resources
- normalization tests exist for Prefect payloads
- orchestration UI renders Prefect deployments, runs, and worker state
- frontend links can connect Prefect run state to local artifacts and repo context

Notes:
- keep the visual language consistent with the current orchestration dashboard
- do not collapse the new data model into old disk-only Oats types if that muddies the boundary

Validation override:
- node --import tsx --test src/lib/client/prefect-normalize.test.ts
- npm run lint -- src/components/orchestration src/lib/client src/hooks

### cutover_and_verification
Title: T010 Cutover, Compatibility Cleanup, And End-to-End Verification
Depends on: worktree_execution, backend_prefect_api, frontend_prefect_dashboard

Implement Task 10 from `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`. Make the Prefect path the primary orchestration surface, write the cutover runbook, update user-facing docs, and verify the end-to-end local setup.

Acceptance criteria:
- Oats CLI and docs clearly position Prefect as the primary orchestration path
- backend/orchestration copy and routes no longer imply the legacy runtime path is primary
- cutover runbook covers Compose, launchd worker bootstrap, deploy, run, and rollback
- targeted end-to-end validation commands are documented and green

Notes:
- do not claim the system survives actual machine sleep; describe it as best-effort local mitigation plus restartable orchestration
- keep the legacy path available only as long as needed for migration safety

Validation override:
- uv run --group dev pytest -q tests/oats/test_prefect_deployments.py tests/oats/test_prefect_flows.py tests/test_api_prefect_orchestration.py
- node --import tsx --test src/lib/client/normalize.test.ts src/lib/client/prefect-normalize.test.ts
- npm run lint
