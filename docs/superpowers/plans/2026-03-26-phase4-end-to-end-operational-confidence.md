# Phase 4 End-to-End Operational Confidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the permanent-worker-loop system is genuinely usable end to end by codifying the real acceptance scenarios for Claude and Codex, surfacing operator intervention and recovery states cleanly, and making those scenarios repeatable enough to act as a release-style confidence suite.

**Architecture:** Build on the readiness surfaces from Phase 1, the runtime materialization model from Phase 2, and the provider-readiness gating from Phase 3. Phase 4 should not invent a second orchestration model. Instead, it should connect the existing backend and UI contracts into a compact smoke harness that exercises cold start, happy-path provider runs, blocked auth, worker interruption, and operator intervention with stable assertions against materialized runtime truth.

**Tech Stack:** FastAPI, permanent resolver loop, Pi worker subprocess orchestration, local runtime artifacts, Next.js, React, SWR, pytest, node:test

---

## File Structure

**Existing files to modify**

- `python/helaicopter_api/application/dispatch.py`
- `python/helaicopter_api/application/dispatch_monitor.py`
- `python/helaicopter_api/application/operator_bootstrap.py`
- `python/helaicopter_api/application/orchestration.py`
- `python/helaicopter_api/application/runtime_materialization.py`
- `python/helaicopter_api/application/workers.py`
- `python/helaicopter_api/schema/dispatch.py`
- `python/helaicopter_api/schema/operator_bootstrap.py`
- `python/helaicopter_api/schema/orchestration.py`
- `python/oats/runtime_state.py`
- `src/components/orchestration/overnight-oats-panel.tsx`
- `src/components/orchestration/operator-bootstrap-panel.tsx`
- `src/components/dispatch/queue-monitor.tsx`
- `src/components/workers/worker-dashboard.tsx`
- `src/lib/client/normalize.ts`
- `src/lib/types.ts`
- `tests/test_api_dispatch.py`
- `tests/test_api_operator_bootstrap.py`
- `tests/test_api_orchestration.py`
- `tests/test_permanent_loop_integration.py`
- `tests/test_resolver_loop.py`
- `src/components/orchestration/oats-graph-view-model.test.ts`
- `src/components/workers/worker-dashboard.test.tsx`

**New files to create**

- `tests/test_end_to_end_smoke.py`
- `tests/test_api_operator_controls.py`
- `src/components/orchestration/operator-bootstrap-panel.test.tsx`
- `docs/orchestration/smoke-scenarios.md`

**Responsibility split**

- `test_end_to_end_smoke.py` owns the acceptance suite for the provider-complete local system.
- Backend application/schema files own the operator-visible states needed to make smoke failures understandable rather than opaque.
- Frontend orchestration and worker components own the operator-facing representation of those acceptance states.
- `docs/orchestration/smoke-scenarios.md` owns the concise human runbook for running and interpreting the smoke flows locally.

### Task 1: Codify the Acceptance Smoke Matrix

**Files:**
- Create: `tests/test_end_to_end_smoke.py`
- Create: `docs/orchestration/smoke-scenarios.md`
- Modify: `tests/test_permanent_loop_integration.py`

- [ ] **Step 1: Write the failing smoke-matrix tests**

```python
def test_smoke_cold_start_to_healthy_system(...) -> None:
    snapshot = boot_local_operator_system(...)
    assert snapshot.bootstrap.overall_status == "ready"
    assert {"claude", "codex"} <= {provider.provider for provider in snapshot.providers}


def test_smoke_claude_and_codex_happy_paths_materialize_runtime_truth(...) -> None:
    result = run_provider_smoke_pair(...)
    assert result.claude.run.status == "completed"
    assert result.codex.run.status == "completed"
    assert result.codex.runtime.task_attempts
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_end_to_end_smoke.py -q`
Expected: FAIL because the acceptance harness and scenario fixtures do not exist yet.

- [ ] **Step 3: Implement the minimal smoke harness and scenario doc**

```python
class SmokeScenarioResult(BaseModel):
    name: str
    status: str
    blocking_reason: str | None = None
```

