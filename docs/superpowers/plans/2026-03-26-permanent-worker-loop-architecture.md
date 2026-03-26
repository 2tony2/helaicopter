# Permanent Worker Loop Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the OATS graph-native runtime from a CLI-invoked batch executor to a permanent resolver loop backed by a worker registry with provider-aware dispatch, adapter-based auth management, and operator UI control surfaces. Promote orchestrate-run patterns into first-class runtime primitives. Integrate Pi v1 (supervisor-style worker shell that spawns per-task provider subprocesses) as the canonical long-lived worker.

**Architecture:** A single Helaicopter backend process runs a background resolver loop (asyncio task) that continuously evaluates graph edges, dispatches ready tasks to registered workers, processes completions and heartbeats, and manages auth credential lifecycle. Workers (Pi v1 shells) register via HTTP, pull tasks, spawn per-task CLI subprocesses, and report results. The operator UI becomes a real-time control console. State authority is split: task graph and results in `.oats/runtime/` (file-based), worker registry and auth credentials in SQLite — no duplicated authority (see design spec for full ownership table).

**Depends on:** `plans/2026-03-25-oats-graph-native-runtime-v2.md` (graph runtime, typed edges, scheduler, discovery, envelopes — must be substantially complete before starting this plan)

**Design spec:** `specs/2026-03-26-permanent-worker-loop-architecture-design.md`

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, Alembic, asyncio, Next.js 16, React 19, SWR, `pytest`, `node:test`, `tsx`

---

## Prerequisites

The v2 graph-native runtime (Tasks 1–8 of the prior plan) must be complete or near-complete. Specifically:
- `graph.py`, `scheduler.py`, `envelope.py`, `discovery.py`, `identity.py` must exist and be tested.
- The ready-queue scheduler, typed edge evaluation, and execution envelope protocol must be working.
- Backend graph API must be serving `nodes`, `edges`, `readyQueue` responses.

---

### Task 1: Worker Registry Data Model and API

**Why:** The worker registry is the foundation for everything else. Without it, workers can't register, the resolver can't dispatch, and the UI can't show worker status. This is a pure data-model + CRUD task with no resolver loop complexity.

**Files:**
- New: `python/alembic/versions/20260326_0001_worker_registry.py`
- New: `python/helaicopter_api/schema/workers.py`
- New: `python/helaicopter_api/application/workers.py`
- New: `python/helaicopter_api/router/workers.py`
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Modify: `python/helaicopter_api/server/app.py` (register router)
- New: `tests/test_api_workers.py`

- [ ] **Step 1: Write failing tests for worker registration, heartbeat, and lifecycle**

```python
# test_api_workers.py
def test_register_worker_returns_worker_id(client) -> None:
    response = client.post("/workers/register", json={
        "workerType": "pi_shell",
        "provider": "claude",
        "capabilities": {
            "provider": "claude",
            "models": ["claude-sonnet-4-6", "claude-opus-4-6"],
            "maxConcurrentTasks": 1,
            "supportsDiscovery": True,
            "supportsResume": True,
            "tags": [],
        },
        "host": "local",
        "pid": 12345,
    })
    assert response.status_code == 201
    payload = response.json()
    assert payload["workerId"].startswith("wkr_")
    assert payload["status"] == "idle"

def test_heartbeat_updates_last_seen(client, registered_worker) -> None:
    response = client.post(f"/workers/{registered_worker}/heartbeat", json={
        "status": "idle",
    })
    assert response.status_code == 200

def test_deregister_worker(client, registered_worker) -> None:
    response = client.delete(f"/workers/{registered_worker}")
    assert response.status_code == 204
    # Verify gone
    response = client.get(f"/workers")
    workers = response.json()
    assert registered_worker not in [w["workerId"] for w in workers]

def test_list_workers_filters_by_provider(client, claude_worker, codex_worker) -> None:
    response = client.get("/workers?provider=claude")
    workers = response.json()
    assert all(w["provider"] == "claude" for w in workers)

def test_drain_worker_prevents_new_dispatch(client, busy_worker) -> None:
    response = client.post(f"/workers/{busy_worker}/drain")
    assert response.status_code == 200
    # Worker should be draining, not idle
    response = client.get(f"/workers/{busy_worker}")
    assert response.json()["status"] == "draining"
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `uv run --group dev pytest tests/test_api_workers.py -q`

- [ ] **Step 3: Create alembic migration for worker_registry table**

```python
# 20260326_0001_worker_registry.py
# Columns: worker_id (PK), worker_type, provider, capabilities_json,
#           auth_credential_id (FK nullable), host, pid, worktree_root,
#           registered_at, last_heartbeat_at, status, current_task_id,
#           current_run_id, metadata_json
```

- [ ] **Step 4: Implement schema, application, and router layers**

- `schema/workers.py`: `WorkerRegistrationRequest`, `WorkerRegistrationResponse`, `WorkerHeartbeatRequest`, `WorkerListResponse`, `WorkerDetailResponse`.
- `application/workers.py`: CRUD operations against `worker_registry` table. Heartbeat update. Drain logic. List with provider filter.
- `router/workers.py`: REST endpoints — `POST /register`, `GET /`, `GET /{id}`, `POST /{id}/heartbeat`, `POST /{id}/drain`, `DELETE /{id}`.
- Wire into `services.py` and `app.py`.

- [ ] **Step 5: Run tests, confirm they pass**

Run: `uv run --group dev pytest tests/test_api_workers.py -q`

- [ ] **Step 6: Commit**

```bash
git add python/alembic/versions/20260326_0001_worker_registry.py \
        python/helaicopter_api/schema/workers.py \
        python/helaicopter_api/application/workers.py \
        python/helaicopter_api/router/workers.py \
        python/helaicopter_api/bootstrap/services.py \
        python/helaicopter_api/server/app.py \
        tests/test_api_workers.py
