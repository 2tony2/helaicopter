# Oats Graph-Native Runtime v2 Design

**Date:** 2026-03-25
**Status:** Draft
**Supersedes:** `specs/2026-03-20-claude-code-orchestrator-design.md`, updates `specs/2026-03-20-oats-stacked-pr-orchestration-design.md`

## Executive Summary

Oats v1 orchestrates small task lists with flat dependency arrays and a best-effort execution loop. That was sufficient for 3–5 task stacked-PR runs. It is not sufficient for what we actually need: 10–30 task graphs where Claude and Codex sessions produce new sub-tasks at runtime, where dependencies carry typed contracts (code-ready, PR-merged, review-approved), where interrupted runs resume from durable checkpoints, and where the backend and UI render the live graph as a first-class control surface.

This v2 design promotes the **task graph** from an implementation detail to the central runtime abstraction. Every run is a directed acyclic graph of typed nodes connected by typed dependency edges. The runtime is a ready-queue scheduler that evaluates edge predicates to determine which tasks are executable. Tasks can discover and insert new nodes into the graph mid-run. Every entity — run, task, session, attempt, operation, PR — carries a durable identity that propagates from Oats CLI through the backend API to the frontend UI.

Prefect is gone (removed 2026-03-23). The superseded Claude Code orchestrator design (2026-03-20) proposed replacing Oats with SQLite tables — that path is abandoned. Oats remains the orchestration engine. `.oats/runtime/` remains the state store, but is now structured as a graph-native control plane rather than a flat task list with JSON snapshots.

## Goals

- **Graph-native runtime model:** The task DAG with typed edges is the primary data structure. All scheduling, readiness, and state transitions derive from graph evaluation.
- **Typed dependency edges:** Dependencies are not just "task A before task B" — they carry a predicate (`code_ready`, `pr_merged`, `checks_passing`, `review_approved`) that the ready-queue evaluates.
- **Ready-queue scheduling:** A ready-work queue replaces the current "iterate tasks and check status" loop. Tasks enter the queue when all inbound edge predicates are satisfied.
- **Dynamic graph mutation:** Running tasks (Claude/Codex sessions) can discover sub-tasks and insert them into the live graph via a structured discovery protocol. The graph grows during execution.
- **Execution envelopes:** Each Claude/Codex invocation is wrapped in a typed envelope that captures the agent type, model, session identity, resource limits, retry policy, and output contract.
- **Durable identifiers:** `run_id`, `task_id`, `session_id`, `attempt_id`, `operation_id`, and `pr_id` are stable, propagated through every layer, and never reused.
- **Retry, recovery, and interruption:** Task failure, session timeout, and run interruption are first-class control-plane concerns with explicit state machines and configurable policies.
- **Backend and UI as graph surfaces:** The API exposes the typed graph, not a flattened task list. The UI renders the DAG with edge types, ready-queue state, and live execution status.
- **Larger task graphs:** 10–30 node runs with multi-level dependency chains, discovered sub-tasks, and concurrent execution across multiple worktrees.

## Non-Goals

- Reintroducing Prefect or any external workflow engine.
- Replacing `.oats/runtime/` with a database-primary control plane. (The file-based store is the right choice for a CLI-first tool that operates in git repos.)
- Auto-merging the final feature PR into `main`.
- Supporting repo policy variations beyond merge-commit-only in the first rollout.
- Building a persistent daemon — refresh/resume remain explicit actions.
- Replacing OATS with Beads or any other framework. This is a Beads-inspired redesign of OATS internals.

## Core Concepts

### The Task Graph

A run is a DAG `G = (V, E)` where:

- **V (nodes)** are tasks. Each task has a `task_id`, a `kind` (implementation, review, merge, verification, meta), a `status`, and an execution envelope.
- **E (edges)** are typed dependencies. Each edge `(u, v, predicate)` means "task v cannot enter the ready queue until predicate(u) is true."

The graph is the single source of truth for scheduling. There is no separate "task list" — the list view is a topological projection of the graph.

### Typed Dependency Edges

