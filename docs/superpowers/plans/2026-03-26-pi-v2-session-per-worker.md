# Pi V2 Session-Per-Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Pi from per-task subprocess spawning to persistent worker-local provider sessions with explicit session lifecycle, operator-visible session health, and conservative protocol extensions that preserve the existing permanent-worker-loop architecture.

**Architecture:** Keep the resolver loop, worker registry, dispatch flow, runtime materialization, and operator console as the stable outer architecture. Implement Pi v2 by adding a worker-local session manager, extending worker and result contracts with session metadata, surfacing reset controls in backend/UI layers, and materializing session reuse/reset truth alongside the existing runtime and operator-action model.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, asyncio, httpx, Next.js 16, React 19, SWR, pytest, node:test, tsx

---

## File Structure

**Existing files to modify**

- `python/oats/pi_worker.py`
- `python/oats/cli.py`
- `python/helaicopter_api/application/workers.py`
- `python/helaicopter_api/application/dispatch.py`
- `python/helaicopter_api/application/runtime_materialization.py`
- `python/helaicopter_api/application/operator_bootstrap.py`
- `python/helaicopter_api/router/workers.py`
- `python/helaicopter_api/schema/workers.py`
- `python/helaicopter_api/schema/runtime_materialization.py`
- `python/helaicopter_api/schema/operator_bootstrap.py`
- `src/components/workers/worker-dashboard.tsx`
- `src/components/orchestration/operator-bootstrap-panel.tsx`
- `src/components/orchestration/overnight-oats-panel.tsx`
- `src/lib/client/normalize.ts`
- `src/lib/client/schemas/workers.ts`
- `src/lib/types.ts`
- `tests/oats/test_pi_worker.py`
- `tests/test_api_workers.py`
- `tests/test_runtime_materialization.py`
- `tests/test_api_runtime_materialization.py`
- `src/components/workers/worker-dashboard.test.tsx`
- `src/lib/client/normalize.test.ts`

**New files to create**

- `python/oats/provider_session.py`
- `tests/oats/test_provider_session.py`
- `tests/test_api_worker_session_controls.py`

**Responsibility split**

- `provider_session.py` owns worker-local persistent provider session lifecycle and reuse rules.
- `pi_worker.py` owns task execution through the session manager and heartbeat/result session metadata.
- `workers.py` and worker schemas own operator/control-plane session visibility and reset actions.
- `runtime_materialization.py` owns projection of session reuse/reset truth for the operator console.
- Frontend worker/orchestration components surface session state and reset affordances without inventing their own lifecycle rules.

### Task 1: Introduce the Worker-Local Session Manager

**Files:**
- Create: `python/oats/provider_session.py`
- Create: `tests/oats/test_provider_session.py`
- Modify: `python/oats/pi_worker.py`

- [ ] **Step 1: Write the failing session-manager tests**

```python
def test_session_manager_starts_absent_and_transitions_to_ready_after_bootstrap() -> None:
    manager = ProviderSessionManager(provider="claude")
    assert manager.status == "absent"
    session = manager.ensure_session()
    assert manager.status == "ready"
    assert session is not None


def test_session_manager_reset_discards_current_session_identity() -> None:
    manager = ProviderSessionManager(provider="codex")
    first = manager.ensure_session()
    manager.reset(reason="operator_requested")
    second = manager.ensure_session()
    assert first.session_id != second.session_id
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/oats/test_provider_session.py -q`
Expected: FAIL because no session manager exists yet.

- [ ] **Step 3: Implement the minimal session manager**

```python
@dataclass
class ProviderSession:
    session_id: str
    provider: str
    status: str
    started_at: datetime
    last_used_at: datetime


class ProviderSessionManager:
    def ensure_session(self) -> ProviderSession: ...
    def reset(self, *, reason: str) -> None: ...
```

Implementation notes:
- Start with in-memory session lifecycle only.
- Keep provider-specific bootstrapping behind helper methods.
- Do not change control-plane APIs in this task.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/oats/test_provider_session.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/oats/provider_session.py tests/oats/test_provider_session.py python/oats/pi_worker.py
git commit -m "feat: add worker-local provider session manager"
```

### Task 2: Route Pi Task Execution Through Persistent Sessions

**Files:**
- Modify: `python/oats/pi_worker.py`
- Modify: `tests/oats/test_pi_worker.py`

- [ ] **Step 1: Write the failing Pi v2 execution tests**

```python
def test_pi_worker_reuses_provider_session_across_multiple_tasks() -> None:
    worker = build_pi_worker_with_fake_session_manager()
    first = run_task(worker, task_id="task_a")
    second = run_task(worker, task_id="task_b")
    assert first.session_id == second.session_id


