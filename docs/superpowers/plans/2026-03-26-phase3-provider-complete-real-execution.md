# Phase 3 Provider-Complete Real Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude and Codex genuinely runnable through the permanent-worker-loop system with real credential validation, provider-aware dispatch gating, and operator-visible remediation when auth or provider requirements are not met.

**Architecture:** Keep the existing worker loop and runtime materialization flow from Phases 1 and 2, but add a provider-readiness layer that sits between credential state, worker capability metadata, dispatch eligibility, and Pi worker execution. The backend should become the authority for whether a provider is runnable right now, while the UI and Pi worker surface that readiness and failure context without forcing operators to infer it from low-level states.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, SQLite-backed auth credentials and subscription settings, permanent resolver loop, Pi worker subprocess orchestration, Next.js, React, SWR, pytest, node:test

---

## File Structure

**Existing files to modify**

- `python/helaicopter_api/application/auth.py`
- `python/helaicopter_api/application/dispatch.py`
- `python/helaicopter_api/application/dispatch_monitor.py`
- `python/helaicopter_api/application/operator_bootstrap.py`
- `python/helaicopter_api/application/workers.py`
- `python/helaicopter_api/application/resolver.py`
- `python/helaicopter_api/schema/auth.py`
- `python/helaicopter_api/schema/dispatch.py`
- `python/helaicopter_api/schema/workers.py`
- `python/helaicopter_api/router/workers.py`
- `python/oats/pi_worker.py`
- `python/oats/cli.py`
- `src/components/auth/auth-management-section.tsx`
- `src/components/dispatch/queue-monitor.tsx`
- `src/components/orchestration/operator-bootstrap-panel.tsx`
- `src/components/workers/worker-card.tsx`
- `src/components/workers/worker-dashboard.tsx`
- `src/lib/client/normalize.ts`
- `src/lib/types.ts`
- `tests/test_api_dispatch.py`
- `tests/test_api_workers.py`
- `tests/test_permanent_loop_integration.py`
- `tests/oats/test_pi_worker.py`

**New files to create**

- `python/helaicopter_api/application/provider_readiness.py`
- `python/helaicopter_api/schema/provider_readiness.py`
- `tests/test_provider_readiness.py`
- `tests/test_api_provider_readiness.py`

**Responsibility split**

- `provider_readiness.py` owns the provider-complete read model: whether Claude or Codex is runnable, blocked, degraded, or misconfigured, and why.
- `auth.py` owns credential-state validation and provider-specific status normalization.
- `dispatch.py`, `dispatch_monitor.py`, and `resolver.py` consume provider readiness when deciding dispatch eligibility and deferred reasons.
- `workers.py` and `pi_worker.py` own worker-side registration and execution preflight feedback that maps cleanly onto provider readiness.
- Frontend auth, worker, bootstrap, and dispatch components surface the readiness model and remediation guidance without inventing their own rules.

### Task 1: Define the Provider Readiness Contract

**Files:**
- Create: `python/helaicopter_api/application/provider_readiness.py`
- Create: `python/helaicopter_api/schema/provider_readiness.py`
- Create: `tests/test_provider_readiness.py`
- Modify: `python/helaicopter_api/application/auth.py`

- [ ] **Step 1: Write the failing provider readiness tests**

```python
def test_provider_readiness_marks_provider_runnable_when_active_credential_and_ready_worker_exist() -> None:
    readiness = build_provider_readiness(...)
    assert readiness.provider == "claude"
    assert readiness.status == "ready"


def test_provider_readiness_explains_missing_auth_and_missing_worker_separately() -> None:
    readiness = build_provider_readiness(...)
    assert readiness.status == "blocked"
    assert "credential" in readiness.blocking_reasons[0].message.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_provider_readiness.py -q`
Expected: FAIL because the provider readiness contract does not exist yet.

- [ ] **Step 3: Implement the minimal provider readiness read model**

```python
class ProviderReadinessResponse(CamelCaseHttpResponseModel):
    provider: str
    status: str
    healthy_worker_count: int
    ready_worker_count: int
    active_credential_count: int
    blocking_reasons: list[ProviderBlockingReason]
```

