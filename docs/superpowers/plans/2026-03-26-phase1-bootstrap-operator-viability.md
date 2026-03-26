# Phase 1 Bootstrap and Operator Viability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the permanent-worker-loop system operable from a clean local setup, with enough backend diagnostics, worker readiness state, UI guidance, and smoke coverage that an operator can bring up real Claude and Codex workers without tribal knowledge.

**Architecture:** Build a thin operator-readiness layer on top of the existing resolver, worker registry, auth surfaces, and `oats pi` worker CLI. The backend should expose an explicit bootstrap/readiness summary, the UI should explain blocked states instead of just listing raw records, and the Pi worker entry flow should become deterministic and documented rather than implicit. This phase does not redesign dispatch or runtime truth; it makes the current foundation understandable and operable.

**Tech Stack:** FastAPI, SQLAlchemy, Typer, Next.js, React, SWR, node:test/pytest

---

## File Structure

**Existing files to modify**

- `python/helaicopter_api/application/workers.py`
- `python/helaicopter_api/application/dispatch.py`
- `python/helaicopter_api/application/auth.py`
- `python/helaicopter_api/application/resolver.py`
- `python/helaicopter_api/router/workers.py`
- `python/helaicopter_api/router/auth.py`
- `python/helaicopter_api/server/lifespan.py`
- `python/helaicopter_api/bootstrap/services.py`
- `python/oats/cli.py`
- `python/oats/pi_worker.py`
- `src/components/workers/worker-dashboard.tsx`
- `src/components/workers/worker-card.tsx`
- `src/components/dispatch/queue-monitor.tsx`
- `src/components/orchestration/overnight-oats-panel.tsx`
- `src/lib/client/workers.ts`
- `src/lib/client/dispatch.ts`
- `src/lib/client/auth.ts`
- `src/lib/client/endpoints.ts`
- `src/lib/types.ts`
- `tests/test_api_workers.py`
- `tests/test_api_dispatch.py`
- `tests/test_api_auth_credentials.py`
- `tests/test_permanent_loop_integration.py`
- `tests/oats/test_pi_worker.py`
- `src/components/workers/worker-dashboard.test.tsx`
- `README.md`

**New files to create**

- `python/helaicopter_api/application/operator_bootstrap.py`
- `python/helaicopter_api/router/operator_bootstrap.py`
- `python/helaicopter_api/schema/operator_bootstrap.py`
- `tests/test_api_operator_bootstrap.py`
- `src/components/orchestration/operator-bootstrap-panel.tsx`
- `src/lib/client/operator-bootstrap.ts`
- `src/lib/client/schemas/operator-bootstrap.ts`
- `docs/orchestration/bootstrap.md`

**Responsibility split**

- `application/operator_bootstrap.py` owns the operator-facing readiness summary and “why dispatch is blocked” reasoning.
- `router/operator_bootstrap.py` and `schema/operator_bootstrap.py` expose the summary cleanly to the frontend and tests.
- `pi_worker.py` and `oats/cli.py` own worker startup ergonomics and preflight behavior.
- `worker-dashboard.tsx`, `queue-monitor.tsx`, and `operator-bootstrap-panel.tsx` turn low-level state into actionable operator messaging.
- `docs/orchestration/bootstrap.md` becomes the canonical cold-start sequence for humans.

### Task 1: Add a Backend Operator Bootstrap Summary

**Files:**
- Create: `python/helaicopter_api/application/operator_bootstrap.py`
- Create: `python/helaicopter_api/router/operator_bootstrap.py`
- Create: `python/helaicopter_api/schema/operator_bootstrap.py`
- Modify: `python/helaicopter_api/router/router.py`
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Test: `tests/test_api_operator_bootstrap.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_operator_bootstrap_reports_missing_workers(client) -> None:
    response = client.get("/operator/bootstrap")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overallStatus"] == "blocked"
    assert "no_registered_workers" in [reason["code"] for reason in payload["blockingReasons"]]


def test_operator_bootstrap_reports_provider_gaps(client, registered_claude_worker) -> None:
    response = client.get("/operator/bootstrap")
    payload = response.json()
    codes = [reason["code"] for reason in payload["blockingReasons"]]
    assert "missing_codex_worker" in codes


def test_operator_bootstrap_reports_ready_when_claude_and_codex_workers_exist(client) -> None:
    register_worker(client, provider="claude")
    register_worker(client, provider="codex")
    response = client.get("/operator/bootstrap")
    payload = response.json()
    assert payload["overallStatus"] == "ready"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_operator_bootstrap.py -q`