def test_pi_worker_marks_session_failed_when_bootstrap_fails() -> None:
    worker = build_pi_worker_with_broken_session_manager()
    result = run_task(worker, task_id="task_a")
    assert result.error_summary == "Provider session bootstrap failed."
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/oats/test_pi_worker.py -q -k "session"`
Expected: FAIL because Pi still spawns fresh subprocesses without session lifecycle.

- [ ] **Step 3: Implement Pi v2 execution flow**

```python
session = self.session_manager.ensure_session()
result = await self.agent_runner.run(envelope, session=session, on_heartbeat=...)
```

Implementation notes:
- Preserve the existing attack-plan and acceptance-criteria flow.
- Treat session bootstrap failure distinctly from task execution failure.
- Keep current redispatch semantics; this task is about execution backend, not queue logic.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/oats/test_pi_worker.py -q -k "session"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/oats/pi_worker.py tests/oats/test_pi_worker.py
git commit -m "feat: execute Pi tasks through persistent sessions"
```

### Task 3: Extend Worker API Contracts With Session State and Reset Control

**Files:**
- Modify: `python/helaicopter_api/application/workers.py`
- Modify: `python/helaicopter_api/router/workers.py`
- Modify: `python/helaicopter_api/schema/workers.py`
- Create: `tests/test_api_worker_session_controls.py`
- Modify: `tests/test_api_workers.py`

- [ ] **Step 1: Write the failing worker session API tests**

```python
def test_worker_detail_includes_session_state(client, registered_worker) -> None:
    payload = client.get(f"/workers/{registered_worker}").json()
    assert payload["sessionStatus"] == "absent"
    assert payload["sessionResetAvailable"] is True


def test_reset_worker_session_marks_session_absent(client, registered_worker) -> None:
    response = client.post(f"/workers/{registered_worker}/reset-session")
    assert response.status_code == 200
    assert response.json()["sessionStatus"] == "absent"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_workers.py tests/test_api_worker_session_controls.py -q`
Expected: FAIL because the worker API does not expose session state yet.

- [ ] **Step 3: Implement worker session fields and reset endpoint**

```python
class WorkerDetailResponse(...):
    session_status: str = "absent"
    session_started_at: str | None = None
    session_last_used_at: str | None = None
    session_failure_reason: str | None = None
    session_reset_available: bool = True
```

Implementation notes:
- Keep session state additive to existing worker detail.
- Reset should be explicit and operator-initiated.
- Do not overload worker `status` with session state.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_workers.py tests/test_api_worker_session_controls.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/workers.py python/helaicopter_api/router/workers.py python/helaicopter_api/schema/workers.py tests/test_api_workers.py tests/test_api_worker_session_controls.py
git commit -m "feat: expose worker session state and reset control"
```

### Task 4: Materialize Session Reuse and Reset Truth

**Files:**
- Modify: `python/helaicopter_api/application/runtime_materialization.py`
- Modify: `python/helaicopter_api/schema/runtime_materialization.py`
- Modify: `tests/test_runtime_materialization.py`
- Modify: `tests/test_api_runtime_materialization.py`

- [ ] **Step 1: Write the failing materialization tests**

```python
def test_runtime_materialization_includes_session_reuse_metadata(tmp_path: Path) -> None:
    materialized = materialize_runtime_run(run_dir)
    assert materialized.task_attempts[0].session_reused is True
    assert materialized.task_attempts[0].provider_session_id is not None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_runtime_materialization.py tests/test_api_runtime_materialization.py -q -k "session"`
Expected: FAIL because runtime materialization does not include session metadata yet.

- [ ] **Step 3: Extend result artifacts and materialization projection**

```python
class MaterializedTaskAttempt(...):
    provider_session_id: str | None = None
    session_reused: bool = False
    session_status_after_task: str | None = None
