# Oats Graph-Native Runtime v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Oats runtime around a graph-native execution model with typed dependency edges, ready-queue scheduling, dynamic task discovery, durable identifiers, execution envelopes, and explicit retry/recovery semantics. Expose the typed graph through the backend API and render it as a first-class UI surface.

**Architecture:** Single-process Oats CLI runtime backed by `.oats/runtime/<run_id>/` artifacts. The task DAG with typed edges is the central data structure. A ready-queue scheduler replaces the status-scanning loop. Claude/Codex sessions can discover and insert sub-tasks at runtime. Every entity carries a durable identifier from CLI through API to UI.

**Supersedes:** `plans/2026-03-20-oats-stacked-pr-orchestration.md`

**Design spec:** `specs/2026-03-25-oats-graph-native-runtime-v2-design.md`

**Tech Stack:** Python 3.13, Typer, Pydantic, FastAPI, Next.js 16, React 19, SWR, `pytest`, `node:test`, `tsx`, ESLint

---

## Current Implementation State

The v1 model is partially implemented across three layers. This plan treats it as legacy to be migrated, not hardened.

**Oats runtime (legacy — to be restructured):**
- `models.py` — flat `RunRuntimeState` with `tasks: list[TaskRuntimeRecord]`. No graph, no typed edges, no execution envelopes, no attempt records. (428 lines)
- `stacked_prs.py` — branch ancestry derivation (correct, retained)
- `planner.py` — dependency-aware branch planning (correct, extended for graph construction)
- `pr.py` — refresh/resume flows, merge ordering (correct, extended for edge re-evaluation)
- `runtime_state.py` — atomic state persistence (correct, extended for graph checkpointing)
- `cli.py` — full command surface (1431 lines, execution loop to be replaced with ready-queue)
- `runner.py` — agent invocation (extended for execution envelopes)

**Backend (partial — to be restructured):**
- `schema/orchestration.py` — flat task list schema. Needs graph response models.
- `application/orchestration.py` — flat normalization. Needs graph-aware normalization.
- Refresh/resume routes exist but return flat payloads.

**Frontend (partial — to be restructured):**
- `types.ts`, `normalize.ts` — flat task types. Need graph types.
- `oats-view-model.ts` — flat summaries. Needs graph-aware view model.
- `oats-pr-stack.tsx` — stacked-PR inspector (retained, extended).

## File Structure

**New (Oats runtime):**
- `python/oats/graph.py` — `TaskGraph`, `TaskNode`, `TypedEdge`, `GraphMutation` models and graph operations (build, validate, insert, evaluate edges)
- `python/oats/scheduler.py` — ready-queue scheduler with edge-driven enqueue and concurrency limiting
- `python/oats/envelope.py` — `ExecutionEnvelope`, `RetryPolicy`, `OutputContract` construction
- `python/oats/discovery.py` — discovered-task protocol: parse, validate, insert into live graph
- `python/oats/identity.py` — durable ID generation (`run_<ulid>`, `task_<slug|ulid>`, `sess_<ulid>`, `att_<ulid>`, `op_<ulid>`)

**Modify (Oats runtime):**
- `python/oats/models.py` — add `TaskGraph`, `AttemptRecord`, `ExecutionEnvelope` to `RunRuntimeState`; add `kind`, `attempts`, `retry_policy`, `discovered_by` to `TaskRuntimeRecord`
- `python/oats/cli.py` — replace status-scanning execution loop with ready-queue scheduler; add interruption handling
- `python/oats/runner.py` — accept execution envelope, return structured attempt result
- `python/oats/runtime_state.py` — persist/load graph, graph mutations, interruption history; derive `stack_status` on cold-load
- `python/oats/pr.py` — re-evaluate typed edges after PR state changes; conflict retry budget
- `python/oats/planner.py` — build `TaskGraph` with typed edges from spec dependencies

**Modify (backend):**
- `python/helaicopter_api/schema/orchestration.py` — `RunGraphResponse`, `TaskNodeResponse`, `TypedEdgeResponse`, attempt/operation detail models
- `python/helaicopter_api/application/orchestration.py` — graph-aware normalization with durable IDs
- `python/helaicopter_api/application/oats_run_actions.py` — error handling, concurrent refresh guard
- `python/helaicopter_api/router/orchestration.py` — graph endpoint, task detail endpoint, events endpoint

**Modify (frontend):**
- `src/lib/types.ts` — graph types: `TaskNode`, `TypedEdge`, `AttemptRecord`, `GraphMutation`
- `src/lib/client/normalize.ts` — graph normalization, edge type mapping, discovered task flagging
- `src/lib/client/normalize.test.ts` — graph normalization tests
- `src/lib/client/mutations.ts` — refresh/resume client mutations
- `src/lib/client/mutations.test.ts` — mutation tests
- `src/components/orchestration/oats-view-model.ts` → rename/restructure to `oats-graph-view-model.ts` — graph-aware view model with edge coloring, ready-queue highlighting
- `src/components/orchestration/oats-pr-stack.tsx` — extend with attempt timeline, operation history
- `src/components/orchestration/overnight-oats-panel.tsx` — DAG rendering, action buttons, discovered-task treatment

**New (tests):**
- `tests/oats/test_task_graph.py` — graph construction, cycle detection, edge evaluation
- `tests/oats/test_scheduler.py` — ready-queue behavior, concurrency limiting, edge-driven enqueue
- `tests/oats/test_discovery.py` — discovery protocol, graph insertion, validation
- `tests/oats/test_envelope.py` — envelope construction, retry policy
- `tests/oats/test_retry_recovery.py` — transient detection, backoff, budget exhaustion, failure propagation
- `tests/oats/test_interruption.py` — SIGINT handling, checkpoint, resume from checkpoint
- `tests/oats/test_durable_ids.py` — ID generation, propagation, no reuse