Implementation notes:
- Read from current credential rows and registered workers only in this task.
- Treat Claude and Codex symmetrically where possible.
- Distinguish `blocked` from `degraded` so “can run, but weakly configured” is separate from “cannot run at all”.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_provider_readiness.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/provider_readiness.py python/helaicopter_api/schema/provider_readiness.py python/helaicopter_api/application/auth.py tests/test_provider_readiness.py
git commit -m "feat: add provider readiness contract"
```

### Task 2: Normalize Real Credential Validation Into Actionable Provider Status

**Files:**
- Modify: `python/helaicopter_api/application/auth.py`
- Modify: `python/helaicopter_api/schema/auth.py`
- Test: `tests/test_api_workers.py`
- Test: `tests/test_provider_readiness.py`

- [ ] **Step 1: Write the failing credential validation tests**

```python
def test_local_cli_session_credential_without_config_is_not_provider_ready() -> None:
    readiness = build_provider_readiness(...)
    assert readiness.status == "blocked"
    assert readiness.blocking_reasons[0].code == "missing_cli_session"


def test_expired_oauth_credential_is_reported_as_expired_not_generic_failure() -> None:
    response = refresh_credential(...)
    assert response.status == "expired"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_provider_readiness.py tests/test_api_workers.py -q -k "cli_session or expired"`
Expected: FAIL because credential readiness is still too generic.

- [ ] **Step 3: Implement provider-aware credential validation**

```python
def credential_provider_status(row: AuthCredentialRecord) -> CredentialProviderStatus:
    if row.status == "revoked":
        return CredentialProviderStatus(code="revoked", runnable=False)
    if row.credential_type == "local_cli_session" and not row.cli_config_path:
        return CredentialProviderStatus(code="missing_cli_session", runnable=False)
```

Implementation notes:
- Preserve existing CRUD behavior.
- Add provider-facing status metadata rather than overloading the old `status` string alone.
- Keep OAuth refresh logic authoritative for oauth-token expiry transitions.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_provider_readiness.py tests/test_api_workers.py -q -k "cli_session or expired"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/auth.py python/helaicopter_api/schema/auth.py tests/test_provider_readiness.py tests/test_api_workers.py
git commit -m "feat: add actionable provider credential validation"
```

### Task 3: Apply Provider Readiness to Dispatch and Queue Blocking Reasons

**Files:**
- Modify: `python/helaicopter_api/application/dispatch.py`
- Modify: `python/helaicopter_api/application/dispatch_monitor.py`
- Modify: `python/helaicopter_api/application/resolver.py`
- Modify: `python/helaicopter_api/schema/dispatch.py`
- Test: `tests/test_api_dispatch.py`
- Test: `tests/test_permanent_loop_integration.py`

- [ ] **Step 1: Write the failing dispatch gating tests**

```python
def test_dispatch_monitor_reports_provider_auth_block_when_worker_exists_but_provider_is_not_runnable() -> None:
    snapshot = build_dispatch_snapshot(...)
    assert snapshot.deferred_tasks[0].reason == "provider_not_ready"


def test_resolver_does_not_dispatch_codex_task_when_only_claude_provider_is_ready() -> None:
    resolver.tick()
    assert graph.get_node("task_codex").status == "pending"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_dispatch.py tests/test_permanent_loop_integration.py -q -k "provider_not_ready or codex_task"`
Expected: FAIL because dispatch only considers coarse worker/auth states today.

- [ ] **Step 3: Implement provider-aware dispatch gating**

```python
if not readiness_by_provider[provider].is_runnable:
    deferred_reason = "provider_not_ready"
    continue
```