| Edge predicate | Meaning | Satisfied when |
|---|---|---|
| `code_ready` | Upstream task has pushed code to its branch | Task status is `succeeded` and branch exists with commits |
| `pr_created` | Upstream task has an open PR | `task_pr` is non-null with state `open` |
| `pr_merged` | Upstream task's PR is merged into its target | `task_pr.merge_gate_status == "merged"` |
| `checks_passing` | Upstream task's PR has all checks green | `task_pr.checks_summary.all_passing == True` |
| `review_approved` | Upstream task's PR has approving review | `task_pr.review_summary.approved == True` |
| `artifact_ready` | Upstream task has produced a named artifact | Named artifact exists in task output |

Edge predicates are evaluated by the ready-queue on every state transition. A task enters the ready queue when **all** inbound edges are satisfied.

### Ready-Queue Scheduler

The execution loop is a ready-queue, not a status-scanning loop:

```
ready_queue: PriorityQueue[Task]  # priority = topological depth, then task priority

while not graph.is_terminal():
    # Drain completions
    for completed in poll_running_tasks():
        graph.record_completion(completed)
        graph.evaluate_outbound_edges(completed)  # may enqueue dependents
        if completed.has_discovered_tasks():
            graph.insert_discovered_tasks(completed.discovered)

    # Fill execution slots
    while ready_queue and running_count < concurrency_limit:
        task = ready_queue.pop()
        envelope = build_execution_envelope(task)
        spawn_agent(task, envelope)
        running_count += 1

    # Wait for next event
    wait_for_completion_or_timeout()
```

Key difference from v1: tasks are **pushed into the ready queue by edge evaluation**, not pulled by scanning. This is O(degree) per completion instead of O(|V|).

### Dynamic Discovered-Task Insertion

A running Claude or Codex session may determine that a task requires sub-tasks not present in the original plan. The discovery protocol:

1. **Agent writes a discovery file** to a well-known path in its worktree: `.oats/discovered/<parent_task_id>.json`.
2. **Discovery file schema:**
   ```json
   {
     "discovered_by": "task_id",
     "tasks": [
       {
         "task_id": "generated-unique-id",
         "title": "Extract shared auth middleware",
         "description": "...",
         "kind": "implementation",
         "dependencies": [{"task_id": "parent_task_id", "predicate": "code_ready"}],
         "execution": {"agent": "codex", "model": "o3-pro"}
       }
     ],
     "edges_to_add": [
       {"from": "generated-unique-id", "to": "existing_task_id", "predicate": "code_ready"}
     ]
   }
   ```
3. **On task completion**, the runtime checks for discovery files, validates the sub-graph (no cycles, no duplicate IDs, all referenced tasks exist), and **inserts the new nodes and edges into the live graph**.
4. **Inserted tasks immediately participate in ready-queue evaluation.** If their dependencies are already satisfied, they enter the queue on the next cycle.
5. **The original plan is not mutated** — `plan.json` is the initial snapshot. The live graph in `state.json` is the authoritative structure. A `graph_mutations` log records all insertions with timestamps and provenance.

### Durable Identifiers

Every entity has a stable, unique identifier that propagates through all layers:

| Entity | ID format | Generated by | Stored in | Propagated to |
|---|---|---|---|---|
| Run | `run_<ulid>` | `oats run` | `state.json` | Backend API, frontend, events |
| Task | `task_<slug>` (from spec) or `task_<ulid>` (discovered) | Planner or discovery | `state.json` graph nodes | Backend API, frontend, agent envelope |
| Session | `sess_<ulid>` | Runner on agent spawn | Execution envelope, `state.json` | Backend API, frontend, agent context |
| Attempt | `att_<ulid>` | Runner on each try | `state.json` task attempts | Backend API, frontend |
| Operation | `op_<ulid>` | PR/merge/retarget handler | Operation history | Backend API, frontend |
| PR | `pr_<owner>/<repo>#<number>` | PR creation handler | `state.json` task PR | Backend API, frontend |

IDs are never reused. A retried task gets a new `attempt_id` but keeps its `task_id`. A re-created PR gets a new `pr_id` but the task keeps its `task_id`. The frontend can link any entity back to its origin.

### Execution Envelopes

Each agent invocation is described by an execution envelope:

