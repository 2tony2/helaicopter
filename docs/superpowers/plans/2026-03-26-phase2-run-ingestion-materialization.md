# Phase 2 Run Ingestion and Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make permanent-loop run state durable, inspectable, and authoritative enough that Helaicopter can show coherent runtime truth for live and recently completed runs without reconstructing everything from loosely related artifacts on each request.

**Architecture:** Keep `.oats/runtime/<run_id>/` as the authoritative store for graph state, results, discoveries, and mutation logs, but add a backend-owned materialization layer that reads those runtime artifacts into stable operator-facing projections. The Phase 2 slice focuses on durable run truth: task attempts, worker claims, graph mutations, dispatch events, and artifact-backed task outputs should all have one backend contract and one normalization path for API/UI use. SQLite facts remain a downstream analytical surface, not the live authority.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, local JSON/JSONL runtime artifacts, Next.js, React, SWR, pytest, node:test

---

## File Structure

**Existing files to modify**

- `python/helaicopter_api/application/resolver.py`
- `python/helaicopter_api/application/workers.py`
- `python/helaicopter_api/application/orchestration.py`
- `python/helaicopter_api/application/dispatch_monitor.py`
- `python/helaicopter_api/adapters/oats_artifacts/store.py`
- `python/helaicopter_api/ports/orchestration.py`
- `python/helaicopter_api/router/orchestration.py`
- `python/helaicopter_api/schema/orchestration.py`
- `python/oats/runtime_state.py`
- `python/oats/models.py`
- `src/components/orchestration/overnight-oats-panel.tsx`
- `src/components/orchestration/oats-view-model.ts`
- `src/components/orchestration/oats-graph-view-model.ts`
- `src/lib/client/endpoints.ts`
- `src/lib/client/normalize.ts`
- `src/lib/client/schemas/dispatch.ts`
- `src/lib/types.ts`
- `tests/test_api_orchestration.py`
- `tests/test_api_dispatch.py`
- `tests/test_permanent_loop_integration.py`
- `src/components/orchestration/oats-graph-view-model.test.ts`

**New files to create**

- `python/helaicopter_api/application/runtime_materialization.py`
- `python/helaicopter_api/schema/runtime_materialization.py`
- `python/helaicopter_api/router/runtime_materialization.py`
- `tests/test_api_runtime_materialization.py`
- `tests/test_runtime_materialization.py`

**Responsibility split**

- `runtime_materialization.py` owns the authoritative read model for live runtime artifacts.
- `resolver.py` and `workers.py` own writing durable runtime events in a shape that materialization can rely on.
- `orchestration.py` consumes the materialized view instead of re-deriving runtime truth ad hoc.
- The frontend orchestration components consume one stable backend response for live attempts, claims, mutations, and outputs.

### Task 1: Define the Runtime Materialization Contract

**Files:**
- Create: `python/helaicopter_api/application/runtime_materialization.py`
- Create: `python/helaicopter_api/schema/runtime_materialization.py`
- Create: `tests/test_runtime_materialization.py`
- Modify: `python/helaicopter_api/ports/orchestration.py`

- [ ] **Step 1: Write the failing contract tests**

```python
def test_materialize_runtime_run_reads_state_results_and_graph_mutations(tmp_path: Path) -> None:
    materialized = materialize_runtime_run(tmp_path / ".oats" / "runtime" / "run_1")
    assert materialized.run_id == "run_1"
    assert materialized.graph_mutations
    assert materialized.task_attempts[0].task_id == "task_auth"


def test_materialize_runtime_run_prefers_runtime_artifacts_over_missing_sqlite_facts(tmp_path: Path) -> None:
    materialized = materialize_runtime_run(tmp_path / ".oats" / "runtime" / "run_1")
    assert materialized.source == "runtime"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_runtime_materialization.py -q`
Expected: FAIL because no runtime materialization module or contract exists yet.

- [ ] **Step 3: Implement the minimal materialized read model**

```python
class MaterializedRuntimeRun(BaseModel):
    run_id: str
    source: str
    task_attempts: list[MaterializedTaskAttempt]
    graph_mutations: list[MaterializedGraphMutation]
    dispatch_events: list[MaterializedDispatchEvent]
```

