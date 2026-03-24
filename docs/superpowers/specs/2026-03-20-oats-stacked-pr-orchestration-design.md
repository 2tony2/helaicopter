# Oats Stacked PR Orchestration Design

## Executive Summary

Helaicopter already vendors Oats, exposes authoritative Oats runtime artifacts through the FastAPI backend, renders an orchestration DAG in the UI, and runs execution through legacy orchestration-backed task worktrees. What it does not yet have is a first-class git and pull-request control plane. Branch naming, task PR creation, and merge automation exist as helpers, but they are not the persisted orchestration model, they are not resumable as a run-owned graph, and they are not surfaced coherently in the UI.

The target state is an artifact-first stacked-PR orchestration model:
- one Oats run owns one long-lived feature branch
- each task owns one stable task branch and one stable worktree path
- task PRs stack according to task dependencies instead of always targeting the feature branch
- Codex CLI sessions handle merge operations and conflict resolution
- the final feature PR to `main` is always a human approval gate
- Oats runtime artifacts and legacy orchestration local artifacts are the source of truth for branch and PR lifecycle
- Helaicopter backend and frontend consume that persisted graph directly

This design extends the current Oats runtime and legacy orchestration artifact contracts instead of introducing a separate git-operations ledger as the primary control plane.

## Goals

- Make git worktree, branch, PR, merge, and conflict-resolution lifecycle first-class orchestration state.
- Let one Oats run own a single long-lived feature branch and PR stack across legacy orchestration retries and resumes.
- Support dependency-aware stacked task PRs instead of forcing every task PR to target the feature branch directly.
- Persist the branch and PR graph locally in Oats and legacy orchestration artifacts so Helaicopter can render and orchestrate from repo-local truth.
- Use Codex CLI sessions for merge operations and conflict-resolution steps.
- Keep a mandatory human approval gate for the final feature PR into `main`.
- Extend backend and frontend contracts so the orchestration UI can show both execution state and branch / PR progression.
- Make the data model explicit enough that historical analytics can later derive PR and merge facts from the same artifacts.

## Non-Goals

- Making GitHub the primary source of truth for orchestration state.
- Auto-merging the final feature PR into `main`.
- Replacing the current Oats runtime artifact model with an app-database-only control plane.
- Supporting arbitrary stacked-PR topologies that do not correspond to the task dependency graph.
- Solving every possible repo policy variation in the first implementation.

## Current State

### Oats

- `python/oats/planner.py` creates one integration branch per run and currently assigns every task PR the same base branch.
- `python/oats/pr.py` can build task PRs, create a final PR, and optionally invoke a merge operator, but PR state is recorded only as command execution output.
- `python/oats/runtime_state.py` persists run and task execution status under `.oats/runtime/<run_id>/`, but it does not persist a branch / PR graph.
- `python/oats/legacy-orchestration/worktree.py` already prepares stable task worktrees and branch names for legacy orchestration task execution.
- `python/oats/legacy-orchestration/artifacts.py` persists local legacy orchestration task checkpoints, but those checkpoints do not yet carry first-class branch / PR state.

### Helaicopter backend and frontend

- `python/helaicopter_api/application/orchestration.py` shapes run records, tasks, and DAG nodes from runtime and record artifacts.
- `python/helaicopter_api/schema/orchestration.py` and `src/lib/types.ts` expose execution status, DAG structure, and session links, but not explicit feature-branch, task-branch, PR, or merge-operation objects.
- `src/components/orchestration/overnight-oats-panel.tsx` renders a run list, run header, DAG, and session links, but not a stacked-PR view.

## Settled Design Decisions

### 1. One Oats run owns one long-lived feature branch and final PR

The existing `integration_branch` concept becomes the run-owned feature branch in meaning, though the field remains for backward compatibility in the first rollout. One `run_id` owns:
- one feature branch
- one final PR from that feature branch to `main`
- one branch / PR graph for all tasks in the run