git commit -m "feat: worker registry data model and CRUD API"
```

---

### Task 2: Auth Credential Store and Management API (Adapter Pattern)

**Why:** Workers need credentials to authenticate with upstream providers. The credential store uses an adapter pattern supporting three tiers: managed OAuth/subscription (OpenClaw reference direction), delegated local CLI session reuse (`~/.claude`, `~/.codex`), and API key fallback. This decouples auth from environment variables and enables per-worker auth, expiry tracking, and cost association. This must exist before the resolver loop can do provider-aware dispatch.

**Files:**
- New: `python/alembic/versions/20260326_0002_auth_credentials.py`
- New: `python/helaicopter_api/schema/auth.py`
- New: `python/helaicopter_api/application/auth.py`
- New: `python/helaicopter_api/router/auth.py`
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Modify: `python/helaicopter_api/server/app.py`
- New: `tests/test_api_auth_credentials.py`

- [ ] **Step 1: Write failing tests for credential CRUD and status lifecycle**

```python
# test_api_auth_credentials.py
def test_create_api_key_credential(client) -> None:
    response = client.post("/auth/credentials", json={
        "provider": "claude",
        "credentialType": "api_key",
        "apiKey": "sk-ant-test-key",
    })
    assert response.status_code == 201
    payload = response.json()
    assert payload["credentialId"].startswith("cred_")
    assert payload["status"] == "active"
    # API key must not be returned in cleartext
    assert "apiKey" not in payload

def test_list_credentials_shows_status_not_secrets(client, claude_cred, codex_cred) -> None:
    response = client.get("/auth/credentials")
    creds = response.json()
    assert len(creds) == 2
    for c in creds:
        assert "accessToken" not in c
        assert "apiKey" not in c
        assert "status" in c

def test_revoke_credential_sets_status(client, active_credential) -> None:
    response = client.delete(f"/auth/credentials/{active_credential}")
    assert response.status_code == 200
    # Verify status
    response = client.get("/auth/credentials")
    cred = [c for c in response.json() if c["credentialId"] == active_credential][0]
    assert cred["status"] == "revoked"

def test_credential_with_expiry_shows_expires_at(client) -> None:
    response = client.post("/auth/credentials", json={
        "provider": "codex",
        "credentialType": "oauth_token",
        "accessToken": "fake-token",
        "tokenExpiresAt": "2026-04-01T00:00:00Z",
    })
    payload = response.json()
    assert payload["tokenExpiresAt"] is not None

def test_update_cost_tracking(client, active_credential) -> None:
    response = client.post(f"/auth/credentials/{active_credential}/record-cost", json={
        "costUsd": 1.50,
    })
    assert response.status_code == 200
    # Verify cumulative
    response = client.get("/auth/credentials")
    cred = [c for c in response.json() if c["credentialId"] == active_credential][0]
    assert cred["cumulativeCostUsd"] == 1.50
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `uv run --group dev pytest tests/test_api_auth_credentials.py -q`

- [ ] **Step 3: Create alembic migration for auth_credentials table**

Columns: `credential_id` (PK), `provider`, `credential_type` (one of: `oauth_token`, `api_key`, `local_cli_session`), `access_token_encrypted`, `refresh_token_encrypted`, `token_expires_at`, `oauth_scopes_json`, `api_key_encrypted`, `cli_config_path`, `subscription_id`, `subscription_tier`, `rate_limit_tier`, `status`, `created_at`, `last_used_at`, `last_refreshed_at`, `cumulative_cost_usd`, `cost_since_reset`.

Add FK from `worker_registry.auth_credential_id` → `auth_credentials.credential_id`.

- [ ] **Step 4: Implement schema, application, and router layers**

- `schema/auth.py`: Request/response models. Never expose secrets in responses.
- `application/auth.py`: CRUD with encryption for token/key fields (use `cryptography.fernet` with app secret). Cost recording. Status transitions.
- `router/auth.py`: `POST /auth/credentials`, `GET /auth/credentials`, `DELETE /auth/credentials/{id}`, `POST /auth/credentials/{id}/record-cost`, `POST /auth/credentials/{id}/refresh`.

- [ ] **Step 5: Run tests, confirm they pass**

Run: `uv run --group dev pytest tests/test_api_auth_credentials.py -q`

- [ ] **Step 6: Commit**

```bash
git add python/alembic/versions/20260326_0002_auth_credentials.py \
        python/helaicopter_api/schema/auth.py \
        python/helaicopter_api/application/auth.py \
        python/helaicopter_api/router/auth.py \
        python/helaicopter_api/bootstrap/services.py \
        python/helaicopter_api/server/app.py \
        tests/test_api_auth_credentials.py
git commit -m "feat: auth credential store with encrypted storage and cost tracking"
```

---

### Task 3: Resolver Loop Core

**Why:** The resolver loop is the heart of the permanent architecture. It replaces the single-process `oats run` execution loop with a continuously-running background task that processes events, evaluates edges, dispatches to workers, and reaps dead workers. This is the most complex task and depends on Tasks 1–2 and the v2 graph runtime.

**Files:**
- New: `python/helaicopter_api/application/resolver.py`
- New: `python/helaicopter_api/application/dispatch.py`
- Modify: `python/helaicopter_api/bootstrap/services.py`
- Modify: `python/helaicopter_api/server/app.py` (start resolver on startup)
- New: `tests/test_resolver_loop.py`

- [ ] **Step 1: Write failing tests for resolver loop behavior**