```python
class ExecutionEnvelope(BaseModel):
    session_id: str                          # sess_<ulid>
    attempt_id: str                          # att_<ulid>
    task_id: str                             # task being executed
    run_id: str                              # parent run
    agent: AgentType                         # claude | codex
    model: str                               # claude-sonnet-4-6, o3-pro, etc.
    reasoning_effort: str | None             # high, medium, low (Codex)
    worktree_path: str                       # isolated git worktree
    parent_branch: str                       # branch to base work on
    timeout_seconds: int                     # hard timeout for this attempt
    max_output_tokens: int | None            # token budget
    retry_policy: RetryPolicy                # max_attempts, backoff, transient_detection
    context: dict                            # task description, dependencies, discovered context
    output_contract: OutputContract          # what the agent must produce (code, pr, artifact)
    discovery_enabled: bool                  # whether agent can discover sub-tasks
```

The envelope is persisted in `state.json` per attempt. This means any attempt can be inspected, replayed, or compared after the fact.

### Retry, Recovery, and Interruption

**Task-level retry:**
- Each task has a `RetryPolicy`: `max_attempts` (default 3), `backoff_seconds` (default [30, 120, 300]), `transient_patterns` (regexes for retryable errors).
- On failure, the runtime checks if the error matches a transient pattern and the attempt budget is not exhausted. If so, a new attempt is enqueued after backoff.
- Non-transient failures immediately mark the task as `failed`. Downstream tasks transition to `blocked_by_failure`.

**Run interruption and resume:**
- `SIGINT` or `SIGTERM` triggers graceful shutdown: running agents are sent `SIGTERM`, the runtime waits up to 30s for completion, then persists current state.
- `oats resume <run_id>` reloads the graph, re-evaluates all edges, rebuilds the ready queue, and continues execution. No work is lost — the last persisted state is the checkpoint.
- A run can be interrupted and resumed any number of times. The `interruption_history` in `state.json` records each interruption with timestamp, reason, and running task states at the time.

**Session timeout:**
- Each execution envelope has a `timeout_seconds`. If an agent session exceeds this, the runtime kills the process, records a timeout attempt, and applies retry policy.
- Heartbeat monitoring detects stale sessions (no stdout/stderr for `heartbeat_timeout_seconds`). Stale sessions are killed and retried.

**Conflict resolution:**
- Merge conflicts trigger a dedicated conflict-resolution task (kind: `merge`) that is inserted into the graph with a `pr_merged` edge back to the conflicting task.
- Conflict resolution has its own retry budget (`max_conflict_retries`, default 3). Exhaustion transitions the run's `stack_status` to `blocked`.

## Persisted Data Model

### RunRuntimeState (contract: `oats-runtime-v2`)

```python
class RunRuntimeState(BaseModel):
    contract: str = "oats-runtime-v2"
    run_id: str                              # run_<ulid>
    title: str
    status: RunStatus                        # pending|running|completed|failed|timed_out|interrupted
    stack_status: StackStatus | None
    feature_branch: FeatureBranchState | None
    final_pr: FinalPullRequestSnapshot | None
    active_operation: ActiveOperation | None

    # The live task graph — this is the authoritative structure
    graph: TaskGraph                         # nodes: list[TaskNode], edges: list[TypedEdge]
    graph_mutations: list[GraphMutation]     # insertions from discovered tasks

    # Flattened view for backward compat and simple queries
    tasks: list[TaskRuntimeRecord]

    ready_queue_snapshot: list[str]          # task_ids currently in ready queue
    interruption_history: list[InterruptionRecord]

    started_at: datetime | None
    finished_at: datetime | None
    last_checkpoint_at: datetime | None
```

### TaskGraph