legacy orchestration flow runs may resume and reuse the same run-owned graph, but they do not create a new feature branch or a new PR stack unless a new Oats run is created.

### 2. Task PRs stack according to dependency structure

Each task gets an explicit parent branch reference.

Branching rules:
- a task with no dependencies branches from the feature branch
- a task with exactly one dependency branches from that upstream task branch
- a task with multiple dependencies waits until those upstream task PRs are merged into the feature branch, then branches from the feature branch

That last rule is an implementation inference required by git itself: a task branch cannot simultaneously branch from multiple heads.

When a parent task PR merges:
- Oats keeps the parent branch alive until all open direct-child PRs that target it are retargeted successfully
- each direct child PR is retargeted from the merged parent branch to the feature branch
- only after successful retargeting may branch cleanup consider the merged parent branch eligible for deletion

Because multi-dependency tasks do not open a branch or PR until their dependencies have merged, the first rollout only needs retargeting logic for direct single-parent child PRs.

### 3. Oats and legacy orchestration artifacts are the source of truth

The canonical operational record lives in repo-local artifacts:
- `.oats/runtime/<run_id>/state.json`
- `.oats/runtime/<run_id>/events.jsonl`
- `.oats/legacy-orchestration/flow-runs/<flow_run_id>/metadata.json`
- `.oats/legacy-orchestration/flow-runs/<flow_run_id>/tasks/*.json`
- `.oats/legacy-orchestration/flow-runs/<flow_run_id>/attempts/*`

GitHub state may enrich those records, but it must not replace them as the authoritative orchestration model.

GitHub-derived fields such as mergeability, checks summary, review state, and merge result are stored as persisted snapshots inside the Oats and legacy orchestration artifacts. The persisted snapshot is the control-plane truth; GitHub is the observation source.

### 4. Codex handles merge operations and conflict resolution

Codex CLI remains the merge operator. If a task PR merge fails, Oats launches a conflict-resolution step, records its session and output as first-class operation history, and retries according to repo policy. Merge failure after the configured retry budget leaves the run in a blocked state visible in the UI.

First-rollout repo-policy boundary:
- task PRs merge with merge commits only
- squash merges and rebase merges are out of scope
- task PRs may merge without human approval if they satisfy the configured automated merge policy
- repository protections that require mandatory human review on task PRs are unsupported in the first rollout because they break the intended automation model

### 5. The final feature PR remains a human gate

The final PR from the feature branch to `main` is always created and tracked by Oats, but it is never auto-merged. Helaicopter should clearly present when the run is ready for final review.

### 6. The orchestration UI shows both execution and PR progression

The orchestration hub keeps its current run-list plus detail-pane structure. The detail experience expands to include:
- lightweight git / PR state on task nodes and run cards
- a dedicated stacked-PR inspector for the selected run or task
- operation history, checks summary, and conflict-resolution visibility

### 7. Task PRs wait in an explicit merge-ready state

In the first rollout, `awaiting_task_merge` is a run-level stack summary, not a task execution status. A task PR that exists but does not yet satisfy merge policy persists its own merge-gate details under `task_pr`, while the run may summarize the overall branch / PR control plane as `awaiting_task_merge`. There is no ambient background polling.

If a refreshed snapshot satisfies merge policy, the same refresh or resume operation immediately advances into the merge attempt. No separate human action is required for task PR merges.

### 8. Cleanup is retain-by-default in the first rollout

In the first rollout, merged task branches and task worktrees are retained by default until the run reaches `ready_for_final_review` or a terminal blocked / failed state. Cleanup is an explicit later operation, not an immediate side effect of each successful task merge.

### 9. Execution status and stack status are independent

The first rollout uses separate status layers:
- `run.status`: overall execution lifecycle such as `pending`, `planning`, `running`, `completed`, `failed`, `timed_out`
- `run.stack_status`: branch / PR control-plane summary such as `building`, `awaiting_task_merge`, `resolving_conflict`, `blocked`, `ready_for_final_review`, `completed`
- `task.status`: task execution lifecycle such as `pending`, `running`, `succeeded`, `failed`, `blocked`
- `task_pr.state` and `task_pr.merge_gate_status`: PR lifecycle and merge-readiness details