```python
# test_resolver_loop.py
@pytest.mark.asyncio
async def test_resolver_dispatches_ready_task_to_idle_worker() -> None:
    """When a task is ready and a capable idle worker exists, dispatch occurs."""
    registry = InMemoryWorkerRegistry()
    worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])

    graph = build_single_task_graph("auth", agent="claude", model="claude-sonnet-4-6")
    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph})

    await resolver.tick()

    assert worker.status == "busy"
    assert worker.current_task_id == "auth"

@pytest.mark.asyncio
async def test_resolver_defers_task_when_no_capable_worker() -> None:
    """A ready task for codex is deferred when only claude workers are available."""
    registry = InMemoryWorkerRegistry()
    registry.register(provider="claude", models=["claude-sonnet-4-6"])

    graph = build_single_task_graph("ml-task", agent="codex", model="o3-pro")
    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph})

    await resolver.tick()

    # Task should be deferred, not dispatched
    assert graph.get_node("ml-task").status == "pending"  # not running

@pytest.mark.asyncio
async def test_resolver_reaps_dead_worker_and_retries_task() -> None:
    """A worker that misses heartbeat threshold is reaped; its task is retried."""
    registry = InMemoryWorkerRegistry()
    worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])
    worker.last_heartbeat_at = datetime.now() - timedelta(minutes=5)
    worker.status = "busy"
    worker.current_task_id = "auth"

    graph = build_single_task_graph("auth", agent="claude", model="claude-sonnet-4-6")
    graph.get_node("auth").status = "running"

    resolver = ResolverLoop(
        registry=registry,
        graphs={"run_1": graph},
        heartbeat_timeout=timedelta(minutes=3),
    )

    await resolver.tick()

    assert worker.status == "dead"
    assert graph.get_node("auth").status == "pending"  # re-queued for retry

@pytest.mark.asyncio
async def test_resolver_processes_worker_completion() -> None:
    """Completion event triggers edge evaluation and may enqueue dependents."""
    registry = InMemoryWorkerRegistry()
    worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])

    graph = build_linear_graph(["a", "b"])
    graph.get_node("a").status = "running"
    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph})

    result = TaskResult(task_id="a", attempt_id="att_1", worker_id=worker.worker_id,
                        status="succeeded", duration_seconds=60.0)
    resolver.submit_completion(result)

    await resolver.tick()

    assert graph.get_node("a").status == "succeeded"
    # b should now be ready and dispatched
    assert graph.get_node("b").status == "running"

@pytest.mark.asyncio
async def test_resolver_skips_dispatch_for_expired_auth() -> None:
    """A worker with expired auth is skipped during dispatch."""
    registry = InMemoryWorkerRegistry()
    worker = registry.register(provider="claude", models=["claude-sonnet-4-6"],
                                auth_status="expired")

    graph = build_single_task_graph("auth", agent="claude", model="claude-sonnet-4-6")
    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph})

    await resolver.tick()

    assert graph.get_node("auth").status == "pending"  # not dispatched
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `uv run --group dev pytest tests/test_resolver_loop.py -q`

- [ ] **Step 3: Implement resolver loop and dispatch logic**

Key implementation:
- `resolver.py`: `ResolverLoop` class with `async tick()` method. Manages active graphs, completion queue, heartbeat checks. Runs as background `asyncio.create_task` on FastAPI startup. **Single-process assumption:** exactly one resolver loop per backend process; no distributed coordination. On startup, reconstructs in-memory state from `.oats/runtime/` (file scan) and SQLite registry.
- `dispatch.py`: `select_worker()` implementing affinity algorithm (provider match → sticky worker → tag match → lowest load). `build_dispatch_envelope()` constructing `ExecutionEnvelope` with worker binding. Auth adapter check: for `oauth_token` credentials, verify `token_expires_at`; for `local_cli_session`, skip expiry check (worker is responsible); for `api_key`, verify key is present.
- Integration: `app.py` starts the resolver loop on `startup` event. The loop runs `tick()` on a configurable interval (default 5 seconds).
- **State authority:** The resolver reads pending results from `.oats/runtime/<run_id>/results/` (authoritative for task outcomes) and updates the SQLite worker registry (authoritative for worker state). No state is dual-written to both stores as authoritative.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `uv run --group dev pytest tests/test_resolver_loop.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/application/resolver.py \
        python/helaicopter_api/application/dispatch.py \
        python/helaicopter_api/bootstrap/services.py \
        python/helaicopter_api/server/app.py \
        tests/test_resolver_loop.py
git commit -m "feat: permanent resolver loop with provider-aware dispatch and dead-worker reaping"
```

---

### Task 4: Pull-Dispatch Endpoint and Attack Plan Builder

**Why:** Workers need to pull tasks. The pull-dispatch endpoint is how Pi shells get work. The attack plan builder promotes orchestrate-run's ad-hoc prompt generation into a structured, testable module.

**Files:**
- New: `python/oats/attack_plan.py`
- Modify: `python/helaicopter_api/router/workers.py` (add next-task and report endpoints)
- Modify: `python/helaicopter_api/application/workers.py`
- Modify: `python/oats/envelope.py` (add AttackPlan, AcceptanceCriterion)
- New: `tests/oats/test_attack_plan.py`
- Modify: `tests/test_api_workers.py`

- [ ] **Step 1: Write failing tests for attack plan construction and pull dispatch**

```python
# test_attack_plan.py
def test_attack_plan_from_task_and_plan_steps() -> None:
    """Attack plan assembles objective, instructions, and context from task spec and plan."""
    task = TaskNode(task_id="auth", kind=TaskKind.IMPLEMENTATION, title="Auth Service Setup")
    plan_steps = [
        PlanStep(ref="1.1", text="Create auth middleware with JWT validation"),
        PlanStep(ref="1.2", text="Add rate limiting per-user"),
    ]
    context = [
        ContextSnippet(source="src/middleware/index.ts", content="export function ...",
                       relevance="Existing middleware pattern to follow"),
    ]

    plan = build_attack_plan(task, plan_steps=plan_steps, context_snippets=context)

    assert "Auth Service Setup" in plan.objective
    assert "JWT validation" in plan.instructions
    assert len(plan.context_snippets) == 1
    assert plan.plan_step_refs == ["1.1", "1.2"]