**Modify (tests):**
- `tests/oats/test_stacked_prs.py` — extend for typed edges, multi-dependency merge gating with edge predicates
- `tests/oats/test_pr_actions.py` — extend for edge re-evaluation after merge, conflict retry budget
- `tests/test_api_orchestration.py` — graph response payloads, durable IDs in responses, new endpoints

**Implementation notes:**
- Use `@test-driven-development` for every task below.
- Use `@verification-before-completion` before claiming the feature is complete.
- Prefect is already removed — no Prefect cleanup needed.
- Keep derived analytics out of this plan.

---

### Task 1: Introduce Graph Runtime Model and Durable Identity System

**Why:** The entire redesign rests on the task graph as the central data structure. Without `TaskGraph`, `TypedEdge`, and durable ID generation, nothing else can be built. This task introduces the core types and proves they work with graph construction, validation, and edge evaluation — independent of the execution loop.

**Files:**
- New: `python/oats/graph.py`
- New: `python/oats/identity.py`
- Modify: `python/oats/models.py`
- New: `tests/oats/test_task_graph.py`
- New: `tests/oats/test_durable_ids.py`

- [ ] **Step 1: Write failing tests for graph construction, typed edges, and ID generation**

```python
# test_task_graph.py
def test_build_graph_from_spec_dependencies() -> None:
    """Build a TaskGraph from a spec with 5 tasks and mixed dependencies."""
    spec = build_test_spec(
        tasks=["auth", "models", "api", "dashboard", "e2e"],
        deps={"api": ["auth", "models"], "dashboard": ["api"], "e2e": ["dashboard", "api"]},
    )
    graph = TaskGraph.from_spec(spec)

    assert len(graph.nodes) == 5
    assert len(graph.edges) == 5
    assert all(e.predicate == EdgePredicate.CODE_READY for e in graph.edges)
    assert graph.is_acyclic()

def test_graph_rejects_cycle() -> None:
    """Inserting an edge that creates a cycle must raise."""
    graph = build_linear_graph(["a", "b", "c"])
    with pytest.raises(GraphCycleError):
        graph.add_edge(TypedEdge(from_task="c", to_task="a", predicate=EdgePredicate.CODE_READY))

def test_edge_predicate_evaluation() -> None:
    """Edge satisfaction changes based on task state."""
    graph = build_linear_graph(["a", "b"])
    edge = graph.edges_to("b")[0]

    assert not edge.satisfied
    graph.record_task_success("a")
    graph.evaluate_edges_from("a")
    assert edge.satisfied

def test_typed_edge_pr_merged_requires_pr_state() -> None:
    """A pr_merged edge is not satisfied by code_ready alone."""
    graph = TaskGraph()
    graph.add_node(TaskNode(task_id="a", kind=TaskKind.IMPLEMENTATION, title="A"))
    graph.add_node(TaskNode(task_id="b", kind=TaskKind.IMPLEMENTATION, title="B"))
    graph.add_edge(TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.PR_MERGED))

    graph.record_task_success("a")
    graph.evaluate_edges_from("a")
    edge = graph.edges_to("b")[0]
    assert not edge.satisfied  # code_ready is true but pr_merged requires PR merge

    graph.record_pr_merged("a")
    graph.evaluate_edges_from("a")
    assert edge.satisfied

def test_topological_order_respects_edge_types() -> None:
    """Topological sort of ready tasks accounts for edge predicates."""
    graph = build_diamond_graph()  # a -> b, a -> c, b -> d, c -> d
    order = graph.topological_order()
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")

# test_durable_ids.py
def test_id_generation_uniqueness() -> None:
    """Generated IDs are unique and correctly prefixed."""
    from oats.identity import generate_run_id, generate_task_id, generate_session_id, generate_attempt_id, generate_operation_id

    run_ids = {generate_run_id() for _ in range(100)}
    assert len(run_ids) == 100
    assert all(rid.startswith("run_") for rid in run_ids)

    sess_ids = {generate_session_id() for _ in range(100)}
    assert len(sess_ids) == 100
    assert all(sid.startswith("sess_") for sid in sess_ids)

def test_task_id_from_slug() -> None:
    """Task IDs from spec use slug format."""
    from oats.identity import task_id_from_slug
    assert task_id_from_slug("Auth Service Setup") == "task_auth-service-setup"

def test_task_id_for_discovered() -> None:
    """Discovered task IDs use ULID format."""
    from oats.identity import generate_discovered_task_id
    tid = generate_discovered_task_id()
    assert tid.startswith("task_")
    assert len(tid) > len("task_")
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run --group dev pytest tests/oats/test_task_graph.py tests/oats/test_durable_ids.py -q`

- [ ] **Step 3: Implement `graph.py` and `identity.py`; extend `models.py`**

Key implementation:
- `graph.py`: `TaskGraph` with `nodes: dict[str, TaskNode]`, `edges: list[TypedEdge]`. Methods: `from_spec()`, `add_node()`, `add_edge()` (with cycle check), `is_acyclic()`, `edges_to()`, `edges_from()`, `evaluate_edges_from()`, `record_task_success()`, `record_pr_merged()`, `topological_order()`, `ready_tasks()` (all inbound edges satisfied and status is pending).
- `identity.py`: ULID-based ID generators with correct prefixes. `task_id_from_slug()` for spec-derived tasks.
- `models.py`: Add `TaskGraph`, `TaskNode`, `TypedEdge`, `EdgePredicate`, `TaskKind`, `GraphMutation`, `AttemptRecord` to the model set. Add `graph: TaskGraph | None` and `graph_mutations: list[GraphMutation]` to `RunRuntimeState`. Add `kind`, `attempts`, `discovered_by` to `TaskRuntimeRecord`.

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run: `uv run --group dev pytest tests/oats/test_task_graph.py tests/oats/test_durable_ids.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/oats/graph.py python/oats/identity.py python/oats/models.py tests/oats/test_task_graph.py tests/oats/test_durable_ids.py
git commit -m "feat: introduce graph runtime model with typed edges and durable identity"
```