This separation allows mixed states. For example, one task PR may be waiting on checks while an unrelated task is still executing. In that case the run remains `running` at the execution layer while `stack_status` may summarize the branch / PR layer as `awaiting_task_merge`.

## Component Model

### Oats planning and runtime layer

Oats owns:
- feature-branch naming and lifecycle
- task-branch ancestry decisions
- stable task worktree assignment
- task PR creation and PR metadata capture
- merge attempts and conflict-resolution attempts
- run-scoped branch / PR snapshots and operation history

### legacy orchestration execution layer

legacy orchestration owns:
- task execution retries and resume behavior
- scheduling and worker routing
- execution attempt identities (`flow_run_id`, task attempt numbers)
- local attempt snapshots that point back to the shared `run_id`

legacy orchestration does not own the meaning of the branch stack. It executes against it and records attempt-level observations.

### Helaicopter serving layer

FastAPI normalizes runtime state, final run records, and legacy orchestration local artifacts into one orchestration response model. The frontend consumes one normalized run object that includes both execution state and the branch / PR graph.

### Historical data-model layer

Control-plane truth stays file-backed in Oats and legacy orchestration artifacts. Historical analytics and database facts may derive:
- feature-branch lifecycle metrics
- task PR counts and durations
- merge-attempt counts
- conflict-resolution counts
- final-review latency

Those derived facts are secondary and must not become the operational source of truth.

## Persisted Data Model

### Runtime contracts

Add additive v2 runtime and record shapes:
- `oats-plan-v2`
- `oats-runtime-v2`
- `oats-run-v2`

Compatibility rules:
- keep `integration_branch`, `task_pr_target`, and `final_pr_target` for current callers
- add explicit feature-branch and PR objects instead of forcing clients to infer them
- backend normalization may map the legacy `integration_branch` into the new feature-branch display model during rollout

### Run-scoped objects

Each run should persist:
- `feature_branch`
  - branch name
  - base branch
  - current head SHA
  - pushed status
  - merge readiness summary
- `final_pr`
  - PR number and URL when created
  - base branch and head branch
  - state (`not_created`, `open`, `ready_for_review`, `merged`, `closed`)
  - review gate status
  - checks summary snapshot
  - snapshot metadata (`snapshot_source`, `last_refreshed_at`, `is_stale`)
- `stack_status`
  - `building`
  - `awaiting_task_merge`
  - `resolving_conflict`
  - `blocked`
  - `ready_for_final_review`
  - `completed`
- `active_operation`
  - current PR create, merge, or resolve step
  - agent and session linkage
  - started / heartbeat / finished timestamps

### Task-scoped objects

Each task should persist:
- `repo_context`
  - worktree path
  - task branch name
  - parent branch name
- `branch_snapshot`
  - local head SHA
  - remote head SHA if known
  - pushed status
  - deleted / retained status
- `task_pr`
  - PR number and URL
  - base branch and head branch
  - state (`not_created`, `open`, `merged`, `closed`, `blocked`)
  - merge gate status (`not_ready`, `awaiting_checks`, `awaiting_review_clearance`, `merge_ready`, `merged`)
  - checks summary snapshot
  - mergeability snapshot
  - review summary snapshot
  - merge result snapshot
  - snapshot metadata (`snapshot_source`, `last_refreshed_at`, `is_stale`)
- `operation_history`
  - PR create operations
  - merge attempts
  - conflict-resolution attempts
  - cleanup operations
  - linked agent session IDs when applicable

### Event stream