Implementation notes:
- Keep the suite compact and explicit; Phase 4 is not a giant regression pack.
- Model the roadmap scenarios directly: cold start, Claude happy path, Codex happy path, auth failure visibility, worker interruption, operator intervention.
- Document how a human operator should read a failing scenario and where to look next in Helaicopter.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_end_to_end_smoke.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_end_to_end_smoke.py docs/orchestration/smoke-scenarios.md tests/test_permanent_loop_integration.py
git commit -m "test: codify orchestration smoke scenarios"
```

### Task 2: Surface Stable Operator-Control States for Pause, Resume, Retry, and Reroute

**Files:**
- Create: `tests/test_api_operator_controls.py`
- Modify: `python/helaicopter_api/application/orchestration.py`
- Modify: `python/helaicopter_api/application/runtime_materialization.py`
- Modify: `python/helaicopter_api/schema/orchestration.py`
- Modify: `python/oats/runtime_state.py`
- Modify: `tests/test_api_orchestration.py`

- [ ] **Step 1: Write the failing operator-control tests**

```python
def test_operator_pause_resume_retry_and_reroute_are_materialized(client) -> None:
    payload = exercise_operator_controls(client, run_id="run_1")
    assert payload["operatorActions"][0]["action"] == "pause"
    assert payload["operatorActions"][-1]["action"] == "reroute"
    assert payload["status"] in {"paused", "running", "pending"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_operator_controls.py tests/test_api_orchestration.py -q -k "pause or resume or retry or reroute"`
Expected: FAIL because operator interventions are not yet represented as a coherent durable action stream.

- [ ] **Step 3: Implement durable operator-action materialization**

```python
class MaterializedOperatorAction(BaseModel):
    action: str
    actor: str
    created_at: datetime
    target_task_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
```

Implementation notes:
- Do not hide operator interventions inside generic graph-mutation text alone.
- Preserve compatibility with the existing graph-native runtime model, but add an explicit operator-action projection for UI and smoke assertions.
- Ensure pause and resume semantics remain visible after reload.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_operator_controls.py tests/test_api_orchestration.py -q -k "pause or resume or retry or reroute"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_api_operator_controls.py python/helaicopter_api/application/orchestration.py python/helaicopter_api/application/runtime_materialization.py python/helaicopter_api/schema/orchestration.py python/oats/runtime_state.py tests/test_api_orchestration.py
git commit -m "feat: materialize operator control actions"
```

### Task 3: Make Worker Interruption and Recovery States Explicit

**Files:**
- Modify: `python/helaicopter_api/application/dispatch.py`
- Modify: `python/helaicopter_api/application/dispatch_monitor.py`
- Modify: `python/helaicopter_api/application/workers.py`
- Modify: `python/helaicopter_api/schema/dispatch.py`
- Modify: `tests/test_api_dispatch.py`
- Modify: `tests/test_resolver_loop.py`
- Modify: `tests/test_end_to_end_smoke.py`

- [ ] **Step 1: Write the failing recovery tests**

```python
def test_worker_interruption_surfaces_recoverable_state_in_dispatch_snapshot(...) -> None:
    snapshot = interrupt_worker_mid_run(...)
    assert snapshot.deferred_tasks[0].reason == "worker_interrupted"
    assert snapshot.deferred_tasks[0].can_retry is True


def test_smoke_worker_interruption_and_recovery(...) -> None:
    result = run_worker_interruption_smoke(...)
    assert result.status == "recovered"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_dispatch.py tests/test_resolver_loop.py tests/test_end_to_end_smoke.py -q -k "worker_interrupted or recovered"`
Expected: FAIL because interruption and recovery are still represented too indirectly for clear smoke coverage.

- [ ] **Step 3: Implement explicit interruption and recovery modeling**

```python
if worker_disappeared_mid_attempt:
    deferred_reason = "worker_interrupted"
    can_retry = True
```

Implementation notes:
- Distinguish worker interruption from provider auth failure and from generic execution failure.
- Surface whether the operator can retry, reroute, or must re-bootstrap the worker.
- Keep the dispatch snapshot and materialized runtime vocabulary aligned.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_dispatch.py tests/test_resolver_loop.py tests/test_end_to_end_smoke.py -q -k "worker_interrupted or recovered"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/dispatch.py python/helaicopter_api/application/dispatch_monitor.py python/helaicopter_api/application/workers.py python/helaicopter_api/schema/dispatch.py tests/test_api_dispatch.py tests/test_resolver_loop.py tests/test_end_to_end_smoke.py
git commit -m "feat: expose worker interruption recovery states"
```

### Task 4: Tighten Operator Bootstrap and Queue Guidance Around Smoke-Critical States

**Files:**
- Modify: `python/helaicopter_api/application/operator_bootstrap.py`
- Modify: `python/helaicopter_api/schema/operator_bootstrap.py`
- Modify: `src/components/orchestration/operator-bootstrap-panel.tsx`
- Modify: `src/components/dispatch/queue-monitor.tsx`
- Create: `src/components/orchestration/operator-bootstrap-panel.test.tsx`
- Modify: `src/components/workers/worker-dashboard.tsx`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/types.ts`
- Modify: `tests/test_api_operator_bootstrap.py`

- [ ] **Step 1: Write the failing UI/API guidance tests**

```tsx
test("bootstrap panel explains smoke-critical blocked states", async () => {
  render(<OperatorBootstrapPanel bootstrap={fixture} />);
  expect(screen.getByText(/worker interrupted/i)).toBeInTheDocument();
  expect(screen.getByText(/retry or reroute/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_operator_bootstrap.py -q && node --import tsx --test src/components/orchestration/operator-bootstrap-panel.test.tsx`
Expected: FAIL because the operator guidance does not yet cover the full smoke-critical intervention states.

- [ ] **Step 3: Implement the bootstrap and queue guidance**

```ts
type OperatorNextStep =
  | "start_worker"
  | "refresh_auth"
  | "retry_or_reroute"
  | "resume_run";
```

Implementation notes:
- Keep the UI guidance concise and operational.
- Prioritize the smoke-critical failure classes: blocked auth, missing worker, worker interruption, paused run, reroute candidate.
- Avoid duplicating backend reasoning in the client; the API should remain authoritative.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_operator_bootstrap.py -q && node --import tsx --test src/components/orchestration/operator-bootstrap-panel.test.tsx src/components/workers/worker-dashboard.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/operator_bootstrap.py python/helaicopter_api/schema/operator_bootstrap.py src/components/orchestration/operator-bootstrap-panel.tsx src/components/dispatch/queue-monitor.tsx src/components/orchestration/operator-bootstrap-panel.test.tsx src/components/workers/worker-dashboard.tsx src/lib/client/normalize.ts src/lib/types.ts tests/test_api_operator_bootstrap.py
git commit -m "feat: add smoke-critical operator guidance"
```

### Task 5: Assemble the Release-Style Confidence Slice and Verify It

**Files:**
- Modify: `tests/test_end_to_end_smoke.py`
- Modify: `docs/orchestration/smoke-scenarios.md`
- Modify: `src/components/orchestration/oats-graph-view-model.test.ts`

- [ ] **Step 1: Expand the suite to the final acceptance set**

Required scenarios:
- cold start to healthy system
- Claude happy-path run
- Codex happy-path run
- auth failure visibility
- worker interruption and recovery
- operator pause/resume/retry/reroute visibility

- [ ] **Step 2: Run the full Phase 4 verification set**

Run: `uv run pytest tests/test_end_to_end_smoke.py tests/test_api_operator_controls.py tests/test_api_operator_bootstrap.py tests/test_api_dispatch.py tests/test_api_orchestration.py tests/test_resolver_loop.py tests/test_permanent_loop_integration.py -q`
Expected: PASS

Run: `node --import tsx --test src/components/orchestration/operator-bootstrap-panel.test.tsx src/components/orchestration/oats-graph-view-model.test.ts src/components/workers/worker-dashboard.test.tsx`
Expected: PASS

Run: `npm run build`
Expected: PASS

- [ ] **Step 3: Document the release gate**

Document in `docs/orchestration/smoke-scenarios.md`:
- what each scenario proves
- which failures are expected to block release
- which failures can be treated as known flake versus genuine regression

- [ ] **Step 4: Commit**

```bash
git add tests/test_end_to_end_smoke.py tests/test_api_operator_controls.py docs/orchestration/smoke-scenarios.md src/components/orchestration/oats-graph-view-model.test.ts
git commit -m "test: add orchestration end-to-end confidence suite"
```

## Definition of Done

- A compact smoke suite exists for the roadmap acceptance scenarios and passes reliably in local verification.
- Claude and Codex happy-path scenarios both assert against materialized runtime truth rather than vague UI impressions.
- Worker interruption, auth failure, and operator intervention produce explicit operator-visible states and remediation guidance.
- The team has a documented release-style definition of "usable end to end" for the current permanent-worker-loop system.

## Notes

- Keep the suite intentionally small and high-signal; this phase is about operational confidence, not exhaustive permutation coverage.
- If a scenario cannot be fully automated with the current architecture, document the manual checkpoint explicitly rather than hiding the gap.
- Do not pull Pi v2 or persistent-session design work into this phase unless a Phase 4 scenario proves Pi v1 cannot support the acceptance bar.
