# Permanent Worker Loop Architecture Design

**Date:** 2026-03-26
**Status:** Draft
**Builds on:** `specs/2026-03-25-oats-graph-native-runtime-v2-design.md`
**Context:** `orchestrate-run` skill learnings, OpenClaw multi-provider direction

## Executive Summary

The v2 graph-native runtime (2026-03-25) redesigned OATS around a task DAG with typed edges and a ready-queue scheduler. That design assumes a single `oats run` invocation that spawns agent subprocesses, polls for completion, and exits when the graph is terminal. This works for 10-30 task runs initiated by a human. It does not work for what comes next: a continuously running control plane where long-lived worker shells (Pi instances) pick up tasks from a shared queue, where workers authenticate via OAuth/subscription credentials to different providers (Claude, Codex), where the scheduler routes tasks based on provider affinity and auth capability, and where the Helaicopter UI is a real-time operator console — not a read-only dashboard.

This design promotes the OATS runtime from a CLI-invoked batch executor to a **permanent resolver loop** backed by a **worker registry** with **provider-aware dispatch**. The `orchestrate-run` skill's hard-won patterns — CLI-process dispatch, cron-based monitoring, re-dispatch on premature exit, session self-registration — are promoted from ad-hoc skill behavior into first-class runtime primitives. Pi becomes the canonical long-lived worker shell: a persistent agent process that registers with the control plane, advertises its provider capabilities, and pulls tasks from the ready queue.

## Goals

- **Permanent resolver loop:** The OATS scheduler runs continuously (or is awakened by events), not invoked once per `oats run`. It evaluates edges, fills the ready queue, dispatches to available workers, and processes completions — indefinitely.
- **Worker registry and lifecycle:** Workers (Pi shells, Claude Code sessions, Codex sessions) register with the control plane, advertise capabilities, and have explicit lifecycle states (idle, busy, draining, dead).
- **Provider-aware dispatch affinity:** The scheduler routes tasks to workers based on which provider/model the task requires and which workers have valid auth for that provider.
- **OAuth/subscription auth model:** Workers authenticate to upstream providers (Anthropic API for Claude, OpenAI API for Codex) via OAuth tokens or subscription-backed API keys managed by Helaicopter. Auth credentials are associated with worker registrations, not baked into config files.
- **orchestrate-run learnings as first-class runtime:** Session self-registration, cron-based liveness monitoring, re-dispatch on premature exit, attack-plan generation, and acceptance-criteria validation move from skill-level scripting into the runtime.
- **Helaicopter as operator console:** The UI becomes a control surface for the permanent loop — worker status, queue depth, dispatch history, auth health, and manual intervention (pause, cancel, re-route, force-retry).

## Non-Goals