```python
class TaskNode(BaseModel):
    task_id: str
    kind: TaskKind                           # implementation|review|merge|verification|meta
    title: str
    status: TaskRuntimeStatus
    execution_envelope: ExecutionEnvelope | None
    attempts: list[AttemptRecord]
    discovered_by: str | None                # task_id that discovered this node, if any

class TypedEdge(BaseModel):
    from_task: str
    to_task: str
    predicate: EdgePredicate                 # code_ready|pr_created|pr_merged|checks_passing|review_approved|artifact_ready
    satisfied: bool
    satisfied_at: datetime | None

class GraphMutation(BaseModel):
    mutation_id: str                         # mut_<ulid>
    kind: str                                # insert_tasks|add_edges|remove_edges
    discovered_by: str                       # task_id
    timestamp: datetime
    nodes_added: list[str]                   # task_ids
    edges_added: list[TypedEdge]
```

### TaskRuntimeRecord (extended)

```python
class TaskRuntimeRecord(BaseModel):
    task_id: str
    title: str
    kind: TaskKind
    status: TaskRuntimeStatus                # pending|queued|running|succeeded|failed|blocked|blocked_by_failure
    parent_branch: str
    branch_strategy: BranchStrategy
    repo_context: TaskRepoContext | None
    branch_snapshot: BranchSnapshot | None
    task_pr: TaskPullRequestSnapshot | None
    operation_history: list[OperationHistoryEntry]
    attempts: list[AttemptRecord]            # all attempts with envelope, outcome, duration
    retry_policy: RetryPolicy
    discovered_by: str | None                # if this task was dynamically inserted
    discovered_tasks: list[str]              # task_ids this task discovered
```

### AttemptRecord

```python
class AttemptRecord(BaseModel):
    attempt_id: str                          # att_<ulid>
    session_id: str                          # sess_<ulid>
    envelope: ExecutionEnvelope
    status: AttemptStatus                    # running|succeeded|failed|timed_out|killed
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    exit_code: int | None
    error_summary: str | None
    is_transient: bool | None                # whether failure matched transient pattern
    stdout_path: str | None                  # path to captured output
    stderr_path: str | None
```

### OperationHistoryEntry (extended)

```python
class OperationHistoryEntry(BaseModel):
    operation_id: str                        # op_<ulid>
    kind: OperationKind                      # pr_create|pr_merge|pr_retarget|conflict_resolution|graph_mutation|...
    status: OperationStatus                  # started|succeeded|failed
    timestamp: datetime
    session_id: str | None                   # agent session that triggered this
    attempt_id: str | None                   # attempt context
    details: dict                            # operation-specific payload
```

## Artifact Layout

```
.oats/
├── config.toml                              # repo policy + concurrency + retry defaults
└── runtime/
    └── <run_id>/
        ├── state.json                       # RunRuntimeState with full graph (atomic writes)
        ├── events.jsonl                     # append-only audit trail
        ├── plan.json                        # initial ExecutionPlan snapshot (immutable)
        ├── graph_mutations.jsonl            # append-only log of dynamic graph changes
        ├── invocations/
        │   └── <session_id>/
        │       ├── envelope.json            # execution envelope for this session
        │       ├── stdout.log               # captured agent output
        │       └── stderr.log               # captured agent errors
        └── discovered/
            └── <task_id>.json               # discovery files written by agents
```

## Architecture

### Component model