Expected: FAIL because the route and summary models do not exist yet.

- [ ] **Step 3: Implement the minimal backend summary**

```python
def build_operator_bootstrap_summary(services, resolver) -> OperatorBootstrapResponse:
    workers = list_workers(services.sqlite_engine)
    credentials = list_credentials(services.sqlite_engine)
    blocking_reasons = []

    if not workers:
        blocking_reasons.append(BootstrapReason(code="no_registered_workers", severity="error"))
    if not any(worker.provider == "claude" for worker in workers):
        blocking_reasons.append(BootstrapReason(code="missing_claude_worker", severity="warning"))
    if not any(worker.provider == "codex" for worker in workers):
        blocking_reasons.append(BootstrapReason(code="missing_codex_worker", severity="warning"))

    status = "ready" if not blocking_reasons else "blocked"
    return OperatorBootstrapResponse(overall_status=status, blocking_reasons=blocking_reasons)
```

Implementation notes:
- Keep the first version intentionally small and deterministic.
- Include resolver-running state, worker counts by provider/status, and credential counts by provider.
- Do not duplicate runtime truth from orchestration facts; this endpoint is a bootstrap/readiness view.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_operator_bootstrap.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/operator_bootstrap.py python/helaicopter_api/router/operator_bootstrap.py python/helaicopter_api/schema/operator_bootstrap.py python/helaicopter_api/router/router.py python/helaicopter_api/bootstrap/services.py tests/test_api_operator_bootstrap.py
git commit -m "feat: add operator bootstrap readiness summary"
```

### Task 2: Make Worker and Dispatch Blocked States Actionable

**Files:**
- Modify: `python/helaicopter_api/application/workers.py`
- Modify: `python/helaicopter_api/application/dispatch.py`
- Modify: `python/helaicopter_api/application/resolver.py`
- Modify: `python/helaicopter_api/router/workers.py`
- Modify: `python/helaicopter_api/schema/workers.py`
- Modify: `tests/test_api_workers.py`
- Modify: `tests/test_api_dispatch.py`
- Modify: `tests/test_permanent_loop_integration.py`

- [ ] **Step 1: Write failing tests for blocked-state explanations**

```python
def test_next_task_reports_blocked_reason_for_provider_mismatch(client, registered_claude_worker) -> None:
    response = client.get(f"/workers/{registered_claude_worker}/next-task")
    assert response.status_code == 204
    snapshot = client.get("/dispatch/queue").json()
    assert snapshot["deferred"][0]["reason"] == "no_capable_worker"


def test_operator_bootstrap_surface_marks_auth_expired_worker_as_blocking(client, auth_expired_worker) -> None:
    payload = client.get("/operator/bootstrap").json()
    assert "auth_expired_workers" in [reason["code"] for reason in payload["blockingReasons"]]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_workers.py tests/test_api_dispatch.py tests/test_permanent_loop_integration.py -q -k "blocked or auth_expired or capable_worker"`
Expected: FAIL because blocked reasons are not yet normalized into a consistent operator-facing contract.

- [ ] **Step 3: Implement normalized blocked-state metadata**

```python
BLOCKED_REASON_LABELS = {
    "no_capable_worker": "No eligible worker can run this task.",
    "auth_expired": "A worker exists, but its provider auth must be refreshed.",
    "worker_draining": "Matching worker is draining and cannot accept new work.",
}
```

Implementation notes:
- Add a small shared mapping for deferred dispatch reasons and worker readiness reasons.
- Ensure the resolver and queue snapshot preserve machine-readable codes.
- Extend worker detail responses with an optional `readinessReason` field when status is not actionable by itself.
- Keep Phase 1 scoped to explanation, not to deeper dispatch redesign.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_workers.py tests/test_api_dispatch.py tests/test_permanent_loop_integration.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/workers.py python/helaicopter_api/application/dispatch.py python/helaicopter_api/application/resolver.py python/helaicopter_api/router/workers.py python/helaicopter_api/schema/workers.py tests/test_api_workers.py tests/test_api_dispatch.py tests/test_permanent_loop_integration.py
git commit -m "feat: explain blocked dispatch and worker readiness states"
```

