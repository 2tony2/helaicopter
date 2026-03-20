# Full Program OATS Prefect Overnight Run Design

## Executive Summary

Helaicopter needs a single overnight OATS run that drives the full implementation program for authoritative analytics, Python-owned semantics, orchestration analytics, and near-real-time refresh, but it cannot be a single blind cutover task. The correct shape is one Prefect-backed OATS run that executes the full program as a sequence of bounded task groups with explicit validation gates, autonomous continuation where safe, and automated PR creation.

By morning, the run should have:

- executed as much of the program as possible without human intervention
- produced task branches and task PRs for completed work
- maintained one integration branch for the whole run
- recorded failures and blocked follow-on work only where dependencies require it
- emitted a final summary artifact that shows completed, failed, skipped, and still-risky areas

## Goals

- Define one OATS markdown run spec for the full implementation program.
- Use the existing Prefect-backed OATS execution path as the runtime.
- Structure the work as phased implementation tasks with strict boundaries.
- Preserve autonomy overnight by continuing independent work after failures.
- Auto-create task PRs and a final PR through the existing OATS git policy.
- Require validation commands per task and a final verification/cutover summary.

## Non-Goals

- Replacing OATS or Prefect runtime behavior in this spec
- Guaranteeing that every phase completes in one night
- Designing a monolithic single-task execution path
- Hiding failures behind a “success” summary when the run only partially completes

## Product And Execution Decisions

The run design is based on the following settled decisions:

- Helaicopter remains local-first and single-user for this work.
- DuckDB is the authoritative historical analytics surface.
- Python owns ingestion and semantic definitions.
- Orchestration analytics are included in scope.
- Near-real-time freshness is part of the target architecture.
- The execution path should use the OATS Prefect setup.
- The overnight run should auto-create task PRs and the final PR.
- The run should continue autonomously as long as downstream work is still meaningful and dependency-safe.

## Why One Run Still Needs Phases

The requested scope is a full implementation program, not a single feature. Trying to express it as one agent prompt would create three problems:

- validation would collapse into one late all-or-nothing check
- failures would waste the rest of the night
- PRs would be too large and hard to reason about

Therefore, the run must be a single OATS run at the orchestration level, but internally composed of bounded tasks that map to coherent milestones.

## Recommended Run Shape

The overnight run should be one Prefect-backed markdown run spec with task groups arranged as a DAG.

### Group 1: Semantic foundation

This group establishes the shared Python semantic layer and contract cleanup foundations. It should include:

- canonical pricing/model matching
- canonical long-context premium logic
- canonical token alias normalization
- canonical status vocabulary and mapping rules
- initial backend contract cleanup for obvious drift such as unsound required fields

This group is the prerequisite for every later group because it removes the highest-value semantic duplication.

### Group 2: Python-native ingestion foundation

This group removes the TypeScript export bridge and introduces Python-native extraction and normalized records for Claude and Codex artifacts.

This group depends on semantic foundation but can branch internally into:

- shared ingestion models and utilities
- Claude extraction
- Codex extraction
- refresh-pipeline wiring

### Group 3: Operational store migration

This group adds provenance and time-semantics improvements to SQLite and introduces idempotent update behavior.

This includes:

- provenance fields such as `record_source` and load timestamps
- separate event-time and file-time fields
- deterministic identity keys
- refresh bookkeeping updates needed for incremental behavior

### Group 4: Warehouse authority cutover

This group makes DuckDB the historical analytics source and extends warehouse loading.

This includes:

- warehouse dimension cleanup and enrichment
- conversation fact loading aligned to Python semantics
- analytics endpoint cutover to DuckDB for historical reads
- bounded current-window supplement support as in-scope work for this overnight program

### Group 5: Orchestration analytics

This group ingests OATS runtime and terminal artifacts into analytical facts while leaving the operational storage format file-based.

This includes:

- run-level orchestration facts
- task-attempt facts
- canonical reconciliation between runtime snapshots and terminal run records
- analytics/API exposure required for the initial orchestration analytics cutover

### Group 6: Frontend simplification

This group removes authoritative business logic from the frontend after backend contracts are stable.

This includes:

- removal of frontend cost/math duplication
- reduction of proxy-style normalization where backend contracts are now explicit
- consumption of backend-owned analytics and status fields

### Group 7: Near-real-time polish and final cutover

This group strengthens the incremental refresh loop, verification, docs, and handoff artifacts.

This includes:

- polling or micro-batch refresh finishing work
- cache invalidation adjustments
- docs updates for the new architecture
- final validation and cutover summary

## Dependency Strategy

The run must encode dependencies conservatively enough to avoid invalid work, but not so conservatively that one failure blocks the whole night.