def test_attack_plan_includes_acceptance_criteria() -> None:
    """Attack plan includes structured acceptance criteria from task spec."""
    task = TaskNode(task_id="auth", kind=TaskKind.IMPLEMENTATION, title="Auth",
                    acceptance_criteria=["All tests pass", "No lint errors"])
    plan = build_attack_plan(task, plan_steps=[], context_snippets=[])

    assert len(plan.acceptance_criteria) == 2
    assert plan.acceptance_criteria[0].description == "All tests pass"

# test_api_workers.py (additions)
def test_pull_dispatch_returns_envelope_for_ready_task(client, idle_claude_worker, run_with_ready_task) -> None:
    response = client.get(f"/workers/{idle_claude_worker}/next-task")
    assert response.status_code == 200
    payload = response.json()
    assert payload["taskId"] is not None
    assert payload["attackPlan"]["objective"] is not None
    assert payload["sessionId"].startswith("sess_")

def test_pull_dispatch_returns_204_when_no_tasks(client, idle_claude_worker) -> None:
    response = client.get(f"/workers/{idle_claude_worker}/next-task")
    assert response.status_code == 204

def test_report_result_completes_task(client, busy_worker_with_task) -> None:
    worker_id, task_id = busy_worker_with_task
    response = client.post(f"/workers/{worker_id}/report", json={
        "taskId": task_id,
        "attemptId": "att_test",
        "status": "succeeded",
        "durationSeconds": 120.0,
        "branchName": "oats/task/auth",
        "commitSha": "abc123",
    })
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `uv run --group dev pytest tests/oats/test_attack_plan.py tests/test_api_workers.py -q`

- [ ] **Step 3: Implement attack plan builder and pull-dispatch/report endpoints**

Key implementation:
- `attack_plan.py`: `build_attack_plan()` assembles `AttackPlan` from `TaskNode`, plan step references, and context snippets. `AcceptanceCriterion` model. Markdown rendering for agent consumption.
- `envelope.py`: Add `AttackPlan`, `ContextSnippet`, `AcceptanceCriterion` models to the envelope module.
- `router/workers.py`: `GET /{worker_id}/next-task` — queries resolver for next dispatchable task matching worker capabilities. Returns `ExecutionEnvelope` with attack plan or 204. `POST /{worker_id}/report` — accepts `TaskResult`, writes to `.oats/runtime/<run_id>/results/`, signals resolver.
- `application/workers.py`: Coordinate between registry, resolver, and state persistence.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `uv run --group dev pytest tests/oats/test_attack_plan.py tests/test_api_workers.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/oats/attack_plan.py python/oats/envelope.py \
        python/helaicopter_api/router/workers.py \
        python/helaicopter_api/application/workers.py \
        tests/oats/test_attack_plan.py tests/test_api_workers.py
git commit -m "feat: attack plan builder and pull-dispatch endpoint for worker task acquisition"
```

---

### Task 5: Pi v1 Worker Shell Implementation

**Why:** Pi v1 is the canonical worker — a supervisor-style long-lived process that spawns a fresh CLI subprocess per task. Without a working Pi implementation, the permanent loop has no consumers. This task builds the Pi-side registration, task loop, heartbeat, per-task subprocess management, and re-dispatch logic. (Pi v2 — persistent agent sessions across tasks — is a future evolution; the worker registry and dispatch protocol are designed to support either model.)

**Files:**
- New: `python/oats/pi_worker.py`
- Modify: `python/oats/cli.py` (add `oats pi start` command)
- New: `tests/oats/test_pi_worker.py`

- [ ] **Step 1: Write failing tests for Pi worker behavior**