- Replacing the file-based `.oats/runtime/` store with a database for the graph. (The graph stays file-based; the worker registry and auth store use Helaicopter's existing SQLite.)
- Multi-tenant worker pools. This is a single-operator system (one developer's machines).
- Running Pi in the cloud. Pi is a local process on the developer's machine.
- Auto-scaling worker count. The operator decides how many Pi shells to run.
- Replacing Claude Code or Codex CLIs. Workers invoke them as subprocesses, same as today.
- Pi v2 continuous-session runtime (a future evolution where Pi maintains persistent agent context across tasks rather than spawning fresh subprocesses). This plan is scoped to Pi v1.

## State Ownership and Authority

The runtime has two persistence layers with distinct ownership:

| Domain | Authoritative Store | Rationale |
|---|---|---|
| **Task graph** (nodes, edges, statuses, attempts) | `.oats/runtime/<run_id>/` (file-based) | Graph state is per-run, append-only, and designed for crash recovery via atomic file writes. Unchanged from v2. |
| **Task results and discovery files** | `.oats/runtime/<run_id>/results/` and `.oats/runtime/<run_id>/discovered/` | Output artifacts co-located with the graph they belong to. Workers write here directly. |
| **Graph mutations log** | `.oats/runtime/<run_id>/graph_mutations.jsonl` | Append-only audit log of all mutations (discovery, operator, edge evaluation). |
| **Worker registry** (registrations, lifecycle, heartbeats) | SQLite `worker_registry` table | Workers span multiple runs; need efficient queries by provider/status. |
| **Auth credentials** (tokens, keys, cost tracking) | SQLite `auth_credentials` table | Shared across workers and runs; need encryption and transactional updates. |
| **Dispatch history** | In-memory ring buffer + `dispatch_history.jsonl` | Observability only; not authoritative. Ring buffer is ephemeral; JSONL is durable but append-only. |
| **Resolver loop ephemeral state** (ready queue, active graph index) | In-memory only | Reconstructed on startup from `.oats/runtime/` file scan + SQLite registry. |

**Key invariant:** No piece of state has two authoritative sources. The resolver loop holds in-memory indices for performance but always rebuilds them from the authoritative stores on startup. When state must cross the boundary (e.g., a worker completion updates both the SQLite registry and the file-based graph), the file-based graph write is the commit point — the registry update is a best-effort follow-up that the next reconciliation pass will fix if it fails.

## Deployment Model

The resolver loop runs as a **single background asyncio task** inside one Helaicopter backend process. There is no multi-process leader election or distributed coordination. This matches the single-operator, single-machine deployment model.

If multiple backend processes are started (e.g., behind a dev proxy), only one should run the resolver loop. The current assumption is a single backend process; if this changes, a simple file-lock or SQLite advisory lock on `resolver_loop_active` is sufficient — no distributed consensus is needed.

## Core Concepts

### The Permanent Resolver Loop

The v2 scheduler is a `while not graph.is_terminal()` loop inside `oats run`. The permanent resolver loop inverts this: the loop runs independently of any single run, and runs are submitted to it.

```
resolver_loop:
    while True:
        # 1. Ingest events
        events = collect_events(worker_completions, worker_heartbeats,
                                graph_mutations, external_signals)

        # 2. Process completions and state transitions
        for event in events:
            match event:
                case WorkerCompletion(task_id, result):
                    graph.record_completion(task_id, result)
                    graph.evaluate_outbound_edges(task_id)
                    process_discoveries(task_id)
                case WorkerHeartbeat(worker_id, status):
                    registry.update_heartbeat(worker_id, status)
                case WorkerTimeout(worker_id, task_id):
                    handle_timeout(worker_id, task_id)
                case RunSubmitted(run_id, graph):
                    active_graphs[run_id] = graph
                    seed_ready_queue(graph)

        # 3. Reap dead workers
        for worker in registry.stale_workers(threshold=heartbeat_timeout):
            handle_worker_death(worker)

        # 4. Dispatch ready tasks to available workers
        for task in ready_queue.drain(limit=available_worker_slots()):
            worker = select_worker(task, registry)
            if worker:
                dispatch(task, worker)
            else:
                ready_queue.defer(task, reason="no_capable_worker")

        # 5. Wait for next event or timeout
        wait(timeout=poll_interval)
```

**Key differences from v2:**
- The loop outlives any single run. Multiple runs can be active simultaneously.
- Workers are external entities that register and deregister, not subprocesses spawned per-task.
- Dispatch is to a *worker*, not to a *subprocess*. The worker decides how to execute (spawn Claude Code, invoke Codex CLI, etc.).
- The loop is event-driven with a fallback poll interval, not purely polling.

**Lifecycle:**
- The resolver loop starts when the Helaicopter backend starts (or when the first run is submitted).
- It runs as a background asyncio task in the FastAPI process.
- It persists state atomically to `.oats/runtime/` on every state transition (same as v2).
- It can be paused/resumed via the operator UI.

### Worker Registry and Lifecycle

A **worker** is a long-lived process that can execute tasks. The canonical worker is a **Pi shell** — a persistent Claude Code or Codex session that stays alive between tasks. But the registry is agent-agnostic: any process that speaks the registration protocol is a worker.

#### Worker Registration

```python
class WorkerRegistration(BaseModel):
    worker_id: str                          # wkr_<ulid>
    worker_type: WorkerType                 # pi_shell | claude_session | codex_session | custom
    provider: ProviderName                  # claude | codex
    capabilities: WorkerCapabilities
    auth_credential_id: str | None          # reference to AuthCredential in auth store
    host: str                               # hostname or "local"
    pid: int | None                         # OS process ID if local
    worktree_root: str | None               # base path for worktree allocation
    registered_at: datetime
    last_heartbeat_at: datetime
    status: WorkerStatus                    # idle | busy | draining | dead | auth_expired

class WorkerCapabilities(BaseModel):
    provider: ProviderName
    models: list[str]                       # models this worker can serve
    max_concurrent_tasks: int               # usually 1 for Pi shells
    supports_discovery: bool                # can this worker emit discovery files
    supports_resume: bool                   # can tasks be resumed on this worker
    tags: list[str]                         # arbitrary affinity tags (e.g., "gpu", "high-memory")
```

#### Worker Lifecycle States

```
                    register()
    ┌──────────┐ ──────────────> ┌──────────┐
    │ unknown  │                 │  idle    │ <─── task_completed()
    └──────────┘                 └──────────┘
                                      │
                                      │ dispatch(task)
                                      ▼
                                 ┌──────────┐
                                 │  busy    │ ──── heartbeat() ───> busy (updated)
                                 └──────────┘
                                      │
                            ┌─────────┼──────────┐
                            │         │          │
                      task_completed  │    heartbeat_timeout
                            │    task_failed     │
                            │         │          │
                            ▼         ▼          ▼
                       ┌────────┐ ┌────────┐ ┌──────┐
                       │  idle  │ │  idle  │ │ dead │
                       └────────┘ └────────┘ └──────┘
                                                 │
                                           re-register()
                                                 │
                                                 ▼
                                            ┌────────┐
                                            │  idle  │
                                            └────────┘

    drain() → draining (finishes current task, then idle, then removed)
    auth_expired → auth_expired (cannot accept new tasks until credential refreshed)
```

#### Worker Registry Storage

The worker registry lives in Helaicopter's app SQLite database (not in `.oats/runtime/`). This is because:
- Workers span multiple runs.
- The registry needs efficient queries (find idle workers by provider, check auth status).
- The Helaicopter backend already manages SQLite via alembic.

```sql
CREATE TABLE worker_registry (
    worker_id TEXT PRIMARY KEY,
    worker_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    auth_credential_id TEXT REFERENCES auth_credentials(credential_id),
    host TEXT NOT NULL DEFAULT 'local',
    pid INTEGER,
    worktree_root TEXT,
    registered_at TEXT NOT NULL,
    last_heartbeat_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    current_task_id TEXT,
    current_run_id TEXT,
    metadata_json TEXT
);
```

### Task Execution Envelope Protocol

The v2 `ExecutionEnvelope` is extended for worker-based dispatch:

```python
class ExecutionEnvelope(BaseModel):
    # Identity (unchanged from v2)
    session_id: str
    attempt_id: str
    task_id: str
    run_id: str

    # Agent config (extended)
    agent: AgentType                         # claude | codex
    model: str
    reasoning_effort: str | None

    # Worker binding (NEW)
    worker_id: str                           # assigned worker
    dispatch_mode: DispatchMode              # push | pull

    # Execution context (extended)
    worktree_path: str
    parent_branch: str
    timeout_seconds: int
    max_output_tokens: int | None

    # Retry policy (unchanged)
    retry_policy: RetryPolicy

    # Task payload (NEW — replaces ad-hoc context dict)
    attack_plan: AttackPlan                  # structured task instructions
    acceptance_criteria: list[AcceptanceCriterion]

    # Discovery and output (unchanged)
    discovery_enabled: bool
    output_contract: OutputContract
```

#### Attack Plan (from orchestrate-run)

The `orchestrate-run` skill generates "attack plans" — structured markdown prompts assembled from plan steps, context snippets, and acceptance criteria. This is promoted to a first-class runtime concept:

```python
class AttackPlan(BaseModel):
    objective: str                           # one-line task objective
    instructions: str                        # full markdown prompt body
    context_snippets: list[ContextSnippet]   # relevant code/doc excerpts
    plan_step_refs: list[str]                # references to plan steps

class ContextSnippet(BaseModel):
    source: str                              # file path or doc reference
    content: str                             # extracted text
    relevance: str                           # why this snippet matters
```

#### Dispatch Modes

- **Push dispatch:** The resolver loop assigns a task to a specific worker and sends the envelope via the worker's command channel (file drop, HTTP POST, or stdin pipe — depending on worker type).
- **Pull dispatch:** The worker polls the control plane for ready tasks matching its capabilities. The resolver loop marks the task as "available" and the worker claims it.

Pi shells use **pull dispatch** — they are autonomous agents that check for work. Subprocess-spawned sessions (v2 compat) use **push dispatch** — the resolver spawns the process directly.

### Task Result / Discovery Protocol

#### Result Protocol

When a worker completes a task, it produces a structured result:

```python
class TaskResult(BaseModel):
    task_id: str
    attempt_id: str
    worker_id: str
    status: ResultStatus                     # succeeded | failed | timed_out | needs_retry

    # Output artifacts
    branch_name: str | None                  # git branch with committed work
    commit_sha: str | None                   # HEAD of the branch
    pr_url: str | None                       # if PR was created
    artifacts: list[TaskArtifact]            # named output files

    # Acceptance criteria results
    criteria_results: list[CriterionResult]  # pass/fail per acceptance criterion

    # Discovery (if any)
    discovered_tasks: list[DiscoveredTaskSpec] | None

    # Diagnostics
    exit_code: int | None
    error_summary: str | None
    duration_seconds: float
    token_usage: TokenUsage | None           # input/output tokens consumed
    cost_estimate: float | None              # estimated API cost
```

Results are written to `.oats/runtime/<run_id>/results/<task_id>/<attempt_id>.json`. The resolver loop reads them on the next cycle.

#### Discovery Protocol (extended from v2)

The v2 discovery protocol (`.oats/discovered/<task_id>.json`) is retained but extended:
- Workers can include discovered tasks inline in the `TaskResult` (no separate file needed).
- The resolver loop validates and inserts discovered tasks the same way.
- Discovery files are still supported as a fallback for workers that can't produce structured results.

#### Mid-Run Discovery Insertion Verification

Discovered tasks inserted mid-run must be verified before they enter the ready queue:

1. **Schema validation:** The `DiscoveredTaskSpec` must have a valid `task_id` (unique within the run), a `kind`, and at least one inbound edge from an existing node.
2. **Edge validation:** All referenced dependency `task_id`s must exist in the current graph. Dangling edges are rejected and logged.
3. **Cycle detection:** The resolver runs a topological-sort check after tentatively inserting the discovered node + edges. If a cycle is introduced, the insertion is rejected and the discovery is recorded as `rejected` in `graph_mutations.jsonl` with the reason.
4. **Dispatch eligibility:** After insertion, the resolver evaluates the new node's inbound edges immediately (same tick). If all dependencies are already satisfied, the task enters the ready queue in the same resolver cycle — no extra tick delay.
5. **Provenance:** All discovery insertions are recorded in `graph_mutations.jsonl` with `source: "discovery"` and the originating `task_id` + `worker_id`.

Integration tests must cover: (a) discovered task with satisfied deps dispatches in the same tick, (b) discovered task with unsatisfied deps waits correctly, (c) discovered task creating a cycle is rejected, (d) discovered task with nonexistent dependency edge is rejected.

### Graph Mutation Model

The v2 graph mutation model (`GraphMutation` with `insert_tasks`, `add_edges`, `remove_edges`) is retained. The permanent loop adds:

#### Run Submission as Graph Mutation

Submitting a new run is a graph mutation: the resolver loop receives a `TaskGraph` and registers it as an active run. Multiple runs can be active simultaneously, each with its own graph.

#### Cross-Run Dependencies (future)

A task in run B can depend on a task in run A via a qualified edge: `run_a:task_x → run_b:task_y`. This is not in v1 of the permanent loop but the model supports it.

#### Operator-Initiated Mutations

The operator (via Helaicopter UI) can:
- **Cancel a task:** Mark it failed, propagate `blocked_by_failure`.
- **Force-retry a task:** Reset status to pending, create new attempt.
- **Re-route a task:** Change the assigned worker or provider.
- **Insert a task:** Add a new task node with edges (same as discovery, but human-initiated).
- **Pause a run:** Prevent new dispatches but let running tasks complete.

All operator mutations are recorded in `graph_mutations.jsonl` with `source: "operator"` provenance.

### Pi Integration Shape

Pi is the canonical long-lived worker. This design covers **Pi v1: supervisor-style worker shell**. Pi v1 is a long-lived process that registers with the control plane, pulls tasks from the ready queue, and spawns a fresh per-task provider subprocess (Claude Code CLI or Codex CLI) for each task. Between tasks, the Pi shell is idle — it holds no agent context. This is a process supervisor, not a continuous session.

**Pi v2 (future, out of scope):** A possible evolution where Pi maintains a persistent agent session across tasks — keeping model context warm, reusing tool state, and accepting follow-up tasks without subprocess teardown. This would require provider-level session APIs that don't exist today. The permanent loop architecture is designed to support either model: the worker registry and dispatch protocol are the same; only the worker-internal execution strategy changes.

#### Pi v1 as Worker Shell

```
┌─────────────────────────────────────────────────────────┐
│  Pi v1 Shell (long-lived supervisor process)             │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Registration │  │ Task Loop    │  │ Heartbeat     │  │
│  │              │  │              │  │               │  │
│  │ register()   │  │ pull_task()  │  │ emit every    │  │
│  │ with caps,   │  │ execute()    │  │ 30s with      │  │
│  │ provider,    │  │ report()     │  │ status and    │  │
│  │ auth cred    │  │ loop         │  │ resource use  │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────────┐│
│  │ Agent Subprocess (per task)                          ││
│  │                                                      ││
│  │ claude -p "$(cat attack-plan.md)" --model ...        ││
│  │   OR                                                 ││
│  │ codex exec --model ... --yolo "$(cat attack-plan)"   ││
│  │                                                      ││
│  │ Monitored by Pi shell for:                           ││
│  │ - PID liveness                                       ││
│  │ - Heartbeat (stdout activity)                        ││
│  │ - Timeout enforcement                                ││
│  │ - Premature exit → commit progress, re-dispatch      ││
│  └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

#### Pi Registration Flow

1. Pi starts and reads its config (provider, model capabilities, auth credential reference).
2. Pi calls the Helaicopter registration endpoint: `POST /workers/register`.
3. The control plane assigns a `worker_id` and adds the worker to the registry.
4. Pi enters its task loop: `GET /workers/{worker_id}/next-task`.
5. If a task is available and the worker's auth is valid, the control plane returns an `ExecutionEnvelope`.
6. Pi spawns the agent subprocess, monitors it, and reports the result: `POST /workers/{worker_id}/report`.
7. Pi returns to step 4.

#### Pi Heartbeat Contract

Pi emits heartbeats every 30 seconds:
```json
{
    "worker_id": "wkr_abc",
    "status": "busy",
    "current_task_id": "task_auth",
    "current_attempt_id": "att_xyz",
    "agent_pid": 12345,
    "agent_alive": true,
    "last_agent_output_at": "2026-03-26T10:15:30Z",
    "resource_usage": {
        "cpu_percent": 45.0,
        "memory_mb": 2048
    }
}
```

The resolver loop uses heartbeats for:
- Liveness detection (no heartbeat for `heartbeat_timeout_seconds` → worker is dead).
- Stale session detection (agent alive but no output for `agent_stale_seconds` → kill and retry).
- Resource monitoring (surfaced in operator UI).

#### Pi Re-Dispatch (from orchestrate-run)

The orchestrate-run skill learned that agent premature exit is normal: "Agents often exit before finishing. Commit their progress, identify remaining work, re-dispatch with focused prompt." This becomes a first-class Pi behavior:

1. Agent subprocess exits.
2. Pi checks acceptance criteria against the worktree state.
3. If criteria are not met:
   a. Pi commits and pushes any uncommitted work.
   b. Pi generates a focused re-dispatch prompt targeting remaining criteria.
   c. Pi spawns a new agent subprocess with the focused prompt.
   d. This counts as a new attempt (new `attempt_id`, same `task_id`).
4. If criteria are met: Pi reports success.
5. If retry budget is exhausted: Pi reports failure.

### orchestrate-run Learnings to Preserve and Evolve

The `orchestrate-run` skill accumulated critical operational patterns. Each is mapped to its permanent-runtime equivalent:

| orchestrate-run Pattern | Runtime Equivalent |
|---|---|
| Dispatch via real CLI processes (`claude -p`, `codex exec`) | Worker subprocess model — Pi spawns CLI processes, never in-context subagents |
| CronCreate for 2-minute monitoring | Resolver loop heartbeat processing replaces cron polling |
| Session self-registration (`register-session` command) | Worker registration API (`POST /workers/register`) |
| Attack plan generation from plan steps + context | `AttackPlan` model in `ExecutionEnvelope` with structured context assembly |
| Re-dispatch on premature exit with focused prompt | Pi re-dispatch behavior with acceptance criteria checking |
| Session history append (never overwrite) | Attempt history in `TaskNode.attempts` — append-only |
| `.orchestrate/` directory for recovery | `.oats/runtime/<run_id>/` with atomic state + results directories |
| `reconcile-run` for DB/filesystem sync | Resolver loop startup reconciliation: compare registry vs. filesystem state |
| Model locked to run spec (never swap) | `ExecutionEnvelope.model` is authoritative; scheduler respects it |
| Review-gated tasks (pause for human) | `TaskKind.REVIEW` tasks emit `awaiting_review` status; operator UI approval gate |
| Branch naming (`oats/task/<task_id>`) | Unchanged — retained as convention |

**Patterns explicitly NOT preserved:**
- Cron-based polling for worker liveness (replaced by heartbeat protocol).
- Writing session JSON to `.orchestrate/sessions/` (replaced by structured `TaskResult` in `.oats/runtime/`).
- `--dangerously-skip-permissions` as default (worker auth model replaces this; permissions are configured per-worker).

### Auth Model: Provider Credential Adapters

#### Problem

Today, agent sessions inherit auth from the developer's local environment — `~/.claude` tokens for Claude Code, `~/.codex` tokens for Codex. The `orchestrate-run` skill doesn't manage auth at all. This works for a single developer on a single machine but breaks when:
- Multiple workers need different provider accounts (personal vs. team subscription).
- OAuth tokens expire mid-run and need refresh.
- The operator wants visibility into which subscription is paying for which tasks.
- Cost tracking requires associating API spend with specific credentials.

#### Auth Adapter Strategy

Auth is not a single rigid mechanism. Different providers support different auth flows, and the same provider may support multiple approaches. The credential store uses an **adapter pattern** with three tiers:

| Adapter Tier | When Used | Example |
|---|---|---|
| **Managed OAuth / subscription** | Provider supports OAuth and Helaicopter manages the full token lifecycle (acquire, refresh, revoke). | OpenClaw direction for Anthropic and OpenAI — this is the reference target for first-class support. |
| **Delegated local CLI credentials** | Provider doesn't support OAuth or the operator prefers to reuse their existing CLI session. Helaicopter delegates to the local credential store (`~/.claude/`, `~/.codex/`) without managing the token lifecycle. | Current Claude Code and Codex CLI auth. The worker inherits the developer's existing session. |
| **API key fallback** | Direct API key injection via environment variable. Simplest, no refresh, no expiry management. | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. |

The `credential_type` field in the credential store distinguishes these. The resolver's auth check adapts per type:
- `oauth_token`: Check `token_expires_at`, auto-refresh if within threshold, block dispatch if refresh fails.
- `local_cli_session`: No expiry check — the worker is responsible for its own session validity. Helaicopter records usage but does not manage the credential.
- `api_key`: No expiry check. Verify key is present. Inject via env var.

OpenClaw remains the reference direction for managed OAuth/subscription support. As providers adopt OAuth, credentials migrate from `local_cli_session` → `oauth_token` without changing the worker registration protocol.

#### Auth Credential Store

Auth credentials are stored in Helaicopter's app SQLite database (authoritative for all credential state — see State Ownership above):

```python
class AuthCredential(BaseModel):
    credential_id: str                       # cred_<ulid>
    provider: ProviderName                   # claude | codex
    credential_type: CredentialType          # oauth_token | api_key | local_cli_session

    # OAuth fields (oauth_token type only)
    access_token: str | None                 # encrypted at rest
    refresh_token: str | None                # encrypted at rest
    token_expires_at: datetime | None
    oauth_scopes: list[str] | None

    # API key fields (api_key type only)
    api_key: str | None                      # encrypted at rest

    # Local CLI session fields (local_cli_session type only)
    cli_config_path: str | None              # e.g., ~/.claude, ~/.codex — informational only

    # Subscription metadata (any type)
    subscription_id: str | None              # links to subscription_settings
    subscription_tier: str | None            # e.g., "max", "pro", "team"
    rate_limit_tier: str | None              # for dispatch throttling

    # Lifecycle
    status: CredentialStatus                 # active | expired | revoked | refreshing
    created_at: datetime
    last_used_at: datetime | None
    last_refreshed_at: datetime | None

    # Cost tracking
    cumulative_cost_usd: float               # total spend through this credential
    cost_since_reset: float                  # spend since last billing cycle
```

```sql
CREATE TABLE auth_credentials (
    credential_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    credential_type TEXT NOT NULL,
    access_token_encrypted BLOB,
    refresh_token_encrypted BLOB,
    token_expires_at TEXT,
    oauth_scopes_json TEXT,
    api_key_encrypted BLOB,
    subscription_id TEXT,
    subscription_tier TEXT,
    rate_limit_tier TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    last_refreshed_at TEXT,
    cumulative_cost_usd REAL DEFAULT 0.0,
    cost_since_reset REAL DEFAULT 0.0
);
```

#### OAuth Flow

For providers that support OAuth (OpenClaw direction — Anthropic and OpenAI are moving toward OAuth for CLI tools):

1. Operator initiates auth via Helaicopter UI: "Add Claude credential."
2. Helaicopter opens the provider's OAuth consent screen (browser redirect).
3. On callback, Helaicopter receives `access_token` + `refresh_token`.
4. Tokens are encrypted and stored in `auth_credentials`.
5. Workers reference credentials by `credential_id` in their registration.
6. The resolver loop checks `token_expires_at` before dispatch. If expiring within 5 minutes, trigger refresh.
7. On refresh failure, the worker's status transitions to `auth_expired` and it stops receiving tasks.

#### Local CLI Session Delegation

For providers where the developer already has a working CLI session:
- Claude: Reuses `~/.claude/` session. Worker subprocess inherits the developer's authenticated state.
- Codex: Reuses `~/.codex/` session. Same inheritance model.
- Stored as `credential_type: local_cli_session`. Helaicopter tracks usage but does not manage the token.
- If the CLI session expires, the worker's task will fail and the resolver treats it as a retryable error. The operator must re-authenticate via the CLI directly.

#### API Key Fallback

Until OAuth is universally supported:
- Claude: `ANTHROPIC_API_KEY` environment variable, stored as `credential_type: api_key`.
- Codex: `OPENAI_API_KEY` environment variable, stored as `credential_type: api_key`.
- The operator can register API keys via the UI. They are encrypted at rest.

#### Credential-Worker Binding

Each worker registration references an `auth_credential_id`. When the resolver dispatches a task to a worker:
1. Look up the worker's credential.
2. Verify `status == active` and `token_expires_at` is not imminent.
3. Inject the credential into the agent subprocess's environment (via env var, not command-line argument).
4. On task completion, update `last_used_at` and `cumulative_cost_usd` from the `TaskResult.cost_estimate`.

### Scheduler Dispatch Affinity by Provider/Auth Capability

The v2 scheduler is provider-agnostic: it picks the next ready task and spawns an agent. The permanent loop scheduler must consider:

#### Affinity Rules

```python
class DispatchAffinity(BaseModel):
    """Rules for matching tasks to workers."""

    # Required: task specifies provider and model
    required_provider: ProviderName
    required_model: str

    # Optional: prefer specific worker tags
    preferred_tags: list[str] = []

    # Optional: sticky worker (prefer re-dispatching to same worker for retries)
    sticky_worker_id: str | None = None

    # Constraints
    requires_worktree: bool = True
    requires_discovery_support: bool = False
```

#### Dispatch Algorithm

```python
def select_worker(task: TaskNode, registry: WorkerRegistry) -> Worker | None:
    affinity = task.dispatch_affinity

    # 1. Filter: capable workers with valid auth
    candidates = registry.idle_workers(
        provider=affinity.required_provider,
        model=affinity.required_model,
        auth_status="active",
    )

    if not candidates:
        return None

    # 2. Prefer sticky worker (for retries — same worktree, warmed context)
    if affinity.sticky_worker_id:
        sticky = [w for w in candidates if w.worker_id == affinity.sticky_worker_id]
        if sticky:
            return sticky[0]

    # 3. Prefer workers with matching tags
    if affinity.preferred_tags:
        tagged = [w for w in candidates
                  if set(affinity.preferred_tags) <= set(w.capabilities.tags)]
        if tagged:
            candidates = tagged

    # 4. Prefer workers with lower current load
    candidates.sort(key=lambda w: w.current_task_count)

    return candidates[0]
```

#### Provider-Specific Dispatch Behavior

| Provider | Auth Adapter | Dispatch via | Auth injection | Monitoring |
|---|---|---|---|---|
| Claude | `local_cli_session` | `claude -p "..." --model <model>` | Inherits `~/.claude` session (no injection) | PID + stdout heartbeat |
| Claude | `api_key` | Same CLI | `ANTHROPIC_API_KEY` env var | Same |
| Claude | `oauth_token` | Same CLI | OAuth token injected into `~/.claude/credentials.json` | Same |
| Codex | `local_cli_session` | `codex exec --model <model> --yolo "..."` | Inherits `~/.codex` session (no injection) | PID + stdout heartbeat |
| Codex | `api_key` | Same CLI | `OPENAI_API_KEY` env var | Same |
| Codex | `oauth_token` | Same CLI | OAuth token injected into `~/.codex/credentials.json` | Same |

### Helaicopter Operator UI / Control-Plane Implications

The UI evolves from a read-only dashboard to an operator console:

#### New UI Surfaces

**Worker Dashboard:**
- Worker list with status badges (idle/busy/draining/dead/auth_expired).
- Per-worker: current task, heartbeat freshness, resource usage, credential status.
- Actions: drain worker, remove worker, refresh auth.

**Queue Monitor:**
- Ready queue depth per run and global.
- Deferred tasks with reasons (no capable worker, auth expired, rate limited).
- Dispatch history: which task went to which worker, when, outcome.

**Auth Management:**
- Credential list with provider, type, status, expiry, cumulative cost.
- Add credential flow (OAuth redirect or API key entry).
- Refresh/revoke actions.
- Cost breakdown by credential.

**Run Control (extended from v2):**
- Pause/resume individual runs.
- Cancel tasks (with cascade control: cancel descendants or not).
- Force-retry failed tasks.
- Re-route: change a task's required provider/model.
- Insert task: add a node to the live graph (operator-initiated discovery).

#### API Extensions

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/workers/register` | Worker self-registration |
| `GET` | `/workers/{worker_id}/next-task` | Pull dispatch — worker requests next task |
| `POST` | `/workers/{worker_id}/heartbeat` | Worker heartbeat |
| `POST` | `/workers/{worker_id}/report` | Worker reports task result |
| `DELETE` | `/workers/{worker_id}` | Deregister worker |
| `GET` | `/workers` | List all registered workers with status |
| `POST` | `/workers/{worker_id}/drain` | Drain worker (finish current, stop accepting) |
| `GET` | `/auth/credentials` | List auth credentials |
| `POST` | `/auth/credentials` | Add credential (API key or initiate OAuth) |
| `GET` | `/auth/credentials/{id}/oauth/callback` | OAuth callback handler |
| `DELETE` | `/auth/credentials/{id}` | Revoke credential |
| `POST` | `/auth/credentials/{id}/refresh` | Force token refresh |
| `GET` | `/dispatch/queue` | Ready queue snapshot with deferred reasons |
| `GET` | `/dispatch/history` | Recent dispatch log |
| `POST` | `/orchestration/runs/{run_id}/pause` | Pause a run |
| `POST` | `/orchestration/runs/{run_id}/tasks/{task_id}/cancel` | Cancel a task |
| `POST` | `/orchestration/runs/{run_id}/tasks/{task_id}/force-retry` | Force retry |
| `POST` | `/orchestration/runs/{run_id}/tasks/{task_id}/reroute` | Change provider/model |
| `POST` | `/orchestration/runs/{run_id}/tasks` | Insert a task (operator discovery) |

#### Backend Architecture Change

The Helaicopter backend gains a background task — the resolver loop. **Deployment assumption:** a single backend process runs the resolver loop (see Deployment Model above). No distributed coordination is required.

```
┌─────────────────────────────────────────────────────────────┐
│  Helaicopter Backend (FastAPI)                               │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ HTTP Router Layer                                     │   │
│  │ /orchestration/* /workers/* /auth/* /dispatch/*        │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                              │                               │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Application Layer                                     │   │
│  │ orchestration.py  workers.py  auth.py  dispatch.py    │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                              │                               │
│  ┌──────────────────────────▼───────────────────────────┐   │
│  │ Resolver Loop (background asyncio task)               │   │
│  │                                                       │   │
│  │ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │   │
│  │ │ Queue   │ │ Registry │ │ Auth     │ │ State     │ │   │
│  │ │ Manager │ │ Manager  │ │ Manager  │ │ Persister │ │   │
│  │ └─────────┘ └──────────┘ └──────────┘ └───────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Storage Layer                                         │   │
│  │ SQLite (workers, auth, subscriptions)                 │   │
│  │ .oats/runtime/ (graph state, results, events)         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Rollout Strategy

### Phase 1: Worker Registry and Auth Store

Introduce `worker_registry` and `auth_credentials` tables. Worker registration/deregistration API. Auth credential CRUD. No resolver loop yet — this is the data model foundation.

### Phase 2: Resolver Loop Core

Background asyncio task that processes completions, evaluates edges, and dispatches to workers. Pull-dispatch endpoint for workers. Heartbeat processing and dead-worker reaping. Single-run support initially.

### Phase 3: Pi Worker Shell

Pi-side implementation: registration, task loop, heartbeat emission, subprocess management, re-dispatch on premature exit, acceptance criteria checking. This is the canonical worker implementation.

### Phase 4: OAuth and Credential Lifecycle

OAuth flow for Claude and Codex. Token refresh automation. Credential-status-aware dispatch (skip workers with expired auth). Cost tracking per credential.

### Phase 5: Operator UI

Worker dashboard, queue monitor, auth management, run control actions (pause, cancel, force-retry, re-route, insert task).

### Phase 6: Multi-Run and Cross-Run Dependencies

Multiple active runs in the resolver loop. Run prioritization. Cross-run dependency edges (future).

## Migration Notes

### From v2 Single-Process Runtime

The v2 `oats run` command continues to work as a convenience wrapper:
1. `oats run <spec.md>` submits the run to the resolver loop (if running) or falls back to the v2 single-process executor.
2. `oats resume <run_id>` signals the resolver loop to re-evaluate the run.
3. `oats watch <run_id>` reads state from `.oats/runtime/` (unchanged).

### From orchestrate-run Skill

The orchestrate-run skill becomes a thin wrapper:
1. Parse the run spec (unchanged).
2. Generate attack plans (delegated to `AttackPlan` builder).
3. Submit to the resolver loop via `POST /orchestration/runs`.
4. Monitor via the operator UI (replaces cron-based monitoring).

The skill retains its role as the user-facing entry point for "run this spec" but delegates execution entirely to the permanent runtime.