### Task 3: Surface Bootstrap and Readiness Guidance in the UI

**Files:**
- Create: `src/components/orchestration/operator-bootstrap-panel.tsx`
- Create: `src/lib/client/operator-bootstrap.ts`
- Create: `src/lib/client/schemas/operator-bootstrap.ts`
- Modify: `src/components/orchestration/overnight-oats-panel.tsx`
- Modify: `src/components/workers/worker-dashboard.tsx`
- Modify: `src/components/workers/worker-card.tsx`
- Modify: `src/components/dispatch/queue-monitor.tsx`
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/types.ts`
- Test: `src/components/workers/worker-dashboard.test.tsx`
- Test: `src/components/orchestration/tabs.test.ts`

- [ ] **Step 1: Write failing UI tests for operator guidance**

```tsx
test("shows bootstrap checklist when no workers are registered", () => {
  render(<OperatorBootstrapPanel summary={blockedSummary} />);
  expect(screen.getByText(/start a claude worker/i)).toBeInTheDocument();
  expect(screen.getByText(/start a codex worker/i)).toBeInTheDocument();
});

test("shows auth remediation banner when workers are auth_expired", () => {
  render(<WorkerDashboardSection workers={[authExpiredWorker]} />);
  expect(screen.getByText(/credential refresh/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- src/components/workers/worker-dashboard.test.tsx src/components/orchestration/tabs.test.ts`
Expected: FAIL because the operator bootstrap panel and richer readiness copy do not exist yet.

- [ ] **Step 3: Implement the minimal UI surfaces**

```tsx
<OperatorBootstrapPanel summary={summary}>
  <ChecklistItem done={summary.hasClaudeWorker}>Start a Claude worker</ChecklistItem>
  <ChecklistItem done={summary.hasCodexWorker}>Start a Codex worker</ChecklistItem>
  <ChecklistItem done={summary.resolverRunning}>Backend resolver loop running</ChecklistItem>
</OperatorBootstrapPanel>
```

Implementation notes:
- Put the bootstrap panel near the top of `overnight-oats-panel.tsx`.
- Reuse existing worker and queue data instead of duplicating cards.
- Prefer explicit action text over generic status labels.
- Keep the copy short and operational: “what to do next” and “why dispatch is blocked.”

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test -- src/components/workers/worker-dashboard.test.tsx src/components/orchestration/tabs.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/components/orchestration/operator-bootstrap-panel.tsx src/lib/client/operator-bootstrap.ts src/lib/client/schemas/operator-bootstrap.ts src/components/orchestration/overnight-oats-panel.tsx src/components/workers/worker-dashboard.tsx src/components/workers/worker-card.tsx src/components/dispatch/queue-monitor.tsx src/lib/client/endpoints.ts src/lib/types.ts src/components/workers/worker-dashboard.test.tsx src/components/orchestration/tabs.test.ts
git commit -m "feat: add operator bootstrap guidance to orchestration UI"
```

### Task 4: Harden the Pi Worker Startup Flow

**Files:**
- Modify: `python/oats/cli.py`
- Modify: `python/oats/pi_worker.py`
- Modify: `tests/oats/test_pi_worker.py`
- Modify: `README.md`
- Create: `docs/orchestration/bootstrap.md`

- [ ] **Step 1: Write failing CLI and worker startup tests**

```python
def test_pi_cli_requires_provider_and_at_least_one_model(cli_runner) -> None:
    result = cli_runner.invoke(app, ["pi", "run", "--provider", "claude"])
    assert result.exit_code != 0
    assert "Missing option '--model'" in result.output


def test_pi_worker_preflight_surfaces_control_plane_connection_error(fake_runner) -> None:
    worker = PiWorker(provider="claude", models=["claude-sonnet-4-6"], control_plane_url="http://127.0.0.1:9")
    with pytest.raises(ControlPlaneUnavailableError):
        asyncio.run(worker.register())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/oats/test_pi_worker.py -q`
Expected: FAIL because the current startup path does not provide a strong preflight contract or clear operator-facing failures.

- [ ] **Step 3: Implement preflight and operator-friendly startup behavior**

```python
def preflight(self) -> list[str]:
    issues = []
    if not self.models:
        issues.append("No model capabilities configured.")
    if not self.control_plane_url:
        issues.append("Control plane URL is required.")
    return issues
```

Implementation notes:
- Add a small preflight step before entering `run_loop()`.
- Make registration failures print a clear message that references the control plane URL and provider.
- Print the assigned worker ID and advertised models on successful registration.
- Update `docs/orchestration/bootstrap.md` and `README.md` with canonical commands for one Claude worker and one Codex worker.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/oats/test_pi_worker.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/oats/cli.py python/oats/pi_worker.py tests/oats/test_pi_worker.py README.md docs/orchestration/bootstrap.md
git commit -m "feat: harden Pi worker bootstrap flow and docs"
```

### Task 5: Add a Cold-Start Operator Smoke Test

**Files:**
- Modify: `tests/test_permanent_loop_integration.py`
- Modify: `tests/test_api_operator_bootstrap.py`
- Modify: `tests/test_api_workers.py`

- [ ] **Step 1: Write the failing cold-start smoke test**

```python
def test_cold_start_reaches_ready_after_registering_claude_and_codex_workers(client) -> None:
    payload = client.get("/operator/bootstrap").json()
    assert payload["overallStatus"] == "blocked"

    register_worker(client, provider="claude")
    register_worker(client, provider="codex")

    payload = client.get("/operator/bootstrap").json()
    assert payload["overallStatus"] == "ready"
    assert payload["blockingReasons"] == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_api_operator_bootstrap.py tests/test_permanent_loop_integration.py -q -k "cold_start or ready"`
Expected: FAIL until the bootstrap summary, worker readiness, and startup assumptions line up.

- [ ] **Step 3: Make the minimal cross-layer fixes**

Implementation notes:
- Only fix issues exposed by the smoke test.
- Do not expand into Phase 2 materialization work.
- Prefer small backend contract fixes over frontend-only masking.

- [ ] **Step 4: Run the test suite slice to verify it passes**

Run: `uv run pytest tests/test_api_operator_bootstrap.py tests/test_api_workers.py tests/test_api_dispatch.py tests/test_permanent_loop_integration.py tests/oats/test_pi_worker.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_api_operator_bootstrap.py tests/test_api_workers.py tests/test_api_dispatch.py tests/test_permanent_loop_integration.py tests/oats/test_pi_worker.py
git commit -m "test: add bootstrap and operator viability smoke coverage"
```

### Task 6: Verify the Whole Phase 1 Slice

**Files:**
- Modify: `docs/orchestration/bootstrap.md`
- Modify: `README.md`

- [ ] **Step 1: Run backend verification**

Run: `uv run pytest tests/test_api_operator_bootstrap.py tests/test_api_workers.py tests/test_api_dispatch.py tests/test_permanent_loop_integration.py tests/oats/test_pi_worker.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run: `npm test -- src/components/workers/worker-dashboard.test.tsx src/components/orchestration/tabs.test.ts`
Expected: PASS

- [ ] **Step 3: Run a manual operator bootstrap check**

Run: `npm run dev`
Expected:
- backend starts with resolver loop active
- orchestration UI shows bootstrap panel
- running `uv run oats pi run --provider claude --model claude-sonnet-4-6 --control-plane http://127.0.0.1:30000` registers a Claude worker
- running `uv run oats pi run --provider codex --model o3-pro --control-plane http://127.0.0.1:30000` registers a Codex worker

- [ ] **Step 4: Update docs with the verified commands**

```md
1. Start Helaicopter with `npm run dev`
2. Start one Claude worker with `uv run oats pi run ...`
3. Start one Codex worker with `uv run oats pi run ...`
4. Confirm `/operator/bootstrap` reports `ready`
```

- [ ] **Step 5: Commit**

```bash
git add docs/orchestration/bootstrap.md README.md
git commit -m "docs: capture verified bootstrap and operator workflow"
```