```
┌─────────────────────────────────────────────────────────────────┐
│  superpowers:orchestrate-run  (thin dispatch surface)           │
│  Parses run spec → invokes `oats run` / `oats resume`          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  Oats CLI  (graph-native orchestration runtime)                 │
│                                                                 │
│  plan → run → resume → refresh → watch                          │
│                                                                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────┐  │
│  │ parser     │ │ graph      │ │ scheduler  │ │ pr          │  │
│  │            │ │            │ │            │ │             │  │
│  │ markdown   │ │ DAG build  │ │ ready-queue│ │ gh CLI      │  │
│  │ spec       │ │ typed edges│ │ edge eval  │ │ PR ops      │  │
│  │ parsing    │ │ branch     │ │ envelope   │ │ merge       │  │
│  │            │ │ ancestry   │ │ dispatch   │ │ retarget    │  │
│  └────────────┘ └────────────┘ └────────────┘ └─────────────┘  │
│                                                                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────────────┐  │
│  │ discovery  │ │ retry      │ │ runtime_state              │  │
│  │            │ │            │ │                            │  │
│  │ sub-task   │ │ policy     │ │ atomic JSON + JSONL writes │  │
│  │ insertion  │ │ evaluation │ │ graph checkpoint           │  │
│  │ validation │ │ backoff    │ │ interruption handling      │  │
│  └────────────┘ └────────────┘ └────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  Helaicopter Backend  (graph-aware API)                         │
│                                                                 │
│  GET  /orchestration/runs              → list runs with summary │
│  GET  /orchestration/runs/{id}         → full graph + state     │
│  GET  /orchestration/runs/{id}/graph   → typed DAG for render   │
│  POST /orchestration/runs/{id}/refresh → trigger oats refresh   │
│  POST /orchestration/runs/{id}/resume  → trigger oats resume    │
│  GET  /orchestration/runs/{id}/task/{task_id}/attempts → attempt│
│  GET  /orchestration/runs/{id}/events  → paginated event stream │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  Helaicopter Frontend  (graph-native orchestration UI)          │
│                                                                 │
│  Run list → Run detail → Live DAG → Task inspector              │
│  Edge-type color coding / ready-queue highlight / attempt drill  │
│  Refresh / resume / cancel actions via backend POST routes      │
│  Discovered-task visual distinction (dashed border)             │
└─────────────────────────────────────────────────────────────────┘
```

### Execution Flow

#### `oats run <spec.md>`

1. **Parse** the markdown run spec → extract tasks, dependencies, agent assignments.
2. **Build the task graph** — create `TaskNode` and `TypedEdge` objects. Validate acyclicity. Assign branch ancestry via `stacked_prs.py`.
3. **Initialize runtime state** — create `RunRuntimeState` with the full graph. Persist `state.json` and `plan.json`.
4. **Seed the ready queue** — evaluate all edges; tasks with no inbound edges (or all edges satisfied) enter the queue.
5. **Execute the ready-queue loop:**
   - Pop tasks from the queue up to `concurrency_limit`.
   - Build execution envelope per task.
   - Spawn agent subprocess in task worktree.
   - On completion: record attempt, evaluate outbound edges, process discoveries, checkpoint state.
   - On failure: apply retry policy. Transient → re-enqueue after backoff. Fatal → mark failed, propagate `blocked_by_failure` to descendants.
   - On timeout: kill session, record timeout attempt, apply retry policy.
6. **PR operations** after successful task execution: create task PR, persist snapshot, re-evaluate edges that depend on `pr_created`.
7. **Checkpoint** state after every task completion or failure (atomic write to `state.json`).
8. **Terminal** when the ready queue is empty and no tasks are running. Print summary and guidance.

#### `oats refresh <run_id>`

1. Load graph from `state.json`.
2. For each task with a PR: fetch current GitHub state, update snapshot.
3. Re-evaluate all edges — `pr_merged`, `checks_passing`, `review_approved` edges may now be satisfied.
4. For newly merge-ready PRs in topological order: execute merge, retarget children, re-evaluate edges.
5. If all task PRs merged: create final PR, set `stack_status = "ready_for_final_review"`.
6. Checkpoint state.

#### `oats resume <run_id>`

1. Run `refresh` logic first.
2. Rebuild the ready queue from current graph state.
3. Re-queue failed tasks within retry budget.
4. Transition `blocked` multi-dependency tasks to `pending` if upstream PRs are now merged.
5. Re-enter the execution loop.

#### `oats watch <run_id>`

Read-only. Continuously poll `state.json` and print graph status, ready queue contents, running tasks, and recent events.

### Concurrency Model

Agent invocations run as subprocesses, each in an isolated git worktree. The ready-queue scheduler enforces `concurrency_limit` from `.oats/config.toml`. The scheduler is cooperative — it polls for completions and heartbeats, not preemptive.

### Merge-Gated Multi-Dependency Tasks

A task with multiple dependencies and `branch_strategy = "after_dependency_merges"`:

1. Has inbound edges with `predicate = "pr_merged"` from each dependency.
2. Cannot enter the ready queue until **all** inbound `pr_merged` edges are satisfied.
3. When all are satisfied, the task gets `parent_branch = feature_branch` (since all upstream code is now merged into it) and enters the ready queue.

This is a natural consequence of the typed-edge model — no special-case code needed.