Implementation notes:
- Keep worker capability matching and provider readiness separate concepts.
- Add a distinct deferred reason for “provider exists in theory, but is not runnable right now”.
- Avoid dispatching into Pi workers that will fail immediately due to missing provider auth.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_dispatch.py tests/test_permanent_loop_integration.py -q -k "provider_not_ready or codex_task"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/dispatch.py python/helaicopter_api/application/dispatch_monitor.py python/helaicopter_api/application/resolver.py python/helaicopter_api/schema/dispatch.py tests/test_api_dispatch.py tests/test_permanent_loop_integration.py
git commit -m "feat: gate dispatch on provider readiness"
```

### Task 4: Expose Provider Readiness Through Backend Worker and Operator Surfaces

**Files:**
- Modify: `python/helaicopter_api/application/workers.py`
- Modify: `python/helaicopter_api/application/operator_bootstrap.py`
- Modify: `python/helaicopter_api/router/workers.py`
- Create: `tests/test_api_provider_readiness.py`
- Test: `tests/test_api_workers.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_workers_index_includes_provider_readiness_metadata(client) -> None:
    payload = client.get("/workers").json()
    assert payload["providers"][0]["provider"] == "claude"
    assert payload["providers"][0]["status"] == "blocked"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_provider_readiness.py tests/test_api_workers.py -q`
Expected: FAIL because provider readiness is not exposed yet.

- [ ] **Step 3: Implement the backend exposure**

```python
class WorkerIndexResponse(CamelCaseHttpResponseModel):
    workers: list[WorkerResponse]
    providers: list[ProviderReadinessResponse]
```

Implementation notes:
- Prefer adding provider readiness to existing worker/bootstrap responses before inventing a separate operator-only route unless the API shape becomes awkward.
- Keep the payloads small and operator-facing.
- Make sure Claude and Codex are both present when known through credentials or workers, even if one side is blocked.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_api_provider_readiness.py tests/test_api_workers.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/workers.py python/helaicopter_api/application/operator_bootstrap.py python/helaicopter_api/router/workers.py tests/test_api_provider_readiness.py tests/test_api_workers.py
git commit -m "feat: expose provider readiness in operator APIs"
```

### Task 5: Harden Pi Worker Preflight and Execution Remediation for Real Providers

**Files:**
- Modify: `python/oats/pi_worker.py`
- Modify: `python/oats/cli.py`
- Test: `tests/oats/test_pi_worker.py`
- Test: `tests/test_permanent_loop_integration.py`

- [ ] **Step 1: Write the failing Pi worker tests**

```python
def test_pi_worker_preflight_reports_missing_provider_auth_context() -> None:
    worker = PiWorker(provider="codex", models=["o3-pro"], control_plane_url="http://localhost:8000")
    assert "auth" in worker.preflight()[0].lower()


def test_pi_worker_result_surfaces_provider_cli_failure_as_actionable_error() -> None:
    result = await worker.run_one_cycle()
    assert "session" in reported_payload["error_summary"].lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/oats/test_pi_worker.py tests/test_permanent_loop_integration.py -q -k "preflight or session"`
Expected: FAIL because Pi worker preflight and result reporting are still too generic.

- [ ] **Step 3: Implement the Pi worker hardening**

```python
def preflight(self) -> list[str]:
    issues = []
    if self.provider == "codex" and not self._has_local_cli_context():
        issues.append("Codex local CLI session is not configured.")
```

Implementation notes:
- Keep provider checks lightweight and local.
- Prefer explicit remediation text over opaque subprocess failures.
- Do not add persistent-session behavior here; that belongs to Phase 5.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/oats/test_pi_worker.py tests/test_permanent_loop_integration.py -q -k "preflight or session"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python/oats/pi_worker.py python/oats/cli.py tests/oats/test_pi_worker.py tests/test_permanent_loop_integration.py
git commit -m "feat: harden pi worker provider preflight"
```

### Task 6: Surface Provider Readiness and Remediation in the Operator UI

**Files:**
- Modify: `src/components/auth/auth-management-section.tsx`
- Modify: `src/components/dispatch/queue-monitor.tsx`
- Modify: `src/components/orchestration/operator-bootstrap-panel.tsx`
- Modify: `src/components/workers/worker-card.tsx`
- Modify: `src/components/workers/worker-dashboard.tsx`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/types.ts`
- Test: `src/components/workers/worker-dashboard.test.tsx`
- Test: `src/lib/client/normalize.test.ts`