```python
# test_pi_worker.py
@pytest.mark.asyncio
async def test_pi_registers_with_control_plane() -> None:
    """Pi worker registers and receives a worker_id."""
    server = MockControlPlane()
    pi = PiWorker(provider="claude", models=["claude-sonnet-4-6"],
                  control_plane_url=server.url)
    await pi.register()

    assert pi.worker_id is not None
    assert pi.worker_id.startswith("wkr_")
    assert server.registered_workers == 1

@pytest.mark.asyncio
async def test_pi_pulls_and_executes_task() -> None:
    """Pi pulls a task, spawns agent subprocess, and reports result."""
    server = MockControlPlane(queued_task=stub_envelope())
    pi = PiWorker(provider="claude", models=["claude-sonnet-4-6"],
                  control_plane_url=server.url,
                  agent_runner=MockAgentRunner(exit_code=0))
    await pi.register()
    await pi.run_one_cycle()

    assert server.reported_results == 1
    assert server.last_result.status == "succeeded"

@pytest.mark.asyncio
async def test_pi_redispatches_on_premature_exit() -> None:
    """When agent exits without meeting acceptance criteria, Pi re-dispatches."""
    runner = MockAgentRunner(exit_code=0, criteria_met=False, max_redispatches=1)
    server = MockControlPlane(queued_task=stub_envelope_with_criteria())
    pi = PiWorker(provider="claude", models=["claude-sonnet-4-6"],
                  control_plane_url=server.url,
                  agent_runner=runner)
    await pi.register()
    await pi.run_one_cycle()

    assert runner.dispatch_count == 2  # original + 1 re-dispatch
    assert server.reported_results == 1

@pytest.mark.asyncio
async def test_pi_emits_heartbeats_during_execution() -> None:
    """Pi sends heartbeats while agent is running."""
    server = MockControlPlane(queued_task=stub_envelope())
    runner = MockAgentRunner(exit_code=0, duration_seconds=5)
    pi = PiWorker(provider="claude", models=["claude-sonnet-4-6"],
                  control_plane_url=server.url,
                  agent_runner=runner, heartbeat_interval=1)
    await pi.register()
    await pi.run_one_cycle()

    assert server.heartbeat_count >= 3  # at least 3 heartbeats in 5s with 1s interval

@pytest.mark.asyncio
async def test_pi_handles_no_tasks_gracefully() -> None:
    """Pi returns to idle when no tasks are available."""
    server = MockControlPlane(queued_task=None)
    pi = PiWorker(provider="claude", models=["claude-sonnet-4-6"],
                  control_plane_url=server.url)
    await pi.register()
    await pi.run_one_cycle()

    assert pi.status == "idle"
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `uv run --group dev pytest tests/oats/test_pi_worker.py -q`

- [ ] **Step 3: Implement Pi worker shell**

Key implementation:
- `pi_worker.py`: `PiWorker` class with:
  - `register()` — POST to `/workers/register`.
  - `run_loop()` — continuous: pull task → execute → report → repeat.
  - `run_one_cycle()` — single iteration (testable).
  - `_execute_task(envelope)` — spawn CLI subprocess (`claude -p` or `codex exec`), monitor PID, emit heartbeats, detect premature exit.
  - `_check_acceptance_criteria(envelope, worktree)` — verify criteria are met post-execution.
  - `_redispatch(envelope, worktree)` — commit progress, build focused prompt, re-spawn.
  - `_emit_heartbeat()` — POST to `/workers/{id}/heartbeat`.
  - `_report_result(result)` — POST to `/workers/{id}/report`.
- `cli.py`: Add `oats pi start --provider claude --model claude-sonnet-4-6 --control-plane http://localhost:8765` command that instantiates and runs `PiWorker`.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `uv run --group dev pytest tests/oats/test_pi_worker.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/oats/pi_worker.py python/oats/cli.py tests/oats/test_pi_worker.py
git commit -m "feat: Pi worker shell with registration, pull-dispatch, heartbeat, and re-dispatch"
```

---

### Task 6: OAuth Flow and Credential Lifecycle Automation

**Why:** API keys in environment variables don't scale. OAuth (the managed adapter tier, with OpenClaw as reference direction) enables token refresh, expiry-aware dispatch, and cost association. This task adds the OAuth callback handler and automatic token refresh to the auth store. The `local_cli_session` adapter (delegated to the worker) requires no lifecycle automation — it is already functional from Task 2.

**Files:**
- Modify: `python/helaicopter_api/router/auth.py` (OAuth initiate/callback)
- Modify: `python/helaicopter_api/application/auth.py` (token refresh logic)
- Modify: `python/helaicopter_api/application/resolver.py` (check auth before dispatch)
- New: `tests/test_oauth_flow.py`

- [ ] **Step 1: Write failing tests for OAuth flow and token refresh**

```python
# test_oauth_flow.py
def test_initiate_oauth_returns_redirect_url(client) -> None:
    response = client.post("/auth/credentials/oauth/initiate", json={
        "provider": "claude",
    })
    assert response.status_code == 200
    assert "redirectUrl" in response.json()