```

Implementation notes:
- Extend result reporting conservatively.
- Keep existing attempt/dispatch/operator-action structure stable.
- Make reset actions visible via operator action projection if emitted.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_runtime_materialization.py tests/test_api_runtime_materialization.py -q -k "session"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/runtime_materialization.py python/helaicopter_api/schema/runtime_materialization.py tests/test_runtime_materialization.py tests/test_api_runtime_materialization.py
git commit -m "feat: materialize session reuse metadata"
```

### Task 5: Surface Session Health and Reset Controls in the Operator UI

**Files:**
- Modify: `src/components/workers/worker-dashboard.tsx`
- Modify: `src/components/orchestration/operator-bootstrap-panel.tsx`
- Modify: `src/components/orchestration/overnight-oats-panel.tsx`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/client/schemas/workers.ts`
- Modify: `src/lib/types.ts`
- Modify: `src/components/workers/worker-dashboard.test.tsx`
- Modify: `src/lib/client/normalize.test.ts`

- [ ] **Step 1: Write the failing UI normalization/render tests**

```tsx
test("worker dashboard renders session state and reset affordance", () => {
  const markup = renderToStaticMarkup(<WorkerDashboardSection workers={workers} providerReadiness={readiness} />);
  assert.match(markup, /session ready/i);
  assert.match(markup, /reset session/i);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --import tsx --test src/components/workers/worker-dashboard.test.tsx src/lib/client/normalize.test.ts`
Expected: FAIL because the frontend contracts do not include session state yet.

- [ ] **Step 3: Implement session-aware UI surfaces**

```ts
type WorkerSessionStatus = "absent" | "starting" | "ready" | "degraded" | "stale" | "failed" | "resetting";
```

Implementation notes:
- Show worker state and session state separately.
- Keep reset control visible but scoped to session failure/degradation cases.
- Surface session reuse in the orchestration runtime-truth area only if the data is present.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --import tsx --test src/components/workers/worker-dashboard.test.tsx src/lib/client/normalize.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/components/workers/worker-dashboard.tsx src/components/orchestration/operator-bootstrap-panel.tsx src/components/orchestration/overnight-oats-panel.tsx src/lib/client/normalize.ts src/lib/client/schemas/workers.ts src/lib/types.ts src/components/workers/worker-dashboard.test.tsx src/lib/client/normalize.test.ts
git commit -m "feat: surface Pi v2 session health in operator UI"
```

### Task 6: End-to-End Pi V2 Confidence Slice

**Files:**
- Modify: `tests/oats/test_pi_worker.py`
- Modify: `tests/test_api_worker_session_controls.py`
- Modify: `tests/test_end_to_end_smoke.py`

- [ ] **Step 1: Add the release-gate Pi v2 scenarios**

Required scenarios:
- worker creates a provider session lazily on first task
- second task reuses the same session
- failed session becomes operator-visible and resettable
- worker death still follows current interruption/retry semantics

- [ ] **Step 2: Run the focused verification suite**

Run: `uv run pytest tests/oats/test_provider_session.py tests/oats/test_pi_worker.py tests/test_api_workers.py tests/test_api_worker_session_controls.py tests/test_runtime_materialization.py tests/test_api_runtime_materialization.py tests/test_end_to_end_smoke.py -q`
Expected: PASS

Run: `node --import tsx --test src/components/workers/worker-dashboard.test.tsx src/lib/client/normalize.test.ts src/components/orchestration/oats-view-model.test.ts`
Expected: PASS

Run: `npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/oats/test_provider_session.py tests/oats/test_pi_worker.py tests/test_api_worker_session_controls.py tests/test_end_to_end_smoke.py
git commit -m "test: add Pi v2 session-per-worker confidence coverage"
```

## Definition of Done

- Pi workers can own and reuse persistent provider sessions across tasks.
- Worker state and session state are both visible and distinct in backend and UI contracts.
- Operators can reset unhealthy sessions without treating the worker as dead.
- Runtime truth records whether sessions were reused or reset.
- Existing resolver-loop and interruption semantics remain intact.

## Notes

- Keep the first Pi v2 wave intentionally narrow: session-per-worker only.
- Do not expand into pooled sessions, run-scoped leasing, or session migration in this plan.
- Preserve current task-envelope authority even when sessions are warm.