## Backend API Design

### Response Models

The API exposes the graph structure, not just a flat task list:

```python
class RunGraphResponse(BaseModel):
    run_id: str
    title: str
    status: RunStatus
    stack_status: StackStatus | None
    feature_branch: FeatureBranchResponse | None
    final_pr: FinalPRResponse | None
    active_operation: ActiveOperationResponse | None

    # Graph structure for DAG rendering
    nodes: list[TaskNodeResponse]
    edges: list[TypedEdgeResponse]

    # Scheduling state
    ready_queue: list[str]                   # task_ids
    running_tasks: list[str]                 # task_ids

    # Metadata
    graph_mutation_count: int
    interruption_count: int
    started_at: str | None
    finished_at: str | None
    last_checkpoint_at: str | None

class TaskNodeResponse(BaseModel):
    task_id: str
    kind: str
    title: str
    status: str
    agent: str | None
    model: str | None
    attempt_count: int
    last_attempt_status: str | None
    last_attempt_duration_seconds: float | None
    pr: TaskPRResponse | None
    operation_count: int
    discovered_by: str | None
    discovered_task_count: int

class TypedEdgeResponse(BaseModel):
    from_task: str
    to_task: str
    predicate: str
    satisfied: bool
```

### Routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/orchestration/runs` | List all runs with summary (status, task count, stack status) |
| `GET` | `/orchestration/runs/{run_id}` | Full run detail with graph, all task nodes, all edges |
| `GET` | `/orchestration/runs/{run_id}/graph` | Typed DAG optimized for frontend rendering |
| `GET` | `/orchestration/runs/{run_id}/events` | Paginated event stream from `events.jsonl` |
| `GET` | `/orchestration/runs/{run_id}/tasks/{task_id}` | Task detail with all attempts and operation history |
| `GET` | `/orchestration/runs/{run_id}/tasks/{task_id}/attempts/{attempt_id}` | Single attempt detail with envelope and logs |
| `POST` | `/orchestration/runs/{run_id}/refresh` | Trigger `oats refresh`, return updated graph |
| `POST` | `/orchestration/runs/{run_id}/resume` | Trigger `oats resume`, return updated graph |

### Normalization Rules

- Read `state.json` directly from `.oats/runtime/<run_id>/`.
- Expose the `TaskGraph` as `nodes` + `edges` arrays — the frontend does layout.
- Include `ready_queue_snapshot` so the UI can highlight executable tasks.
- Expose `graph_mutation_count` and `discovered_by` so the UI can distinguish original vs. discovered tasks.
- Carry durable IDs (`session_id`, `attempt_id`, `operation_id`) through to every response object.
- Expose staleness metadata: `last_checkpoint_at` on runs, `last_github_fetch_at` on PR snapshots.

## UI Design

### Run List

- Run title, feature branch, stack status badge.
- Task count breakdown: `{succeeded}/{total}` with discovered tasks shown as `+{discovered}`.
- Ready queue indicator: `{n} tasks ready` when run is active.
- Last activity timestamp.

### Run Detail: Live DAG

- **Graph rendering** with nodes as task cards and edges as typed arrows.
- **Edge color coding:** `code_ready` = blue, `pr_merged` = green, `checks_passing` = yellow, `review_approved` = purple. Satisfied edges are solid; unsatisfied are dashed.
- **Ready-queue highlight:** tasks in the ready queue get a glowing border.
- **Discovered tasks** rendered with dashed border and a "discovered by {parent}" label.
- **Running tasks** show a progress indicator and current attempt duration.
- **Failed tasks** show attempt count and last error summary on hover.

### Task Inspector (sidebar)

- Task title, kind, status, agent/model.
- Attempt timeline: each attempt as a row with status, duration, session link.
- Operation history: PR create, merge, retarget, conflict resolution events with timestamps.
- Inbound/outbound edges with predicate and satisfaction status.
- If discovered: link to discovering task. If discoverer: list of discovered tasks.

### Actions

- **Refresh** button (enabled when `stack_status` is not `completed`).
- **Resume** button (enabled when there are failed/blocked tasks within retry budget).
- Both invoke backend POST routes and update the graph on response.