def test_oauth_callback_stores_credential(client, pending_oauth_state) -> None:
    response = client.get(
        f"/auth/credentials/oauth/callback?code=test_code&state={pending_oauth_state}"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["credentialId"].startswith("cred_")
    assert payload["status"] == "active"

def test_refresh_expired_token(client, expired_oauth_credential) -> None:
    response = client.post(f"/auth/credentials/{expired_oauth_credential}/refresh")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "active"
    # tokenExpiresAt should be in the future
    assert payload["tokenExpiresAt"] is not None

@pytest.mark.asyncio
async def test_resolver_auto_refreshes_expiring_token() -> None:
    """Resolver detects token expiring within 5 minutes and triggers refresh."""
    auth_store = InMemoryAuthStore()
    cred = auth_store.create(provider="claude", credential_type="oauth_token",
                              token_expires_at=datetime.now() + timedelta(minutes=3))
    registry = InMemoryWorkerRegistry()
    worker = registry.register(provider="claude", auth_credential_id=cred.credential_id)

    resolver = ResolverLoop(registry=registry, auth_store=auth_store,
                            graphs={}, token_refresh_threshold=timedelta(minutes=5))

    await resolver.tick()

    # Token should have been refreshed
    updated = auth_store.get(cred.credential_id)
    assert updated.last_refreshed_at is not None
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `uv run --group dev pytest tests/test_oauth_flow.py -q`

- [ ] **Step 3: Implement OAuth flow and token refresh automation**

Key implementation:
- `router/auth.py`: `POST /auth/credentials/oauth/initiate` generates OAuth URL with PKCE. `GET /auth/credentials/oauth/callback` exchanges code for tokens, stores encrypted credential.
- `application/auth.py`: `refresh_credential()` uses refresh_token to get new access_token. Provider-specific OAuth client (Anthropic, OpenAI).
- `resolver.py`: On each tick, check `auth_credentials` for tokens expiring within `token_refresh_threshold`. Auto-refresh. On refresh failure, set worker status to `auth_expired`.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `uv run --group dev pytest tests/test_oauth_flow.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/router/auth.py \
        python/helaicopter_api/application/auth.py \
        python/helaicopter_api/application/resolver.py \
        tests/test_oauth_flow.py
git commit -m "feat: OAuth credential flow with auto-refresh and expiry-aware dispatch"
```

---

### Task 7: Dispatch Queue Monitor and History API

**Why:** The operator needs visibility into what the resolver is doing: what's queued, what's deferred, what was dispatched where. This is the "dispatch observability" surface that makes the permanent loop debuggable.

**Files:**
- New: `python/helaicopter_api/schema/dispatch.py`
- New: `python/helaicopter_api/application/dispatch_monitor.py`
- New: `python/helaicopter_api/router/dispatch.py`
- Modify: `python/helaicopter_api/application/resolver.py` (emit dispatch events)
- Modify: `python/helaicopter_api/server/app.py`
- New: `tests/test_api_dispatch.py`

- [ ] **Step 1: Write failing tests for dispatch queue and history endpoints**

```python
# test_api_dispatch.py
def test_queue_snapshot_shows_ready_and_deferred(client, run_with_mixed_readiness) -> None:
    response = client.get("/dispatch/queue")
    payload = response.json()

    assert "ready" in payload
    assert "deferred" in payload
    assert len(payload["deferred"]) > 0
    assert payload["deferred"][0]["reason"] == "no_capable_worker"

def test_dispatch_history_shows_recent_dispatches(client, run_with_dispatched_tasks) -> None:
    response = client.get("/dispatch/history?limit=10")
    payload = response.json()

    assert len(payload["entries"]) > 0
    entry = payload["entries"][0]
    assert "taskId" in entry
    assert "workerId" in entry
    assert "dispatchedAt" in entry
    assert "provider" in entry
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `uv run --group dev pytest tests/test_api_dispatch.py -q`

- [ ] **Step 3: Implement dispatch monitor and history**

- `dispatch_monitor.py`: Reads resolver's internal queue state and dispatch log.
- `resolver.py`: Emit `DispatchEvent` on every dispatch (task_id, worker_id, timestamp, provider, model). Store in-memory ring buffer (last 1000 events) + append to `dispatch_history.jsonl`.
- `schema/dispatch.py`: `QueueSnapshotResponse`, `DispatchHistoryResponse`.
- `router/dispatch.py`: `GET /dispatch/queue`, `GET /dispatch/history`.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `uv run --group dev pytest tests/test_api_dispatch.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/schema/dispatch.py \
        python/helaicopter_api/application/dispatch_monitor.py \
        python/helaicopter_api/router/dispatch.py \
        python/helaicopter_api/application/resolver.py \
        python/helaicopter_api/server/app.py \
        tests/test_api_dispatch.py
git commit -m "feat: dispatch queue monitor and history API for resolver observability"
```

---

### Task 8: Operator UI — Worker Dashboard and Auth Management

**Why:** The Helaicopter frontend must surface the new control-plane primitives: worker status, auth credentials, dispatch queue. Without this, the permanent loop is a black box.

**Files:**
- Modify: `src/lib/types.ts` (worker, auth, dispatch types)
- New: `src/lib/client/workers.ts` (worker API client)
- New: `src/lib/client/auth.ts` (auth API client)
- New: `src/components/workers/worker-dashboard.tsx`
- New: `src/components/workers/worker-card.tsx`
- New: `src/components/auth/credential-list.tsx`
- New: `src/components/auth/add-credential-dialog.tsx`
- New: `src/components/dispatch/queue-monitor.tsx`
- Modify: `src/components/orchestration/overnight-oats-panel.tsx` (link to worker/dispatch views)
- New: `src/components/workers/worker-dashboard.test.ts`

- [ ] **Step 1: Write failing tests for worker dashboard view model**

```ts
// worker-dashboard.test.ts
test("buildWorkerDashboard groups workers by provider", () => {
  const workers = [
    { workerId: "wkr_1", provider: "claude", status: "idle" },
    { workerId: "wkr_2", provider: "codex", status: "busy" },
    { workerId: "wkr_3", provider: "claude", status: "busy" },
  ];
  const dashboard = buildWorkerDashboard(workers);

  assert.equal(dashboard.byProvider.claude.length, 2);
  assert.equal(dashboard.byProvider.codex.length, 1);
  assert.equal(dashboard.idleCount, 1);
  assert.equal(dashboard.busyCount, 2);
});

test("buildWorkerDashboard flags auth-expired workers", () => {
  const workers = [
    { workerId: "wkr_1", provider: "claude", status: "auth_expired" },
  ];
  const dashboard = buildWorkerDashboard(workers);

  assert.equal(dashboard.authExpiredCount, 1);
  assert.ok(dashboard.hasAuthIssues);
});
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `node --import tsx --test src/components/workers/worker-dashboard.test.ts`

- [ ] **Step 3: Implement frontend components**

Key implementation:
- `types.ts`: `Worker`, `AuthCredential`, `DispatchQueueSnapshot`, `DispatchHistoryEntry` types.
- `workers.ts`: SWR hooks for `useWorkers()`, `useDrainWorker()`, `useRemoveWorker()`.
- `auth.ts`: SWR hooks for `useCredentials()`, `useAddCredential()`, `useRevokeCredential()`.
- `worker-dashboard.tsx`: Worker list grouped by provider with status badges. Idle/busy/dead/auth_expired counts. Drain and remove actions.
- `worker-card.tsx`: Individual worker detail — current task, heartbeat freshness, resource usage.
- `credential-list.tsx`: Credential table with provider, type, status, expiry, cumulative cost. Revoke action.
- `add-credential-dialog.tsx`: Form for API key entry. OAuth initiate button (opens redirect).
- `queue-monitor.tsx`: Ready queue depth, deferred tasks with reasons, recent dispatch history.
- `overnight-oats-panel.tsx`: Navigation links to worker dashboard, auth management, queue monitor.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `node --import tsx --test src/components/workers/worker-dashboard.test.ts`

- [ ] **Step 5: Run lint**

Run: `npm run lint`

- [ ] **Step 6: Commit**

```bash
git add src/lib/types.ts src/lib/client/workers.ts src/lib/client/auth.ts \
        src/components/workers/ src/components/auth/ src/components/dispatch/ \
        src/components/orchestration/overnight-oats-panel.tsx
git commit -m "feat: operator UI with worker dashboard, auth management, and queue monitor"
```

---

### Task 9: Run Control Actions (Pause, Cancel, Force-Retry, Re-Route, Insert Task)

**Why:** An operator console without intervention controls is just a dashboard. The operator needs to pause runs, cancel tasks, force retries, re-route to different providers, and insert tasks — all recorded as graph mutations with provenance.

**Files:**
- Modify: `python/helaicopter_api/router/orchestration.py` (new action endpoints)
- Modify: `python/helaicopter_api/application/orchestration.py` (action logic)
- Modify: `python/oats/graph.py` (operator mutation support)
- Modify: `tests/test_api_orchestration.py`
- Modify: `src/components/orchestration/overnight-oats-panel.tsx` (action buttons)

- [ ] **Step 1: Write failing tests for run control actions**

```python
# test_api_orchestration.py (additions)
def test_pause_run_prevents_new_dispatches(client, active_run) -> None:
    response = client.post(f"/orchestration/runs/{active_run}/pause")
    assert response.status_code == 200
    # Verify status
    response = client.get(f"/orchestration/runs/{active_run}")
    assert response.json()["status"] == "paused"

def test_cancel_task_propagates_blocked(client, run_with_chain) -> None:
    run_id, task_ids = run_with_chain  # a -> b -> c
    response = client.post(f"/orchestration/runs/{run_id}/tasks/{task_ids[0]}/cancel")
    assert response.status_code == 200
    # Check cascading block
    response = client.get(f"/orchestration/runs/{run_id}")
    nodes = {n["taskId"]: n for n in response.json()["nodes"]}
    assert nodes[task_ids[0]]["status"] == "cancelled"
    assert nodes[task_ids[1]]["status"] == "blocked_by_failure"

def test_force_retry_resets_failed_task(client, run_with_failed_task) -> None:
    run_id, task_id = run_with_failed_task
    response = client.post(f"/orchestration/runs/{run_id}/tasks/{task_id}/force-retry")
    assert response.status_code == 200
    response = client.get(f"/orchestration/runs/{run_id}")
    node = [n for n in response.json()["nodes"] if n["taskId"] == task_id][0]
    assert node["status"] == "pending"

def test_reroute_task_changes_provider(client, run_with_pending_task) -> None:
    run_id, task_id = run_with_pending_task
    response = client.post(f"/orchestration/runs/{run_id}/tasks/{task_id}/reroute", json={
        "provider": "codex",
        "model": "o3-pro",
    })
    assert response.status_code == 200

def test_insert_task_adds_to_graph(client, active_run) -> None:
    response = client.post(f"/orchestration/runs/{active_run}/tasks", json={
        "title": "Operator-added task",
        "kind": "implementation",
        "dependencies": [{"taskId": "existing_task", "predicate": "code_ready"}],
        "agent": "claude",
        "model": "claude-sonnet-4-6",
    })
    assert response.status_code == 201
    payload = response.json()
    assert payload["taskId"].startswith("task_")

def test_all_operator_mutations_logged(client, active_run) -> None:
    client.post(f"/orchestration/runs/{active_run}/pause")
    response = client.get(f"/orchestration/runs/{active_run}")
    mutations = response.json().get("graphMutations", [])
    operator_mutations = [m for m in mutations if m.get("source") == "operator"]
    assert len(operator_mutations) >= 1
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `uv run --group dev pytest tests/test_api_orchestration.py -q -k "pause or cancel or retry or reroute or insert or operator"`

- [ ] **Step 3: Implement run control actions**

Key implementation:
- `graph.py`: Add `cancel_task()`, `force_retry_task()`, `reroute_task()`. All record `GraphMutation` with `source: "operator"`.
- `application/orchestration.py`: Action handlers that validate state transitions and delegate to graph methods. Pause sets run status, signals resolver to skip this run.
- `router/orchestration.py`: New POST endpoints per the design spec.
- `overnight-oats-panel.tsx`: Wire action buttons to corresponding API calls.

- [ ] **Step 4: Run tests, confirm they pass**

Run: `uv run --group dev pytest tests/test_api_orchestration.py -q`

- [ ] **Step 5: Commit**

```bash
git add python/helaicopter_api/router/orchestration.py \
        python/helaicopter_api/application/orchestration.py \
        python/oats/graph.py \
        tests/test_api_orchestration.py \
        src/components/orchestration/overnight-oats-panel.tsx
git commit -m "feat: operator run control actions — pause, cancel, force-retry, re-route, insert task"
```

---

### Task 10: Integration Testing — Multi-Worker, Multi-Run, Auth Lifecycle, Mid-Run Discovery

**Why:** The permanent loop architecture spans many components: resolver, registry, auth, dispatch, Pi, graph. This task verifies they work together at realistic scale — multiple workers, multiple concurrent runs, auth expiry mid-run, worker death and recovery, and discovered-task insertion mid-run (including validation, cycle rejection, and same-tick dispatch).

**Files:**
- New: `tests/test_permanent_loop_integration.py`
- All modified files from Tasks 1–9

- [ ] **Step 1: Write integration tests for multi-worker scenarios**

```python
# test_permanent_loop_integration.py
@pytest.mark.asyncio
async def test_two_workers_two_runs_concurrent_dispatch() -> None:
    """Two workers (claude + codex) serve two concurrent runs with mixed provider tasks."""
    registry = InMemoryWorkerRegistry()
    claude_worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])
    codex_worker = registry.register(provider="codex", models=["o3-pro"])

    run_a = build_mixed_provider_graph("run_a", claude_tasks=2, codex_tasks=1)
    run_b = build_mixed_provider_graph("run_b", claude_tasks=1, codex_tasks=2)

    resolver = ResolverLoop(registry=registry, graphs={"run_a": run_a, "run_b": run_b})
    await run_resolver_to_completion(resolver, agent_stub=instant_success())

    assert all_tasks_succeeded(run_a)
    assert all_tasks_succeeded(run_b)