---

### Task 2: Ready-Queue Scheduler and Execution Envelopes

**Why:** The v1 execution loop scans all tasks on every iteration and checks status flags. The ready-queue scheduler is O(degree) per completion, supports typed edge predicates, and wraps each invocation in a structured envelope that enables retry, replay, and inspection.

**Files:**
- New: `python/oats/scheduler.py`
- New: `python/oats/envelope.py`
- New: `tests/oats/test_scheduler.py`
- New: `tests/oats/test_envelope.py`
- Modify: `python/oats/cli.py`
- Modify: `python/oats/runner.py`

- [ ] **Step 1: Write failing tests for ready-queue scheduling and envelope construction**

```python
# test_scheduler.py
def test_scheduler_seeds_ready_queue_from_graph() -> None:
    """Tasks with no inbound edges are immediately ready."""
    graph = build_diamond_graph()  # a -> b, a -> c, b -> d, c -> d
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=2)
    ready = scheduler.get_ready_tasks()
    assert [t.task_id for t in ready] == ["a"]

def test_scheduler_enqueues_dependents_after_completion() -> None:
    """Completing a task evaluates outbound edges and enqueues newly-ready dependents."""
    graph = build_diamond_graph()
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

    scheduler.mark_running("a")
    scheduler.record_completion("a", success=True)

    ready = scheduler.get_ready_tasks()
    assert set(t.task_id for t in ready) == {"b", "c"}

def test_scheduler_respects_concurrency_limit() -> None:
    """Cannot exceed concurrency_limit running tasks."""
    graph = build_wide_graph(width=10)  # 10 independent tasks
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=3)
    ready = scheduler.get_ready_tasks()
    assert len(ready) == 3

def test_scheduler_blocks_on_unsatisfied_pr_merged_edge() -> None:
    """A task behind a pr_merged edge does not become ready on code_ready alone."""
    graph = TaskGraph()
    graph.add_node(TaskNode(task_id="a", kind=TaskKind.IMPLEMENTATION, title="A"))
    graph.add_node(TaskNode(task_id="b", kind=TaskKind.IMPLEMENTATION, title="B"))
    graph.add_edge(TypedEdge(from_task="a", to_task="b", predicate=EdgePredicate.PR_MERGED))
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

    scheduler.mark_running("a")
    scheduler.record_completion("a", success=True)

    ready = scheduler.get_ready_tasks()
    assert len(ready) == 0  # b is not ready — pr_merged not satisfied

def test_scheduler_detects_terminal_state() -> None:
    """Scheduler is terminal when all tasks are succeeded/failed and nothing is running."""
    graph = build_linear_graph(["a", "b"])
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
    scheduler.mark_running("a")
    scheduler.record_completion("a", success=True)
    scheduler.mark_running("b")
    scheduler.record_completion("b", success=True)
    assert scheduler.is_terminal()

# test_envelope.py
def test_envelope_construction_from_task_and_config() -> None:
    """Execution envelope captures all required fields."""
    task = TaskNode(task_id="auth", kind=TaskKind.IMPLEMENTATION, title="Auth")
    config = RunConfig(agent="codex", model="o3-pro", timeout_seconds=600, max_attempts=3)
    envelope = build_execution_envelope(task, config, run_id="run_abc", worktree="/tmp/wt", parent_branch="feat/x")

    assert envelope.session_id.startswith("sess_")
    assert envelope.attempt_id.startswith("att_")
    assert envelope.task_id == "auth"
    assert envelope.run_id == "run_abc"
    assert envelope.agent == "codex"
    assert envelope.timeout_seconds == 600
    assert envelope.retry_policy.max_attempts == 3

def test_envelope_generates_unique_ids_per_attempt() -> None:
    """Each attempt for the same task gets a unique session_id and attempt_id."""
    task = TaskNode(task_id="auth", kind=TaskKind.IMPLEMENTATION, title="Auth")
    config = RunConfig(agent="claude", model="claude-sonnet-4-6", timeout_seconds=300, max_attempts=2)
    e1 = build_execution_envelope(task, config, run_id="run_abc", worktree="/tmp/wt1", parent_branch="feat/x")
    e2 = build_execution_envelope(task, config, run_id="run_abc", worktree="/tmp/wt2", parent_branch="feat/x")
    assert e1.session_id != e2.session_id
    assert e1.attempt_id != e2.attempt_id
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run --group dev pytest tests/oats/test_scheduler.py tests/oats/test_envelope.py -q`

- [ ] **Step 3: Implement scheduler and envelope modules; refactor CLI execution loop**

Key implementation:
- `scheduler.py`: `ReadyQueueScheduler` wrapping a `TaskGraph`. Maintains a priority queue (heapq by topological depth). `get_ready_tasks()` pops up to `available_slots` tasks. `record_completion()` evaluates outbound edges and enqueues newly-ready tasks. `is_terminal()` checks no running/pending/queued tasks remain.
- `envelope.py`: `build_execution_envelope()` constructs `ExecutionEnvelope` with fresh `session_id` and `attempt_id` from `identity.py`.
- `cli.py`: Replace the `while unfinished_tasks` loop with `while not scheduler.is_terminal()`. Use `scheduler.get_ready_tasks()` instead of scanning. Pass envelope to `runner.py`.
- `runner.py`: Accept `ExecutionEnvelope`, use it for timeout, model selection, and context injection.

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run: `uv run --group dev pytest tests/oats/test_scheduler.py tests/oats/test_envelope.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/oats/scheduler.py python/oats/envelope.py python/oats/cli.py python/oats/runner.py tests/oats/test_scheduler.py tests/oats/test_envelope.py
git commit -m "feat: ready-queue scheduler with typed edge evaluation and execution envelopes"
```

---

### Task 3: Retry, Recovery, and Interruption Handling

**Why:** v1 has a `max_task_attempts` counter but no transient-failure detection, no backoff, no `blocked_by_failure` propagation to descendants, and no graceful interruption with checkpoint. These are control-plane essentials for runs that take 30+ minutes and span 10+ concurrent agent sessions.