`events.jsonl` becomes the append-only audit trail for git and PR lifecycle. New event types should include:
- `feature_branch_prepared`
- `task_branch_prepared`
- `task_pr_created`
- `task_pr_merge_requested`
- `task_pr_merge_succeeded`
- `task_pr_merge_failed`
- `conflict_resolution_started`
- `conflict_resolution_succeeded`
- `conflict_resolution_failed`
- `final_pr_created`
- `final_review_ready`

### GitHub snapshot contract

GitHub remains the source for PR observation fields, but Oats is responsible for deciding when to fetch and persist them.

Required refresh points:
- immediately after task PR creation
- immediately before a merge attempt
- immediately after a merge attempt
- immediately after a conflict-resolution attempt
- when a run is resumed
- when a human explicitly requests refresh from the orchestration UI or backend action surface

Required persisted snapshot fields:
- `snapshot_source` such as `github_cli` or a later REST adapter
- `last_refreshed_at`
- mergeability state
- checks rollup
- review summary for each task PR
- review-gate summary for the final PR

First-rollout merge policy for task PRs:
- PR state must be open
- mergeability must be clean
- all required GitHub checks must be passing
- there must be no unresolved blocking review state such as `changes_requested`
- merge method must be `merge_commit`

Task PRs do not require human approval in the first rollout. The only mandatory human gate is the final feature PR to `main`.

Backend serving rules:
- serve the most recent persisted snapshot without silently replacing it
- expose staleness so the UI can distinguish fresh from old GitHub observations
- treat refresh as an explicit orchestration operation, not ambient background polling in the first rollout
- expose `awaiting_task_merge` and related waiting-state summaries so the UI can show why a task PR has not advanced

### Orchestration action contract

The first rollout supports one explicit mutation family for waiting-state advancement:
- `refresh_run` / `resume_run`, modeled as run-scoped orchestration actions

Run-scoped means:
- one invocation targets a single Oats `run_id`
- the action refreshes GitHub snapshots for all waiting PRs in that run
- the action may advance multiple merge-ready task PRs in topological order within that same invocation
- the action also refreshes the final feature PR snapshot if it exists

Ownership and surface:
- Oats CLI owns the underlying runtime behavior
- Helaicopter backend exposes the action
- Helaicopter UI invokes the backend action for operator-driven refresh / resume

Final PR completion detection:
- there is no background polling in the first rollout
- the run transitions from `ready_for_final_review` to `completed` only when an explicit run-scoped refresh observes that the final feature PR is merged
- until that explicit refresh happens, the run remains visible as waiting for final review even if the merge happened externally

Multi-dependency execution gating:
- a multi-dependency task remains execution-`blocked` until all upstream task PRs are merged into the feature branch
- legacy orchestration scheduling for that task is therefore merge-gated, not merely upstream-task-completion-gated
- only after that merge gate clears may the task branch be created and the task transition back to execution-`pending`

## Runtime Flow

1. Oats planning builds the task DAG and the branch-stack plan.
2. Runtime initialization creates or validates the run-owned feature branch state.
3. legacy orchestration task execution prepares or reuses the task worktree and task branch using the persisted parent-branch rule.
4. The executor agent performs code changes in the task worktree.
5. Validation runs for the task.
6. Oats creates or updates the task PR and records the PR snapshot.
7. If the task PR does not yet satisfy merge policy, the run records `awaiting_task_merge` and waits for an explicit run-scoped refresh or resume action.
8. If the task PR is mergeable and checks satisfy policy, that same run-scoped refresh or resume action immediately invokes Codex for the merge attempt and may continue through other merge-ready waiting tasks in topological order.
9. On merge failure, Oats launches conflict resolution, records the attempt, and retries the merge within configured limits.
10. When a task PR merges, Oats retargets any open direct-child PRs to the feature branch before parent-branch cleanup eligibility.
11. Once all task PRs required by the run have merged upward into the feature branch, Oats creates the final PR to `main`.
12. The run transitions to `ready_for_final_review` and waits for human approval outside Oats auto-merge.
13. After the final feature PR is merged by a human, a later explicit run-scoped refresh observes that merged state and marks the run `completed`.