## Testing Strategy

### Oats Runtime (Python)

| Test area | Coverage |
|---|---|
| `test_task_graph.py` | Graph construction, typed edge creation, cycle detection, topological ordering, edge predicate evaluation |
| `test_ready_queue.py` | Ready-queue seeding, edge-driven enqueue, concurrency limiting, priority ordering |
| `test_discovery.py` | Discovery file parsing, graph insertion validation, cycle rejection, edge addition, provenance tracking |
| `test_execution_envelope.py` | Envelope construction, retry policy defaults, timeout propagation |
| `test_retry_recovery.py` | Transient detection, backoff scheduling, budget exhaustion, `blocked_by_failure` propagation |
| `test_interruption.py` | SIGINT handling, state checkpoint on interrupt, resume from checkpoint |
| `test_stacked_prs.py` | Branch ancestry with typed edges, multi-dependency merge gating |
| `test_pr_actions.py` | Refresh/resume with edge re-evaluation, merge ordering, retargeting |
| `test_durable_ids.py` | ID generation, propagation through state, no reuse across retries |

### Backend (Python)

| Test area | Coverage |
|---|---|
| `test_api_orchestration_graph.py` | Graph response shape, edge types in payload, ready-queue exposure |
| `test_api_orchestration_actions.py` | Refresh/resume routes, 404 for unknown runs, concurrent refresh guard |
| `test_api_orchestration_detail.py` | Task detail with attempts, operation history, discovered task links |

### Frontend (TypeScript)

| Test area | Coverage |
|---|---|
| `normalize.test.ts` | Graph normalization, edge type mapping, discovered task flagging |
| `mutations.test.ts` | Refresh/resume request/response, error handling |
| `oats-graph-view-model.test.ts` | Node layout hints, edge coloring, ready-queue highlighting, attempt summaries |
| `oats-task-inspector.test.ts` | Attempt timeline, operation history, edge detail |

## Rollout Strategy

### Phase 1: Graph Runtime Core

Introduce the `TaskGraph`, `TypedEdge`, and `GraphMutation` models. Refactor the execution loop from status-scanning to ready-queue scheduling. Implement execution envelopes and durable ID generation. Wire retry/recovery state machine. Ensure existing runs still work — the graph is built from the existing dependency arrays with default `code_ready` edge predicates.

### Phase 2: Dynamic Discovery

Implement the discovered-task protocol: discovery file schema, graph insertion with validation, provenance tracking, `graph_mutations.jsonl` logging. Test with a multi-level discovery scenario (task discovers sub-tasks that themselves have dependencies).

### Phase 3: Backend Graph API

Expose the typed graph through the API. New response models with nodes, edges, ready queue, graph mutations. Durable ID propagation through all response objects. Attempt and operation detail endpoints.

### Phase 4: Frontend Graph UI

DAG rendering with typed edges, ready-queue highlighting, discovered-task visual treatment. Task inspector with attempt timeline and operation history. Refresh/resume action buttons.

### Phase 5: Large-Graph Verification

End-to-end testing with 15–30 node graphs including multi-level dependencies, dynamic discovery, concurrent execution, interruption/resume cycles, and conflict resolution. Performance validation of ready-queue evaluation and state checkpoint under load.

## Migration Notes

### From v1 task lists to v2 graphs

The v1 `tasks` array with `dependencies: list[str]` maps directly to a graph with `code_ready` edges. The migration is:

1. For each task in `tasks`, create a `TaskNode`.
2. For each `dep` in `task.dependencies`, create a `TypedEdge(from=dep, to=task.task_id, predicate="code_ready")`.
3. The `tasks` array is retained as a flattened view for backward compatibility — it is derived from the graph, not the source of truth.

Existing `state.json` files without a `graph` field are auto-migrated on load.

### From the superseded orchestrator design

The Claude Code orchestrator design proposed SQLite tables as the primary store. That path is abandoned. All orchestration state stays in `.oats/runtime/` artifacts. The `helaicopter_db` package has no orchestration tables.

### Residual Prefect references

Any remaining Prefect references in Oats Python code must be removed as part of Phase 1.