**Files:**
- Modify: `python/oats/scheduler.py`
- Modify: `python/oats/models.py`
- Modify: `python/oats/runtime_state.py`
- Modify: `python/oats/cli.py`
- New: `tests/oats/test_retry_recovery.py`
- New: `tests/oats/test_interruption.py`

- [ ] **Step 1: Write failing tests for retry semantics, failure propagation, and interruption**

```python
# test_retry_recovery.py
def test_transient_failure_triggers_retry_with_backoff() -> None:
    """A failure matching a transient pattern re-enqueues the task after backoff."""
    graph = build_linear_graph(["a", "b"])
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
    scheduler.mark_running("a")

    result = AttemptResult(
        status="failed",
        error_summary="Connection reset by peer",
        exit_code=1,
    )
    action = scheduler.record_completion("a", success=False, result=result)

    assert action.kind == "retry"
    assert action.backoff_seconds == 30  # first retry default backoff

def test_non_transient_failure_marks_failed_and_propagates() -> None:
    """A non-transient failure marks the task failed and blocks descendants."""
    graph = build_linear_graph(["a", "b", "c"])
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
    scheduler.mark_running("a")

    result = AttemptResult(status="failed", error_summary="SyntaxError in generated code", exit_code=1)
    action = scheduler.record_completion("a", success=False, result=result)

    assert action.kind == "fail"
    assert graph.nodes["b"].status == TaskRuntimeStatus.BLOCKED_BY_FAILURE
    assert graph.nodes["c"].status == TaskRuntimeStatus.BLOCKED_BY_FAILURE

def test_retry_budget_exhaustion() -> None:
    """After max_attempts failures, task is marked failed regardless of transience."""
    graph = build_single_task_graph("a", max_attempts=2)
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

    # Attempt 1
    scheduler.mark_running("a")
    scheduler.record_completion("a", success=False, result=transient_result())
    # Attempt 2
    scheduler.mark_running("a")
    action = scheduler.record_completion("a", success=False, result=transient_result())

    assert action.kind == "fail"
    assert graph.nodes["a"].status == TaskRuntimeStatus.FAILED

def test_conflict_retry_budget_blocks_stack() -> None:
    """After max_conflict_retries, stack_status transitions to blocked."""
    state = state_with_repeated_merge_conflicts(attempts=3, max_retries=3)
    refreshed = refresh_run(state=state, github_client=stub_conflict_client())

    assert refreshed.stack_status == "blocked"
    assert refreshed.active_operation is None

# test_interruption.py
def test_sigint_checkpoints_state_and_marks_interrupted() -> None:
    """SIGINT during execution persists current state and marks run interrupted."""
    graph = build_wide_graph(width=5)
    runtime = MockRuntime(graph, concurrency_limit=3)
    runtime.start_tasks(["t0", "t1", "t2"])

    runtime.simulate_sigint()

    state = runtime.load_persisted_state()
    assert state.status == RunStatus.INTERRUPTED
    assert len(state.interruption_history) == 1
    assert state.interruption_history[0].running_tasks == ["t0", "t1", "t2"]

def test_resume_from_interrupted_state_rebuilds_ready_queue() -> None:
    """Resuming an interrupted run rebuilds the ready queue and continues."""
    state = build_interrupted_state(
        completed=["a"],
        interrupted_running=["b"],  # was running at interruption
        pending=["c"],  # depends on b
    )
    scheduler = ReadyQueueScheduler.from_persisted_state(state)
    ready = scheduler.get_ready_tasks()

    # b should be re-queued (was running, not completed)
    assert "b" in [t.task_id for t in ready]
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run --group dev pytest tests/oats/test_retry_recovery.py tests/oats/test_interruption.py -q`

- [ ] **Step 3: Implement retry state machine, failure propagation, and interruption handling**

Key implementation:
- `scheduler.py`: `record_completion()` returns a `CompletionAction` (retry/fail/succeed). Transient detection via regex patterns in `RetryPolicy`. Backoff schedule. `blocked_by_failure` propagation to all reachable descendants.
- `models.py`: Add `BLOCKED_BY_FAILURE` to `TaskRuntimeStatus`. Add `InterruptionRecord` with timestamp, reason, running task snapshot. Add `interruption_history` to `RunRuntimeState`. Add `INTERRUPTED` to `RunStatus`.
- `runtime_state.py`: On `write_runtime_state()`, ensure atomic write even under signal. Add `checkpoint_on_signal()` handler.
- `cli.py`: Register SIGINT/SIGTERM handler that calls `checkpoint_on_signal()`, waits for running agents (up to 30s), then persists and exits. `resume` command: call `ReadyQueueScheduler.from_persisted_state()` to rebuild queue.
- `pr.py`: Conflict retry budget tracking, `stack_status = "blocked"` on exhaustion.

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run: `uv run --group dev pytest tests/oats/test_retry_recovery.py tests/oats/test_interruption.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/oats/scheduler.py python/oats/models.py python/oats/runtime_state.py python/oats/cli.py python/oats/pr.py tests/oats/test_retry_recovery.py tests/oats/test_interruption.py
git commit -m "feat: retry/recovery state machine with failure propagation and interruption handling"
```

---

### Task 4: Dynamic Discovered-Task Insertion

**Why:** The current model assumes the task graph is fully known at plan time. Real Claude/Codex runs discover sub-tasks: "this API endpoint needs a shared middleware extraction first." The graph must grow during execution while maintaining acyclicity and correct scheduling.

**Files:**
- New: `python/oats/discovery.py`
- Modify: `python/oats/graph.py`
- Modify: `python/oats/scheduler.py`
- Modify: `python/oats/models.py`
- New: `tests/oats/test_discovery.py`

- [ ] **Step 1: Write failing tests for task discovery, graph insertion, and validation**