Implementation notes:
- Build from runtime files only in this task: `state.json`, `graph_mutations.jsonl`, `dispatch_history.jsonl`, and result/discovery folders when present.
- Do not mix SQLite facts into this contract yet.
- Ensure the contract distinguishes “artifact missing” from “empty artifact”.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_runtime_materialization.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/runtime_materialization.py python/helaicopter_api/schema/runtime_materialization.py python/helaicopter_api/ports/orchestration.py tests/test_runtime_materialization.py
git commit -m "feat: add runtime materialization read model"
```

### Task 2: Persist Durable Runtime Events the Materializer Can Trust

**Files:**
- Modify: `python/helaicopter_api/application/resolver.py`
- Modify: `python/helaicopter_api/application/workers.py`
- Modify: `python/oats/runtime_state.py`
- Modify: `python/oats/models.py`
- Test: `tests/test_permanent_loop_integration.py`

- [ ] **Step 1: Write failing persistence tests**

```python
def test_worker_completion_writes_result_artifact_and_attempt_metadata(tmp_path: Path) -> None:
    report_task_result(...)
    assert (runtime_dir / "run_1" / "results" / "task_auth.json").exists()


def test_resolver_dispatch_writes_dispatch_history_jsonl(tmp_path: Path) -> None:
    resolver.tick()
    assert (runtime_dir / "dispatch_history.jsonl").read_text()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_permanent_loop_integration.py -q -k "result_artifact or dispatch_history"`
Expected: FAIL because the currently written artifacts are too thin or inconsistent for a stable materialized view.

- [ ] **Step 3: Implement durable runtime event persistence**

```python
def write_task_result_artifact(runtime_dir: Path, result: TaskResult) -> Path:
    path = runtime_dir / result.run_id / "results" / f"{result.task_id}.json"
    _atomic_write_json(path, result.model_dump(mode="json"))
    return path
```

Implementation notes:
- Ensure result artifacts include attempt ID, worker ID, status, duration, branch, commit, and error summary.
- Keep `dispatch_history.jsonl` append-only and machine-readable.
- If task attempt metadata currently lives only inside `state.json`, make sure the materializer can still reconstruct latest and historical attempts deterministically.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_permanent_loop_integration.py -q -k "result_artifact or dispatch_history"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/resolver.py python/helaicopter_api/application/workers.py python/oats/runtime_state.py python/oats/models.py tests/test_permanent_loop_integration.py
git commit -m "feat: persist durable runtime events for materialization"
```

### Task 3: Expose a Backend Runtime Materialization Endpoint

**Files:**
- Create: `python/helaicopter_api/router/runtime_materialization.py`
- Modify: `python/helaicopter_api/router/router.py`
- Modify: `python/helaicopter_api/application/runtime_materialization.py`
- Modify: `python/helaicopter_api/schema/runtime_materialization.py`
- Test: `tests/test_api_runtime_materialization.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_runtime_materialization_endpoint_returns_live_attempts_and_mutations(client) -> None:
    response = client.get("/orchestration/runtime/run_1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["taskAttempts"][0]["taskId"] == "task_auth"
    assert payload["graphMutations"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_runtime_materialization.py -q`
Expected: FAIL because the endpoint does not exist yet.

- [ ] **Step 3: Implement the endpoint**

```python
@runtime_materialization_router.get("/orchestration/runtime/{run_id}")
async def runtime_run_detail(run_id: str, services: BackendServices = Depends(get_services)):
    return get_materialized_runtime_run(services, run_id)
```

Implementation notes:
- Return one coherent payload that includes task attempts, worker claims, dispatch history, graph mutations, and artifact-derived output references.
- Keep this separate from `/orchestration/oats` list shaping.
- Use 404 for unknown run IDs; do not silently fall back to an empty payload.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_runtime_materialization.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/router/runtime_materialization.py python/helaicopter_api/router/router.py python/helaicopter_api/application/runtime_materialization.py python/helaicopter_api/schema/runtime_materialization.py tests/test_api_runtime_materialization.py
git commit -m "feat: expose runtime materialization endpoint"
```

### Task 4: Refactor Orchestration API Shaping to Consume Materialized Runtime Truth

**Files:**
- Modify: `python/helaicopter_api/application/orchestration.py`
- Modify: `python/helaicopter_api/schema/orchestration.py`
- Modify: `tests/test_api_orchestration.py`

- [ ] **Step 1: Write failing orchestration endpoint tests**

```python
def test_get_oats_run_uses_materialized_runtime_attempts_and_mutations(client) -> None:
    payload = client.get("/orchestration/oats/run_1").json()
    assert payload["graphMutations"][0]["source"] == "operator"
    assert payload["tasks"][0]["attempts"] == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_orchestration.py -q -k "materialized or graphMutations or attempts"`
Expected: FAIL because orchestration shaping still reconstructs runtime truth directly from mixed sources.

- [ ] **Step 3: Implement the refactor**

```python
materialized = get_materialized_runtime_run(services, run_id)
tasks = shape_tasks_from_materialized_runtime(materialized)
```

Implementation notes:
- Replace ad hoc runtime reconstruction paths with the materialized contract where possible.
- Keep persisted SQLite facts as the list/analytics source, but let live run detail prefer runtime materialization.
- Make “live” vs “persisted” source explicit in the response when both exist.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_orchestration.py -q -k "materialized or graphMutations or attempts"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/orchestration.py python/helaicopter_api/schema/orchestration.py tests/test_api_orchestration.py
git commit -m "refactor: shape orchestration detail from materialized runtime truth"
```