- [ ] **Step 1: Write the failing frontend tests**

```ts
test("worker dashboard surfaces provider readiness and remediation copy", () => {
  const dashboard = renderDashboard(providerReadinessPayload);
  assert.match(dashboard.textContent ?? "", /credential refresh/i);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --import tsx --test src/components/workers/worker-dashboard.test.tsx src/lib/client/normalize.test.ts`
Expected: FAIL because provider readiness metadata is not normalized or rendered yet.

- [ ] **Step 3: Implement the frontend wiring**

```ts
export interface ProviderReadiness {
  provider: "claude" | "codex";
  status: "ready" | "degraded" | "blocked";
  blockingReasons: Array<{ code: string; message: string }>;
}
```

Implementation notes:
- Prefer additive UI: show provider health alongside workers and auth panels.
- Do not bury provider readiness inside individual worker cards only; operators need both provider-level and worker-level views.
- Reuse wording from backend reasons so remediation stays consistent.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --import tsx --test src/components/workers/worker-dashboard.test.tsx src/lib/client/normalize.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/components/auth/auth-management-section.tsx src/components/dispatch/queue-monitor.tsx src/components/orchestration/operator-bootstrap-panel.tsx src/components/workers/worker-card.tsx src/components/workers/worker-dashboard.tsx src/lib/client/normalize.ts src/lib/types.ts src/components/workers/worker-dashboard.test.tsx src/lib/client/normalize.test.ts
git commit -m "feat: show provider readiness in operator ui"
```

### Task 7: Add Phase 3 Provider-Complete Smoke Coverage

**Files:**
- Modify: `tests/test_provider_readiness.py`
- Modify: `tests/test_api_dispatch.py`
- Modify: `tests/test_api_workers.py`
- Modify: `tests/test_permanent_loop_integration.py`
- Modify: `tests/oats/test_pi_worker.py`

- [ ] **Step 1: Write the failing smoke scenarios**

```python
def test_claude_provider_happy_path_is_runnable_when_worker_and_credential_are_ready() -> None:
    readiness = build_provider_readiness(...)
    assert readiness.status == "ready"


def test_codex_provider_blocked_state_explains_missing_local_cli_session() -> None:
    readiness = build_provider_readiness(...)
    assert readiness.blocking_reasons[0].code == "missing_cli_session"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_provider_readiness.py tests/test_api_dispatch.py tests/test_api_workers.py tests/test_permanent_loop_integration.py tests/oats/test_pi_worker.py -q -k "provider_happy_path or missing_local_cli_session or provider_not_ready"`
Expected: FAIL until the provider-complete layer is coherent across auth, dispatch, and Pi worker behavior.

- [ ] **Step 3: Make the smallest cross-layer fixes**

Implementation notes:
- Only fix issues that block the provider-readiness smoke slice.
- Do not pull Pi v2 or persistent-session work into this phase.
- Favor explicit operator-visible reasons over implicit fallback behavior.

- [ ] **Step 4: Run the full Phase 3 verification slice**

Run: `uv run pytest tests/test_provider_readiness.py tests/test_api_provider_readiness.py tests/test_api_dispatch.py tests/test_api_workers.py tests/test_permanent_loop_integration.py tests/oats/test_pi_worker.py -q`
Expected: PASS

- [ ] **Step 5: Run frontend verification**

Run: `node --import tsx --test src/components/workers/worker-dashboard.test.tsx src/lib/client/normalize.test.ts`
Expected: PASS

- [ ] **Step 6: Run build verification**

Run: `npm run build`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add tests/test_provider_readiness.py tests/test_api_provider_readiness.py tests/test_api_dispatch.py tests/test_api_workers.py tests/test_permanent_loop_integration.py tests/oats/test_pi_worker.py src/components/workers/worker-dashboard.test.tsx src/lib/client/normalize.test.ts
git commit -m "test: add provider-complete orchestration coverage"
```