```python
# test_discovery.py
def test_parse_discovery_file() -> None:
    """Discovery file is parsed into validated task and edge objects."""
    raw = {
        "discovered_by": "api",
        "tasks": [
            {"task_id": "task_extract-middleware", "title": "Extract shared auth middleware",
             "kind": "implementation", "dependencies": [{"task_id": "api", "predicate": "code_ready"}],
             "execution": {"agent": "codex", "model": "o3-pro"}}
        ],
        "edges_to_add": [
            {"from": "task_extract-middleware", "to": "dashboard", "predicate": "code_ready"}
        ],
    }
    discovery = parse_discovery_file(raw)
    assert len(discovery.tasks) == 1
    assert discovery.tasks[0].task_id == "task_extract-middleware"
    assert discovery.tasks[0].discovered_by == "api"

def test_insert_discovered_tasks_into_live_graph() -> None:
    """Discovered tasks and edges are inserted and immediately participate in scheduling."""
    graph = build_linear_graph(["a", "b"])  # a -> b
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

    discovery = Discovery(
        discovered_by="a",
        tasks=[TaskNode(task_id="a1", kind=TaskKind.IMPLEMENTATION, title="Sub-task",
                        discovered_by="a")],
        edges_to_add=[
            TypedEdge(from_task="a", to_task="a1", predicate=EdgePredicate.CODE_READY),
            TypedEdge(from_task="a1", to_task="b", predicate=EdgePredicate.CODE_READY),
        ],
    )

    # a is already succeeded
    graph.record_task_success("a")
    mutations = insert_discovered_tasks(graph, scheduler, discovery)

    assert "a1" in graph.nodes
    assert len(mutations) == 1
    assert mutations[0].nodes_added == ["a1"]

    # a1 should be in ready queue (a is succeeded, code_ready edge is satisfied)
    ready = scheduler.get_ready_tasks()
    assert "a1" in [t.task_id for t in ready]

def test_discovery_rejects_cycle() -> None:
    """Discovery that would create a cycle is rejected."""
    graph = build_linear_graph(["a", "b", "c"])
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

    discovery = Discovery(
        discovered_by="c",
        tasks=[],
        edges_to_add=[TypedEdge(from_task="c", to_task="a", predicate=EdgePredicate.CODE_READY)],
    )

    with pytest.raises(GraphCycleError):
        insert_discovered_tasks(graph, scheduler, discovery)

def test_discovery_rejects_duplicate_task_id() -> None:
    """Discovery with a task_id that already exists is rejected."""
    graph = build_linear_graph(["a", "b"])
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)

    discovery = Discovery(
        discovered_by="a",
        tasks=[TaskNode(task_id="b", kind=TaskKind.IMPLEMENTATION, title="Duplicate")],
        edges_to_add=[],
    )

    with pytest.raises(DuplicateTaskIdError):
        insert_discovered_tasks(graph, scheduler, discovery)

def test_graph_mutations_logged_with_provenance() -> None:
    """Graph mutations are recorded with timestamp and discovering task."""
    graph = build_linear_graph(["a", "b"])
    scheduler = ReadyQueueScheduler(graph, concurrency_limit=4)
    graph.record_task_success("a")

    discovery = Discovery(
        discovered_by="a",
        tasks=[TaskNode(task_id="a1", kind=TaskKind.IMPLEMENTATION, title="Sub", discovered_by="a")],
        edges_to_add=[TypedEdge(from_task="a", to_task="a1", predicate=EdgePredicate.CODE_READY)],
    )
    mutations = insert_discovered_tasks(graph, scheduler, discovery)

    assert mutations[0].discovered_by == "a"
    assert mutations[0].kind == "insert_tasks"
    assert mutations[0].mutation_id.startswith("mut_")
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run --group dev pytest tests/oats/test_discovery.py -q`

- [ ] **Step 3: Implement discovery module and wire into scheduler**

Key implementation:
- `discovery.py`: `parse_discovery_file()` validates JSON schema. `insert_discovered_tasks()` adds nodes and edges to the graph (with cycle check), records `GraphMutation`, and notifies the scheduler to re-evaluate readiness.
- `graph.py`: Add `insert_node()` (fails on duplicate ID), `insert_edges()` (fails on cycle). Ensure `evaluate_edges_from()` works for newly-inserted nodes.
- `scheduler.py`: After `record_completion()`, check for discovery files in the task's worktree at `.oats/discovered/<task_id>.json`. If found, call `insert_discovered_tasks()`.
- `models.py`: `GraphMutation`, `DuplicateTaskIdError`.

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run: `uv run --group dev pytest tests/oats/test_discovery.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/oats/discovery.py python/oats/graph.py python/oats/scheduler.py python/oats/models.py tests/oats/test_discovery.py
git commit -m "feat: dynamic discovered-task insertion with graph validation and provenance"
```

---

### Task 5: Durable Identity Propagation Through Backend and API

**Why:** The runtime now generates durable IDs for every entity. The backend must propagate these through the API so the frontend can link any entity to its origin. The API must expose the graph structure (nodes + edges), not just a flat task list.

**Files:**
- Modify: `python/helaicopter_api/schema/orchestration.py`
- Modify: `python/helaicopter_api/application/orchestration.py`
- Modify: `python/helaicopter_api/application/oats_run_actions.py`
- Modify: `python/helaicopter_api/router/orchestration.py`
- Modify: `tests/test_api_orchestration.py`

- [ ] **Step 1: Write failing API tests for graph response shape and durable IDs**