### Task 5: Surface Materialized Runtime Truth in the Orchestration UI

**Files:**
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/types.ts`
- Modify: `src/components/orchestration/overnight-oats-panel.tsx`
- Modify: `src/components/orchestration/oats-view-model.ts`
- Modify: `src/components/orchestration/oats-graph-view-model.ts`
- Test: `src/components/orchestration/oats-graph-view-model.test.ts`

- [ ] **Step 1: Write failing frontend tests**

```ts
test("graph view model includes materialized mutation and attempt context", () => {
  const model = buildOatsGraphViewModel(materializedRunPayload);
  assert.equal(model.sidebar.attempts[0]?.attemptId, "att_2");
  assert.equal(model.sidebar.graphMutations[0]?.source, "operator");
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --import tsx --test src/components/orchestration/oats-graph-view-model.test.ts`
Expected: FAIL because the frontend types and view-models do not consume the new runtime materialization payload yet.

- [ ] **Step 3: Implement the frontend wiring**

```ts
export function runtimeMaterialization(runId: string) {
  return api(`/orchestration/runtime/${enc(runId)}`);
}
```

Implementation notes:
- Show attempts, graph mutations, and dispatch context without inventing frontend-only semantics.
- Prefer additive UI: make the richer runtime truth visible in details panes before changing the main graph layout.
- Keep normalization tolerant of mixed live/persisted payloads during rollout.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --import tsx --test src/components/orchestration/oats-graph-view-model.test.ts src/lib/client/normalize.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/client/endpoints.ts src/lib/client/normalize.ts src/lib/types.ts src/components/orchestration/overnight-oats-panel.tsx src/components/orchestration/oats-view-model.ts src/components/orchestration/oats-graph-view-model.ts src/components/orchestration/oats-graph-view-model.test.ts
git commit -m "feat: surface materialized runtime truth in orchestration UI"
```

### Task 6: Add a Phase 2 Runtime-Truth Smoke Slice

**Files:**
- Modify: `tests/test_api_runtime_materialization.py`
- Modify: `tests/test_api_orchestration.py`
- Modify: `tests/test_permanent_loop_integration.py`

- [ ] **Step 1: Write the failing smoke scenario**

```python
def test_live_run_materialization_survives_reload_and_preserves_attempt_history(client) -> None:
    payload = client.get("/orchestration/runtime/run_1").json()
    assert payload["taskAttempts"]
    assert payload["dispatchHistory"]
    assert payload["graphMutations"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_runtime_materialization.py tests/test_api_orchestration.py tests/test_permanent_loop_integration.py -q -k "materialization or attempt_history or reload"`
Expected: FAIL until the materialized runtime contract is stable across API layers.

- [ ] **Step 3: Make the smallest cross-layer fixes**

Implementation notes:
- Only fix issues that block the smoke slice.
- Do not expand into provider-auth execution changes from Phase 3.
- Prefer fixing authority/conflict ambiguity over patching around symptoms.

- [ ] **Step 4: Run the full Phase 2 verification slice**

Run: `uv run pytest tests/test_runtime_materialization.py tests/test_api_runtime_materialization.py tests/test_api_orchestration.py tests/test_api_dispatch.py tests/test_permanent_loop_integration.py -q`
Expected: PASS

- [ ] **Step 5: Run frontend verification**

Run: `node --import tsx --test src/components/orchestration/oats-graph-view-model.test.ts src/lib/client/normalize.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_runtime_materialization.py tests/test_api_runtime_materialization.py tests/test_api_orchestration.py tests/test_api_dispatch.py tests/test_permanent_loop_integration.py src/components/orchestration/oats-graph-view-model.test.ts src/lib/client/normalize.test.ts
git commit -m "test: add runtime materialization and live-truth smoke coverage"
```