### Dependency rules

- Semantic foundation blocks everything else.
- Python-native ingestion blocks operational-store and warehouse work that relies on canonical records.
- Warehouse authority and orchestration analytics can proceed in parallel once their prerequisites are met.
- Frontend simplification depends on backend contract stabilization.
- Final cutover depends on all terminal groups but must tolerate partial completion and summarize it accurately.

`backend contract stabilization` means:

- canonical Python semantics are wired into backend responses
- historical analytics endpoints read DuckDB for historical ranges
- orchestration analytics contracts needed by the frontend are present
- known unsound required frontend fields are removed or intentionally supplied by the backend

### Continuation policy

If a task fails:

- direct dependents are blocked
- unrelated tasks continue
- later tasks with satisfied prerequisites continue
- the run never fabricates success for blocked work

This keeps the overnight run productive without violating dependency safety.

## Git And Branching Model

The run should follow the existing OATS git/prefect conventions from `.oats/config.toml`.

### Required behavior

- create one integration branch for the run
- create one task branch per task
- auto-push task branches
- auto-create task PRs
- auto-create the final PR against `main`

### PR expectations

Task PRs should stay bounded to the task scope. The run spec should not encourage giant mixed-purpose tasks, because that would defeat the value of auto-created PRs.

The final PR should be treated as the integration artifact for morning review, not as proof that every planned milestone succeeded.

## Run Artifacts

The overnight program should generate deterministic artifacts that are useful in the morning.

### Required authored files

The implementation should introduce at least:

- one markdown OATS run spec under `examples/`
- one implementation plan doc under `docs/superpowers/plans/`
- any supporting documentation needed to explain the overnight execution and recovery workflow

### Required run outputs

The runtime should emit:

- Prefect flow-run metadata and checkpoints
- OATS task state and records
- task-level validation results
- a final run summary that distinguishes completed, failed, blocked, and skipped tasks

## Task Design Principles

Each task in the run spec should:

- own one coherent implementation slice
- have explicit acceptance criteria
- have explicit validation commands
- avoid bundling unrelated work
- be small enough to create a meaningful PR

Tasks should be implementation-oriented, not analysis-oriented. The point of this run is to land code, tests, docs, and cutover artifacts.

## Validation Strategy

### Per-task validation

Every task should declare focused validation commands. These should be narrower than the repo-wide validation suite when possible so the run can make progress efficiently overnight.

### Cross-phase validation

Some checkpoints need broader validation once multiple tasks land in the integration branch. The plan should include dedicated verification tasks for:

- semantic parity and regression coverage
- ingestion and refresh behavior
- warehouse-backed analytics behavior
- orchestration analytics behavior
- frontend contract and rendering behavior

### Final validation

The final task should run broad validation, gather results, and write a morning handoff summary. If broad validation fails, the run should still create accurate artifacts and PRs for completed tasks rather than discarding the night’s work.

## Failure Handling

Failure handling is central to this design.

### Failure principles

- do not retry endlessly without new evidence
- allow dependency-safe continuation
- record the failed task, reason, and affected downstream tasks
- preserve completed branches and PRs
- make the final summary explicit about what remains unfinished or risky

Merge-conflict handling and limited flaky-test retries should rely on the existing OATS and Prefect runtime policy rather than separate authored plan tasks, unless implementation work reveals a missing runtime capability that itself needs a dedicated task.

### Final summary requirements

The final task should produce a concise but concrete morning summary covering:

- completed tasks
- failed tasks
- blocked tasks
- validation status by phase
- PRs created
- major residual risks

## Scope Boundaries For The First Overnight Run

This run is “full” at the program level, but it still needs a defined boundary for one night of autonomous work.

The run should target:

- implementation of as many phased tasks as possible
- validated commits and PRs for completed tasks
- partial completion transparency where the full program does not finish

The run should not assume:

- guaranteed completion of every milestone
- human intervention during the night
- the absence of merge conflicts, flaky tests, or environment issues

## Documentation To Author Before Execution

Before the overnight run can be used, the repo needs:

- this design spec
- a detailed implementation plan that decomposes the run into task-sized units
- the markdown OATS run definition itself

The plan must be written for agentic execution and include exact files, tests, commands, and checkpoints.

## Open Questions Resolved By This Design

This design settles the following execution questions:

- one overnight run should cover the full implementation program
- it should use the Prefect-backed OATS execution path
- it should auto-create task PRs and a final PR
- it should continue autonomously whenever dependency rules allow

## Planning Constraint

The implementation plan derived from this spec must not collapse the overnight run into a handful of oversized tasks. The value of the design depends on maintaining small, reviewable, validation-gated tasks inside one coordinated run.