```python
def test_orchestration_run_detail_returns_graph_with_typed_edges(
    client, oats_runtime_with_graph,
) -> None:
    response = client.get("/orchestration/runs/run_abc")
    payload = response.json()

    assert "nodes" in payload
    assert "edges" in payload
    assert len(payload["nodes"]) == 5
    assert len(payload["edges"]) == 4

    edge = payload["edges"][0]
    assert "predicate" in edge
    assert edge["predicate"] in ["code_ready", "pr_merged", "checks_passing", "review_approved"]
    assert "satisfied" in edge

def test_orchestration_run_detail_includes_ready_queue(
    client, oats_runtime_with_running_tasks,
) -> None:
    response = client.get("/orchestration/runs/run_abc")
    payload = response.json()

    assert "readyQueue" in payload
    assert isinstance(payload["readyQueue"], list)

def test_orchestration_task_detail_includes_attempts_with_durable_ids(
    client, oats_runtime_with_retried_task,
) -> None:
    response = client.get("/orchestration/runs/run_abc/tasks/auth")
    payload = response.json()

    assert len(payload["attempts"]) == 2
    assert payload["attempts"][0]["attemptId"].startswith("att_")
    assert payload["attempts"][0]["sessionId"].startswith("sess_")
    assert payload["attempts"][0]["attemptId"] != payload["attempts"][1]["attemptId"]

def test_orchestration_run_includes_discovered_task_metadata(
    client, oats_runtime_with_discovered_tasks,
) -> None:
    response = client.get("/orchestration/runs/run_abc")
    payload = response.json()

    discovered = [n for n in payload["nodes"] if n.get("discoveredBy")]
    assert len(discovered) == 1
    assert discovered[0]["discoveredBy"] == "api"

def test_orchestration_refresh_returns_404_for_unknown_run(client) -> None:
    response = client.post("/orchestration/runs/nonexistent/refresh")
    assert response.status_code == 404

def test_orchestration_events_endpoint_returns_paginated_events(
    client, oats_runtime_with_events,
) -> None:
    response = client.get("/orchestration/runs/run_abc/events?limit=10")
    payload = response.json()

    assert "events" in payload
    assert len(payload["events"]) <= 10
```

- [ ] **Step 2: Run the backend tests and confirm they fail**

Run: `uv run --group dev pytest tests/test_api_orchestration.py -q`

- [ ] **Step 3: Implement graph-aware API responses and new endpoints**

Key changes:
- `schema/orchestration.py`: `RunGraphResponse` with `nodes`, `edges`, `ready_queue`, `graph_mutation_count`. `TaskNodeResponse` with `attempt_count`, `discovered_by`, `discovered_task_count`. `TypedEdgeResponse`. `AttemptResponse` with all durable IDs.
- `application/orchestration.py`: Read `state.json`, extract `graph` field, normalize nodes and edges. Propagate all durable IDs.
- `router/orchestration.py`: Add `GET /orchestration/runs/{run_id}/tasks/{task_id}`, `GET /orchestration/runs/{run_id}/events`.
- `application/oats_run_actions.py`: 404 for unknown runs, concurrent refresh guard.

- [ ] **Step 4: Re-run the backend tests and confirm they pass**

Run: `uv run --group dev pytest tests/test_api_orchestration.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/schema/orchestration.py python/helaicopter_api/application/orchestration.py python/helaicopter_api/application/oats_run_actions.py python/helaicopter_api/router/orchestration.py tests/test_api_orchestration.py
git commit -m "feat: graph-aware backend API with durable identity propagation"
```

---

### Task 6: Frontend Graph Normalization, View Model, and DAG Rendering

**Why:** The frontend must consume the graph API and render a live DAG with typed edges, ready-queue highlighting, discovered-task treatment, and attempt drill-down — not a flat task list.

**Files:**
- Modify: `src/lib/types.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/client/normalize.test.ts`
- Modify: `src/lib/client/mutations.ts`
- Modify: `src/lib/client/mutations.test.ts`
- Modify/rename: `src/components/orchestration/oats-view-model.ts` → `src/components/orchestration/oats-graph-view-model.ts`
- New: `src/components/orchestration/oats-graph-view-model.test.ts`
- Modify: `src/components/orchestration/oats-pr-stack.tsx`
- Modify: `src/components/orchestration/overnight-oats-panel.tsx`

- [ ] **Step 1: Write failing tests for graph normalization and view model**