@pytest.mark.asyncio
async def test_auth_expiry_mid_run_defers_then_resumes() -> None:
    """Token expires mid-run. Tasks are deferred. Token refresh unblocks dispatch."""
    auth_store = InMemoryAuthStore()
    cred = auth_store.create(provider="claude", token_expires_at=datetime.now() + timedelta(seconds=2))

    registry = InMemoryWorkerRegistry()
    worker = registry.register(provider="claude", auth_credential_id=cred.credential_id)

    graph = build_linear_graph(["a", "b", "c"])
    resolver = ResolverLoop(registry=registry, auth_store=auth_store,
                            graphs={"run_1": graph})

    # Execute a — should succeed
    await resolver.tick()
    simulate_task_completion(resolver, "a")

    # Wait for token to expire
    await asyncio.sleep(3)
    await resolver.tick()

    # b should be deferred (auth expired)
    assert graph.get_node("b").status == "pending"

    # Simulate token refresh
    auth_store.refresh(cred.credential_id)
    await resolver.tick()

    # Now b should be dispatched
    assert graph.get_node("b").status == "running"

@pytest.mark.asyncio
async def test_worker_death_triggers_task_retry_on_different_worker() -> None:
    """Worker dies mid-task. Task is retried on a different worker."""
    registry = InMemoryWorkerRegistry()
    worker_a = registry.register(provider="claude", models=["claude-sonnet-4-6"])
    worker_b = registry.register(provider="claude", models=["claude-sonnet-4-6"])

    graph = build_single_task_graph("auth", agent="claude", model="claude-sonnet-4-6")
    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph},
                            heartbeat_timeout=timedelta(seconds=2))

    await resolver.tick()
    assert graph.get_node("auth").status == "running"
    dispatched_to = graph.get_node("auth").current_worker_id

    # Simulate worker death (no heartbeat)
    registry.get(dispatched_to).last_heartbeat_at = datetime.now() - timedelta(seconds=10)

    await resolver.tick()

    # Task should be re-queued and dispatched to the other worker
    assert registry.get(dispatched_to).status == "dead"
    assert graph.get_node("auth").status == "running"
    assert graph.get_node("auth").current_worker_id != dispatched_to