## API and Serving Design

### Backend response changes

Extend `OrchestrationRunResponse` and frontend `OvernightOatsRunRecord` with additive fields for:
- feature branch summary
- final PR summary
- task branch summaries
- task PR summaries
- branch / PR operation history
- node-level git / PR status badges

The initial serving path should remain `GET /orchestration/oats`. A separate endpoint is not required for the first rollout because the orchestration detail view already centers on a selected run record.

### Backend shaping rules

The backend should:
- merge runtime state and final run record views without losing the run-owned branch / PR graph
- prefer live runtime snapshots when a run is active
- merge legacy orchestration attempt artifacts by `run_id` plus task ID
- carry linked Codex session IDs into operation-history responses for merge and conflict-resolution steps
- expose enough parent-branch and base-branch information that the frontend does not need to reconstruct the stack heuristically

## UI Design

### Run list

Each run card should show:
- feature branch name
- overall stack status
- task PR count and merge count
- final review readiness
- blocked / conflict indicators when relevant

### Run detail

Keep the current run header, DAG, and session-link model, but expand the detail view with:
- compact git / PR badges on task nodes
- a stacked-PR inspector that visualizes parent-child PR ancestry
- operation-history detail for the selected run or task
- checks summary and merge outcome detail where available

### Interaction model

- Selecting a task highlights both its DAG node and its PR-stack record.
- The UI shows merge-operator and conflict-resolution sessions as first-class links alongside executor sessions.
- The final PR is visually distinct from task PRs because it is the human-only gate to `main`.

## Failure Handling

### Task execution failures

If task implementation or validation fails, the task remains failed and dependent tasks stay blocked. No PR merge progression happens past that point.

### PR creation failures

If PR creation fails, the failure is recorded as a task operation failure. The run remains blocked on that task until retried or resumed.

### Merge failures

If merge fails:
- record the failed merge attempt
- launch a conflict-resolution step
- record the conflict-resolution session and result
- retry the merge if the resolution step succeeded

If retries are exhausted, the run enters a blocked state that is explicit in both runtime artifacts and UI state.

## Testing Strategy

### Oats

Add or extend tests for:
- dependency-aware branch ancestry planning
- multi-dependency branch-parent resolution
- run-owned feature branch reuse across resumes
- persisted task PR and final PR snapshots
- operation-history event emission
- conflict-resolution retry paths

### legacy orchestration artifact handling

Add tests for:
- `run_id` propagation into local flow-run metadata
- task checkpoint persistence of branch / PR state
- resume behavior that reuses task worktrees and branches instead of recreating them

### Backend

Add tests for:
- orchestration response shaping with feature-branch and PR graph objects
- runtime versus record precedence for branch / PR state
- merge and conflict operation normalization
- node badge rollups and final-review readiness

### Frontend

Add tests for:
- normalization of new orchestration response fields
- run-card status summaries
- DAG node git / PR badges
- stacked-PR inspector rendering
- selection sync between DAG nodes and PR-stack records

## Rollout Strategy

### Phase 1: Oats runtime contracts

Implement the additive v2 models, planner changes, runtime persistence, and PR operation recording.

### Phase 2: legacy orchestration attempt integration

Propagate `run_id`, persist branch / PR attempt snapshots, and make resume semantics reuse the same stack.

### Phase 3: Backend and UI

Extend orchestration schemas, normalize the new graph, and add the stacked-PR UI.

### Phase 4: Derived analytics

Treat derived analytics as an explicitly later follow-on after the first implementation plan completes the orchestration control plane.

## Open Questions Resolved By This Design

- Source of truth: Oats and legacy orchestration artifacts, not live GitHub state.
- Merge operator: Codex CLI sessions.
- Conflict handling: automatic conflict-resolution step before surfacing blocked state.
- Final gate: manual human approval on the feature PR to `main`.
- Resume semantics: one Oats run owns one long-lived feature branch stack across legacy orchestration resumes.