```ts
// normalize.test.ts
test("normalizeRunGraph maps nodes and typed edges", () => {
  const raw = rawRunGraphWithEdges;
  const run = normalizeRunGraph(raw);

  assert.equal(run.nodes.length, 5);
  assert.equal(run.edges.length, 4);
  assert.equal(run.edges[0].predicate, "code_ready");
  assert.equal(typeof run.edges[0].satisfied, "boolean");
});

test("normalizeRunGraph flags discovered tasks", () => {
  const raw = rawRunGraphWithDiscoveredTask;
  const run = normalizeRunGraph(raw);

  const discovered = run.nodes.filter(n => n.discoveredBy);
  assert.equal(discovered.length, 1);
  assert.equal(discovered[0].discoveredBy, "api");
});

// oats-graph-view-model.test.ts
test("buildGraphViewModel produces edge color map", () => {
  const model = buildGraphViewModel(normalizedRunWithEdges);
  const edge = model.edges[0];
  assert.ok(edge.color);
  assert.equal(edge.color, "blue"); // code_ready = blue
});

test("buildGraphViewModel highlights ready-queue tasks", () => {
  const model = buildGraphViewModel(normalizedRunWithReadyQueue);
  const readyNodes = model.nodes.filter(n => n.isReady);
  assert.equal(readyNodes.length, 2);
});

test("buildGraphViewModel shows attempt count and last error", () => {
  const model = buildGraphViewModel(normalizedRunWithRetries);
  const failedNode = model.nodes.find(n => n.taskId === "auth");
  assert.equal(failedNode.attemptCount, 3);
  assert.ok(failedNode.lastError);
});

test("buildGraphViewModel exposes canRefresh and canResume", () => {
  const active = buildGraphViewModel(activeRun);
  assert.ok(active.canRefresh);
  assert.ok(!active.canResume);

  const failed = buildGraphViewModel(runWithFailedTasks);
  assert.ok(failed.canRefresh);
  assert.ok(failed.canResume);

  const completed = buildGraphViewModel(completedRun);
  assert.ok(!completed.canRefresh);
  assert.ok(!completed.canResume);
});

// mutations.test.ts
test("refreshOatsRun posts to correct endpoint and returns graph", async () => {
  const fetcher = mockFetcher({ nodes: [], edges: [], stackStatus: "ready_for_final_review" });
  const result = await refreshOatsRun("run_abc", { fetcher });
  assert.equal(result.stackStatus, "ready_for_final_review");
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `node --import tsx --test src/lib/client/normalize.test.ts src/lib/client/mutations.test.ts src/components/orchestration/oats-graph-view-model.test.ts`

- [ ] **Step 3: Implement graph types, normalization, view model, and component updates**

Key changes:
- `types.ts`: `TaskNode`, `TypedEdge`, `AttemptRecord`, `GraphMutation`, `RunGraph` types.
- `normalize.ts`: `normalizeRunGraph()` maps API response to typed frontend objects. Edge type mapping. Discovered task flagging.
- `oats-graph-view-model.ts`: `buildGraphViewModel()` produces layout hints (node positions from topological depth), edge colors by predicate, ready-queue highlight flags, attempt summaries, `canRefresh`/`canResume` booleans.
- `mutations.ts`: `refreshOatsRun()`, `resumeOatsRun()` POST to backend.
- `oats-pr-stack.tsx`: Extend with attempt timeline per task, operation history rendering.
- `overnight-oats-panel.tsx`: DAG rendering using graph view model. Refresh/resume buttons. Discovered-task dashed borders.

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run: `node --import tsx --test src/lib/client/normalize.test.ts src/lib/client/mutations.test.ts src/components/orchestration/oats-graph-view-model.test.ts`

- [ ] **Step 5: Commit**

```bash
git add src/lib/types.ts src/lib/client/normalize.ts src/lib/client/normalize.test.ts src/lib/client/mutations.ts src/lib/client/mutations.test.ts src/components/orchestration/oats-graph-view-model.ts src/components/orchestration/oats-graph-view-model.test.ts src/components/orchestration/oats-pr-stack.tsx src/components/orchestration/overnight-oats-panel.tsx
git commit -m "feat: frontend graph normalization, DAG view model, and edge-typed rendering"
```

---

### Task 7: Graph Runtime Migration and Planner Integration

**Why:** The new graph model and scheduler need to be wired into the existing planner (`planner.py`) so that `oats run` produces a `TaskGraph` instead of a flat task list, and existing `state.json` files without a `graph` field are auto-migrated on load.

**Files:**
- Modify: `python/oats/planner.py`
- Modify: `python/oats/runtime_state.py`
- Modify: `python/oats/stacked_prs.py`
- Modify: `tests/oats/test_stacked_prs.py`

- [ ] **Step 1: Write failing tests for planner graph output and state migration**

```python
def test_planner_produces_task_graph_with_typed_edges() -> None:
    """Planner should return a TaskGraph, not just a task list."""
    spec = build_test_spec(
        tasks=["auth", "models", "api", "dashboard"],
        deps={"api": ["auth", "models"], "dashboard": ["api"]},
    )
    plan = build_execution_plan(spec)

    assert plan.graph is not None
    assert len(plan.graph.nodes) == 4
    assert len(plan.graph.edges) == 3
    assert all(e.predicate == EdgePredicate.CODE_READY for e in plan.graph.edges)

def test_planner_assigns_pr_merged_edges_for_multi_dependency_tasks() -> None:
    """Multi-dependency tasks with after_dependency_merges strategy get pr_merged edges."""
    spec = build_test_spec(
        tasks=["a", "b", "c"],
        deps={"c": ["a", "b"]},
    )
    plan = build_execution_plan(spec)

    c_edges = plan.graph.edges_to("c")
    assert all(e.predicate == EdgePredicate.PR_MERGED for e in c_edges)

def test_legacy_state_without_graph_auto_migrates() -> None:
    """Loading a v1 state.json without a graph field creates the graph from tasks."""
    v1_state = build_v1_state(tasks=["a", "b", "c"], deps={"b": ["a"], "c": ["b"]})
    state = load_runtime_state(v1_state)

    assert state.graph is not None
    assert len(state.graph.nodes) == 3
    assert len(state.graph.edges) == 2
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run --group dev pytest tests/oats/test_stacked_prs.py -q`

- [ ] **Step 3: Implement planner graph construction and state migration**

Key changes:
- `planner.py`: `build_execution_plan()` constructs a `TaskGraph` from spec dependencies. Single-parent deps get `code_ready` edges. Multi-dependency tasks with `after_dependency_merges` get `pr_merged` edges.
- `stacked_prs.py`: Branch ancestry derivation works with `TaskGraph` edges instead of flat dependency arrays.
- `runtime_state.py`: `load_runtime_state()` detects missing `graph` field and auto-migrates from `tasks` array.

- [ ] **Step 4: Re-run the tests and confirm they pass**

Run: `uv run --group dev pytest tests/oats/test_stacked_prs.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/oats/planner.py python/oats/runtime_state.py python/oats/stacked_prs.py tests/oats/test_stacked_prs.py
git commit -m "feat: planner produces TaskGraph with typed edges; auto-migrate v1 state"
```

---

### Task 8: Large-Graph Scheduling and Recovery Verification

**Why:** The redesign targets 10–30 node graphs with multi-level dependencies, dynamic discovery, concurrent execution, and interruption/resume. This task verifies the full system at that scale — not just unit tests on individual components.

**Files:**
- New: `tests/oats/test_large_graph_scenarios.py`
- Modify: `tests/test_api_orchestration.py`
- All modified files from Tasks 1–7

- [ ] **Step 1: Write integration tests for large-graph scenarios**

```python
# test_large_graph_scenarios.py
def test_20_task_diamond_graph_with_concurrent_execution() -> None:
    """A 20-task graph with 4 levels of dependencies executes correctly with concurrency 4."""
    spec = build_layered_spec(layers=[4, 6, 6, 4])  # 20 tasks, diamond shape
    plan = build_execution_plan(spec)
    assert len(plan.graph.nodes) == 20

    runtime = SimulatedRuntime(plan, concurrency_limit=4)
    runtime.run_to_completion(agent_stub=instant_success_agent())

    assert runtime.state.status == RunStatus.COMPLETED
    assert all(t.status == TaskRuntimeStatus.SUCCEEDED for t in runtime.state.tasks)
    # Verify topological ordering was respected
    for edge in plan.graph.edges:
        from_finish = runtime.completion_time(edge.from_task)
        to_start = runtime.start_time(edge.to_task)
        assert from_finish <= to_start