@pytest.mark.asyncio
async def test_discovered_task_with_satisfied_deps_dispatches_same_tick() -> None:
    """A discovered task whose dependencies are already completed dispatches immediately."""
    registry = InMemoryWorkerRegistry()
    worker = registry.register(provider="claude", models=["claude-sonnet-4-6"])

    graph = build_single_task_graph("a", agent="claude", model="claude-sonnet-4-6")
    graph.get_node("a").status = "succeeded"
    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph})

    # Simulate discovery: task b depends on completed task a
    discovery = DiscoveredTaskSpec(task_id="b", kind="implementation",
                                   dependencies=[{"taskId": "a", "predicate": "code_ready"}],
                                   agent="claude", model="claude-sonnet-4-6")
    resolver.submit_discovery("run_1", source_task_id="a", discovered=[discovery])

    await resolver.tick()

    assert graph.get_node("b").status == "running"  # dispatched in same tick

@pytest.mark.asyncio
async def test_discovered_task_creating_cycle_is_rejected() -> None:
    """A discovered task that would create a cycle is rejected."""
    registry = InMemoryWorkerRegistry()
    graph = build_linear_graph(["a", "b"])  # a -> b
    graph.get_node("a").status = "running"
    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph})

    # Discovered task c: b -> c -> a would create a cycle
    discovery = DiscoveredTaskSpec(task_id="c", kind="implementation",
                                   dependencies=[{"taskId": "b", "predicate": "code_ready"}],
                                   dependents=[{"taskId": "a", "predicate": "code_ready"}],
                                   agent="claude", model="claude-sonnet-4-6")
    resolver.submit_discovery("run_1", source_task_id="b", discovered=[discovery])

    await resolver.tick()

    assert graph.get_node_optional("c") is None  # rejected, not inserted

@pytest.mark.asyncio
async def test_discovered_task_with_nonexistent_dep_is_rejected() -> None:
    """A discovered task referencing a nonexistent dependency is rejected."""
    registry = InMemoryWorkerRegistry()
    graph = build_single_task_graph("a", agent="claude", model="claude-sonnet-4-6")
    resolver = ResolverLoop(registry=registry, graphs={"run_1": graph})

    discovery = DiscoveredTaskSpec(task_id="b", kind="implementation",
                                   dependencies=[{"taskId": "nonexistent", "predicate": "code_ready"}],
                                   agent="claude", model="claude-sonnet-4-6")
    resolver.submit_discovery("run_1", source_task_id="a", discovered=[discovery])

    await resolver.tick()

    assert graph.get_node_optional("b") is None  # rejected
```

- [ ] **Step 2: Run tests, confirm they fail**

Run: `uv run --group dev pytest tests/test_permanent_loop_integration.py -q`

- [ ] **Step 3: Fix integration issues**

Address real bugs surfaced by integration tests. Typical issues: race conditions in dispatch, auth check timing, worker selection after death, multi-graph ready-queue evaluation ordering.

- [ ] **Step 4: Run all tests end-to-end**

```bash
uv run --group dev pytest tests/ -q --ignore=tests/oats/test_large_graph_scenarios.py
uv run --group dev pytest tests/oats/test_large_graph_scenarios.py -q
node --import tsx --test src/components/workers/worker-dashboard.test.ts
node --import tsx --test src/lib/client/normalize.test.ts
npm run lint
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_permanent_loop_integration.py
git add -u
git commit -m "feat: multi-worker multi-run integration tests with auth lifecycle verification"
```