def test_graph_with_mid_run_discovery_and_recovery() -> None:
    """A task discovers 3 sub-tasks. One fails and is retried. Run completes."""
    spec = build_test_spec(
        tasks=["plan", "api", "frontend", "e2e"],
        deps={"api": ["plan"], "frontend": ["plan"], "e2e": ["api", "frontend"]},
    )
    plan = build_execution_plan(spec)

    # api task will discover 3 sub-tasks
    agent_behaviors = {
        "api": DiscoveringAgent(discovers=[
            {"task_id": "task_extract-auth", "title": "Extract auth", "kind": "implementation",
             "dependencies": [{"task_id": "api", "predicate": "code_ready"}]},
            {"task_id": "task_extract-validation", "title": "Extract validation", "kind": "implementation",
             "dependencies": [{"task_id": "api", "predicate": "code_ready"}]},
            {"task_id": "task_auth-tests", "title": "Auth tests", "kind": "verification",
             "dependencies": [{"task_id": "task_extract-auth", "predicate": "code_ready"}]},
        ]),
        "task_extract-auth": FailThenSucceedAgent(fail_count=1),  # transient failure
    }

    runtime = SimulatedRuntime(plan, concurrency_limit=4, agent_behaviors=agent_behaviors)
    runtime.run_to_completion()

    assert runtime.state.status == RunStatus.COMPLETED
    assert len(runtime.state.graph.nodes) == 7  # 4 original + 3 discovered
    assert len(runtime.state.graph_mutations) == 1

    # Verify the retried task has 2 attempts
    auth_task = runtime.state.graph.nodes["task_extract-auth"]
    assert len(auth_task.attempts) == 2

def test_interrupted_large_graph_resumes_correctly() -> None:
    """A 15-task graph is interrupted after 8 completions and resumes to finish."""
    spec = build_layered_spec(layers=[3, 5, 4, 3])
    plan = build_execution_plan(spec)

    runtime = SimulatedRuntime(plan, concurrency_limit=3)
    runtime.run_until_n_completions(8)
    runtime.simulate_sigint()

    state = runtime.load_persisted_state()
    assert state.status == RunStatus.INTERRUPTED
    completed_count = sum(1 for t in state.tasks if t.status == TaskRuntimeStatus.SUCCEEDED)
    assert completed_count == 8

    # Resume
    resumed_runtime = SimulatedRuntime.from_persisted_state(state, concurrency_limit=3)
    resumed_runtime.run_to_completion()

    assert resumed_runtime.state.status == RunStatus.COMPLETED
    assert all(t.status == TaskRuntimeStatus.SUCCEEDED for t in resumed_runtime.state.tasks)

def test_cascading_failure_in_deep_graph() -> None:
    """A failure in an early task blocks all descendants, but independent branches complete."""
    spec = build_test_spec(
        tasks=["a", "b", "c", "d", "x", "y"],
        deps={"b": ["a"], "c": ["b"], "d": ["c"], "y": ["x"]},
    )
    plan = build_execution_plan(spec)

    agent_behaviors = {"a": AlwaysFailAgent()}
    runtime = SimulatedRuntime(plan, concurrency_limit=4, agent_behaviors=agent_behaviors)
    runtime.run_to_completion()

    assert runtime.state.graph.nodes["a"].status == TaskRuntimeStatus.FAILED
    assert runtime.state.graph.nodes["b"].status == TaskRuntimeStatus.BLOCKED_BY_FAILURE
    assert runtime.state.graph.nodes["c"].status == TaskRuntimeStatus.BLOCKED_BY_FAILURE
    assert runtime.state.graph.nodes["d"].status == TaskRuntimeStatus.BLOCKED_BY_FAILURE
    # Independent branch completes
    assert runtime.state.graph.nodes["x"].status == TaskRuntimeStatus.SUCCEEDED
    assert runtime.state.graph.nodes["y"].status == TaskRuntimeStatus.SUCCEEDED
    assert runtime.state.status == RunStatus.FAILED  # overall run failed
```

- [ ] **Step 2: Run the integration tests and confirm they fail**

Run: `uv run --group dev pytest tests/oats/test_large_graph_scenarios.py -q`

- [ ] **Step 3: Fix any integration issues surfaced by large-graph scenarios**

This step addresses real bugs found by integration tests — not pre-planned implementation. Typical issues: ready-queue not properly re-seeding after resume, edge evaluation ordering in deep graphs, discovery insertion timing relative to concurrent completions.

- [ ] **Step 4: Re-run all tests end-to-end**

Run: `uv run --group dev pytest tests/oats/ -q && uv run --group dev pytest tests/test_api_orchestration.py -q`

- [ ] **Step 5: Run the full frontend verification suite**

Run: `node --import tsx --test src/lib/client/normalize.test.ts src/lib/client/mutations.test.ts src/components/orchestration/oats-graph-view-model.test.ts`

- [ ] **Step 6: Run lint**

Run: `npm run lint`

- [ ] **Step 7: Regenerate OpenAPI snapshots**

Run: `npm run api:openapi`

- [ ] **Step 8: Commit**

```bash
git add tests/oats/test_large_graph_scenarios.py
git add -u
git commit -m "feat: large-graph integration tests and end-to-end verification"
```
