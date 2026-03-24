# Claude Code Orchestrator — Design Spec

**Date:** 2026-03-20
**Status:** Draft
**Replaces:** Oats CLI and all associated infrastructure

## Overview

Replace the entire Oats orchestration stack with a single Claude Code superpowers skill that acts as the orchestrator. A human starts a Claude Code session, invokes the skill, points it at a markdown run spec, and the skill handles task expansion, dispatch, monitoring, and completion — all within one session.

This eliminates: the Oats Python CLI, the orchestration control plane (Docker, Postgres, Redis), the macOS launchd worker, artifact reconciliation, and ~5000 lines of orchestration Python. It replaces them with one skill file, one Alembic migration, a small Python DB helper, six API routes, and rebuilt frontend components.

## Motivation

The current system requires Docker containers, an orchestration server, launchd workers, a custom Python CLI, dual data stores (orchestration API + local filesystem artifacts), and complex reconciliation logic. All of this exists to do one thing: run AI agent tasks in parallel with dependency ordering. Claude Code can do this natively via CLI-spawned processes and `/loop` polling.

## System Flow

Three phases within a single Claude Code session:

```
PREPARE → DISPATCH → MONITOR
```

### Prepare

1. Human invokes `superpowers:orchestrate-run`, points at a run spec
2. Skill parses the markdown spec — extracts config, defaults, tasks, dependencies
3. Validates the DAG (no cycles, all `depends_on` references exist)
4. Writes run + tasks + dependencies to SQLite via the DB helper (status: `preparing`)
5. For each task — the **expansion** phase:
   a. Reads referenced plan steps from the linked superpowers plan
   b. Reads all linked context files
   c. Explores codebase for additional relevant code (imports, types, tests)
   d. Writes `~/helaicopter/runs/{run_id}/tasks/{task_id}/attack-plan.md`
   e. Updates SQLite with `attack_plan_path`
6. Presents each attack plan to the human for review/editing
7. Creates git worktrees per task
8. Run status → `ready`

### Dispatch

1. Topological sort of tasks
2. For each task with no unmet dependencies (respecting concurrency limit):
   a. Build CLI command (see CLI Commands below)
   b. Run in task's worktree as a background process, capture PID
   c. Parse session ID from JSON output stream (primary ID capture method)
   d. Write session record to SQLite via DB helper
   e. Task status → `running`
3. The spawned session's attack plan includes instructions to self-register its conversation ID via the same DB helper (backup ID capture method)

### CLI Commands

The orchestrator constructs different commands depending on the agent:

**Claude Code:**
```bash
# Dispatch (non-interactive, streaming JSON for session ID capture)
claude -p "$(cat attack-plan.md)" --model <model> --thinking <thinking> \
  --output-format stream-json <cli_args>
# Session ID extracted from the stream-json output

# Resume a session (e.g., for retry with context preservation)
claude --resume <session-id> -p "The previous attempt failed because X. Try again with Y." \
  --output-format stream-json

# Continue most recent session
claude -c -p "follow-up instruction" --output-format stream-json
```

**Codex:**
```bash
# Dispatch (non-interactive, JSONL output for session ID capture)
codex exec "$(cat attack-plan.md)" --json <cli_args>
# Session ID extracted from thread.started JSONL event

# Resume a session (retry with context preservation)
codex exec resume <session-id> --json

# Resume most recent session
codex exec resume --last --json
```

**Key advantage of `--resume` for retries:** Instead of creating a cold new session, `--resume` preserves the full conversation history from the failed attempt. The agent knows what it already tried and why it failed, making retries significantly more effective.

### Monitor (via `/loop`)

1. Poll interval configurable (default 2 min)
2. For each running session:
   a. Check process liveness via `ps -p $PID` (exit code 0 = alive)
   b. If process exited, read exit code and check SQLite for self-reported status
3. On task completion: status → `completed`, check dependents, auto-dispatch unblocked tasks (multiple dispatches per loop iteration if several tasks completed between polls)
4. On `review: true` task completion: status → `review`, notify human, wait for approval
5. On task failure: status → `failed`, notify human with error context. Human can request retry (see Retry Semantics below)
6. Enforce concurrency: count running sessions, dispatch up to `concurrency - running_count` new tasks
7. When all tasks done: run status → `completed`, final summary

### Retry Semantics

When a task fails, the human can request a retry. Two strategies:

**Strategy A — Resume (preferred):** Use `claude --resume <session-id>` or `codex exec resume <session-id>` to continue the failed session with a follow-up prompt explaining what went wrong. This preserves the full conversation history — the agent knows what it tried and why it failed.

1. The orchestrator sends a follow-up prompt to the existing session via `--resume`
2. A new `orchestration_session` row is created (the old one preserved for history, linked to same task)
3. Task status → `running` again
4. Same worktree is reused (the agent's partial work is still there)

**Strategy B — Fresh start:** For cases where the approach was fundamentally wrong and a clean slate is needed.

1. A new git worktree is created (or the existing one is reset)
2. The attack plan can be revised
3. A new `orchestration_session` row is created
4. Task status → `running` again
5. Dispatched as a new cold session

The human chooses the strategy. Multiple sessions per task is expected — the schema supports it via the `orchestration_session` table's foreign key to `orchestration_task`.

### Orchestrator Crash Recovery

If the orchestrator session dies (terminal closed, crash, timeout), background agent processes continue running. To recover:

1. Start a new Claude Code session, invoke the orchestrator skill
2. Point it at the run ID (not a spec) — the skill detects this is a resume, not a new run
3. Reads current state from SQLite: which tasks are running, completed, failed
4. Checks liveness of running sessions via `ps -p $PID`
5. Updates SQLite for any sessions that exited while unmonitored
6. Resumes the monitor loop

The skill must distinguish between `orchestrate-run spec.md` (new run) and `orchestrate-run --resume {run_id}` (recovery).

## Run Spec Format

Markdown format referencing a superpowers plan. Tasks are deliberately thin — the expansion phase turns them into rich attack plans.

```markdown
# Run: Refactor Auth Module

## Config
concurrency: 2
base_branch: main
plan: docs/superpowers/plans/2026-03-20-auth-refactor-plan.md

## Defaults
agent: claude
model: sonnet
thinking: high
cli_args: --max-turns 50

## Tasks

### task-1: Extract token validation
plan_steps: [1, 2]
context:
  - src/lib/auth/middleware.ts
  - src/lib/auth/types.ts

### task-2: Add refresh token support
plan_steps: [3]
depends_on: [task-1]
model: opus
thinking: extended
review: true

### task-3: Update API docs
plan_steps: [4]
depends_on: [task-1]
agent: codex
context:
  - docs/api/
```

### Task Fields

| Field | Required | Inherits from Defaults | Description |
|-------|----------|----------------------|-------------|
| `plan_steps` | yes | no | Array of step numbers from the superpowers plan |
| `depends_on` | no | no | Array of task IDs that must complete first |
| `agent` | no | yes | `claude` or `codex` |
| `model` | no | yes | Model name (sonnet, opus, etc.) |
| `thinking` | no | yes | Reasoning effort: high, medium, low, extended |
| `context` | no | no | Files/directories for context expansion |
| `review` | no | no | `true` to require human approval before cascading (default `false`). Maps to `review_required` column in schema. |
| `cli_args` | no | yes | Pass-through CLI arguments appended to the command |
| `acceptance_criteria` | no | no | Validation commands run by the agent session before reporting completion |

### Attack Plan Template

Each task's thin spec gets expanded into a self-contained `attack-plan.md`. The template structure:

```markdown
# Task: {task_title}
Run: {run_id} | Task: {task_id}

## Objective
{Expanded from plan steps — what this task must accomplish}

## Background Context
{Content from linked context files, relevant code snippets, type definitions, etc.}

## Specific Instructions
{Detailed implementation steps derived from the superpowers plan steps}

## Files to Modify
{List of files identified during expansion, with brief notes on what to change}

## Acceptance Criteria
{From the task spec, if provided. Commands to run for validation.}
Run these before reporting completion:
- {acceptance_criteria commands}

## Session Registration
When you start, run:
`python -m helaicopter_db.orchestration register-session --run-id {run_id} --task-id {task_id} --conversation-id $YOUR_SESSION_ID`

When you finish, run:
`python -m helaicopter_db.orchestration complete-session --run-id {run_id} --task-id {task_id} --status completed`

If you encounter an unrecoverable error, run:
`python -m helaicopter_db.orchestration complete-session --run-id {run_id} --task-id {task_id} --status failed --error "description"`
```

The human reviews and can edit each attack plan before dispatch.

## SQLite Write Mechanism

A small Python module (`python/helaicopter_db/orchestration.py`) provides both a programmatic API and a CLI interface for all SQLite writes. This is used by:

- The orchestrator skill (via shell: `python -m helaicopter_db.orchestration <command> <args>`)
- Spawned agent sessions (via the same CLI, for self-registration)
- The FastAPI backend (via direct import, for any mutation endpoints)

### CLI Interface

```bash
# Run management
python -m helaicopter_db.orchestration create-run --id <uuid> --title "..." --spec-path "..." --plan-path "..." --base-branch main --concurrency 2
python -m helaicopter_db.orchestration update-run --id <uuid> --status running

# Task management
python -m helaicopter_db.orchestration create-task --run-id <uuid> --task-id task-1 --title "..." --agent claude --model sonnet --thinking high
python -m helaicopter_db.orchestration update-task --run-id <uuid> --task-id task-1 --status running --worktree-path "..."

# Dependency management
python -m helaicopter_db.orchestration add-dependency --run-id <uuid> --task-id task-2 --depends-on task-1

# Session management
python -m helaicopter_db.orchestration create-session --run-id <uuid> --task-id task-1 --pid 12345 --cli-command "claude --prompt ..."
python -m helaicopter_db.orchestration register-session --run-id <uuid> --task-id task-1 --conversation-id <id>
python -m helaicopter_db.orchestration complete-session --run-id <uuid> --task-id task-1 --status completed
python -m helaicopter_db.orchestration complete-session --run-id <uuid> --task-id task-1 --status failed --error "description"

# Queries (for the orchestrator's monitor loop)
python -m helaicopter_db.orchestration get-running-sessions --run-id <uuid>
python -m helaicopter_db.orchestration get-ready-tasks --run-id <uuid>
```

All commands use parameterized queries. No raw string interpolation into SQL.

## SQLite Schema

Four new tables in the existing database, replacing `FactOrchestrationRun` and `FactOrchestrationTaskAttempt`.

```sql
CREATE TABLE orchestration_run (
    id TEXT PRIMARY KEY,              -- UUID generated by orchestrator
    title TEXT NOT NULL,
    spec_path TEXT NOT NULL,
    plan_path TEXT,
    base_branch TEXT NOT NULL,
    concurrency INTEGER DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'preparing',  -- preparing|ready|running|completed|failed
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE TABLE orchestration_task (
    run_id TEXT NOT NULL REFERENCES orchestration_run(id),
    task_id TEXT NOT NULL,            -- from spec (e.g. "task-1")
    title TEXT NOT NULL,
    plan_steps TEXT,                  -- JSON array, e.g. "[1, 2]"
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|ready|running|completed|failed|review
    agent TEXT NOT NULL,              -- claude|codex
    model TEXT,
    thinking TEXT,                    -- high|medium|low|extended
    worktree_path TEXT,
    attack_plan_path TEXT,
    cli_args TEXT,                    -- pass-through CLI arguments
    acceptance_criteria TEXT,         -- JSON array of validation commands
    review_required BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    PRIMARY KEY (run_id, task_id)
);

CREATE TABLE orchestration_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    conversation_id TEXT,             -- from CLI JSON output stream (primary)
    self_reported_id TEXT,            -- from session self-registration (backup)
    session_name TEXT,                -- optional human-readable name for --resume by name
    pid INTEGER,
    cli_command TEXT,                 -- full command used to spawn
    status TEXT DEFAULT 'running',    -- running|completed|failed
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    exit_code INTEGER,
    error_text TEXT,
    FOREIGN KEY (run_id, task_id) REFERENCES orchestration_task(run_id, task_id)
);

CREATE TABLE orchestration_dependency (
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    FOREIGN KEY (run_id, task_id) REFERENCES orchestration_task(run_id, task_id),
    FOREIGN KEY (run_id, depends_on_task_id) REFERENCES orchestration_task(run_id, task_id),
    PRIMARY KEY (run_id, task_id, depends_on_task_id)
);

-- Performance indexes
CREATE INDEX idx_orchestration_task_run_id ON orchestration_task(run_id);
CREATE INDEX idx_orchestration_task_status ON orchestration_task(run_id, status);
CREATE INDEX idx_orchestration_session_task ON orchestration_session(run_id, task_id);
CREATE INDEX idx_orchestration_session_status ON orchestration_session(status);
```

### Status Values

**Run:** `preparing` → `ready` → `running` → `completed` | `failed`

**Task:** `pending` → `ready` → `running` → `completed` | `failed` | `review`

A task is `pending` until created. It becomes `ready` when all its dependencies are `completed` (or it has no dependencies). The orchestrator checks readiness during dispatch and each monitor loop iteration.

**Session:** `running` → `completed` | `failed`

## API Routes

Six endpoints replacing ~15 existing orchestration routes:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/orchestration/runs` | List all runs with status, task count, timestamps |
| GET | `/orchestration/runs/{run_id}` | Single run with full task details and sessions |
| GET | `/orchestration/runs/{run_id}/tasks/{task_id}` | Task detail with attack plan content, session, conversation link |
| GET | `/orchestration/runs/{run_id}/dag` | Dependency graph: nodes (tasks) + edges + status per node |
| POST | `/orchestration/runs/{run_id}/tasks/{task_id}/approve` | Approve a task in `review` status, triggering cascade |
| POST | `/orchestration/runs/{run_id}/tasks/{task_id}/retry` | Retry a failed task (creates new session) |

The four GET endpoints are straight SQLite reads. The two POST endpoints write to SQLite via the DB helper module (direct import). The approve endpoint sets the task to `completed` and could trigger a webhook or write a flag file that the orchestrator's `/loop` picks up. The retry endpoint creates a new session record and sets the task back to `running`.

Note: The orchestrator skill session is the primary actor for dispatching tasks. The POST endpoints serve as a secondary interface — they update state that the orchestrator's next `/loop` poll will pick up and act on.

## Frontend

The orchestration hub (`orchestration-hub.tsx`) gets rebuilt with three views:

### Run List
Table/cards showing all runs with status badges, task progress (e.g. 3/5 completed), timestamps. Click through to detail.

### Run Detail
- **Left panel:** DAG visualization. Nodes are tasks colored by status, edges are dependencies.
- **Right panel:** Task list with status, agent, model, conversation link, timestamps.
- Action buttons: approve (for tasks in `review`), retry (for failed tasks).

### Task Detail
Expandable or drill-down view:
- Attack plan content (rendered markdown)
- Session history: all sessions for this task, each with conversation ID (clickable link to conversation view), PID, exit code, timestamps
- Worktree path, branch name
- Error text if failed

**Removed components:** overnight-oats-panel, oats-pr-stack.
**Kept/rebuilt:** orchestration-hub (shell), orchestration page, tabs.

## File System Layout

```
~/helaicopter/
├── runs/
│   └── {run_id}/
│       ├── spec.md                    # copy of the original run spec
│       └── tasks/
│           └── {task_id}/
│               └── attack-plan.md     # expanded prompt
└── worktrees/
    └── {run_id}-{task_id}/            # git worktree checkouts
```

### Worktree Cleanup

Worktrees are cleaned up when a run reaches terminal status (`completed` or `failed`). The orchestrator skill runs `git worktree remove` for each task's worktree during the final summary phase. For failed runs, the human can choose to keep worktrees for debugging. Orphaned worktrees from crashed orchestrator sessions can be cleaned up manually or via `git worktree prune`.

## Superpowers Integration

Superpowers is cloned/managed at `/Users/tony/Code/agent-harness/`. Helaicopter's Claude Code sessions load skills from there instead of the global plugin path.

The new orchestration skill lives alongside existing superpowers skills:

```
/Users/tony/Code/agent-harness/
├── skills/
│   ├── brainstorming/                 # existing
│   ├── writing-plans/                 # existing
│   ├── ...
│   └── orchestrate-run/               # NEW
│       └── SKILL.md
```

### Full Pipeline

1. `superpowers:brainstorming` → design spec
2. `superpowers:writing-plans` → implementation plan
3. `superpowers:orchestrate-run` → parse spec, expand tasks, dispatch, monitor

Each skill invokes the next. The orchestrator skill is the final stage that turns plans into running agent sessions.

### Run Spec Authoring

Run specs live in the repo, conventionally under `docs/runs/` or alongside the plan they reference. The spec author links to a superpowers plan and defines tasks that reference plan steps. The spec can be written by hand or generated by the writing-plans skill as a final output.

## Deletion Scope

### Entire packages/directories removed
- `python/oats/` — orchestration CLI, models, parser, planner, runner, runtime state
- `ops/launchd/` — worker plist template
- `.oats/` — config, runtime, runs, artifacts
- `.oats-worktrees/`

### Backend code removed
- `python/helaicopter_api/router/orchestration.py`
- `python/helaicopter_api/router/router.py` — remove orchestration router imports and includes
- `python/helaicopter_api/application/orchestration.py`
- `python/helaicopter_api/application/oats_run_actions.py`
- `python/helaicopter_api/schema/orchestration.py`
- `python/helaicopter_api/ports/orchestration.py`
- `python/helaicopter_api/pure/orchestration_analytics.py`
- `python/helaicopter_db/orchestration_facts.py`
- All orchestration dependencies from `pyproject.toml`

### Frontend code removed
- `src/components/orchestration/overnight-oats-panel.tsx`
- `src/components/orchestration/oats-pr-stack.tsx`
- `src/components/orchestration/oats-view-model.ts`
- `src/components/orchestration/oats-view-model.test.ts`
- `src/components/orchestration/tabs.ts` — rewrite for new tab structure
- `src/components/orchestration/tabs.test.ts` — rewrite
- Orchestration-specific code in `src/lib/client/endpoints.ts` — replace with new endpoints
- Orchestration-specific code in `src/lib/client/normalize.ts` — replace with new normalizers
- Orchestration-specific Zod schemas in `src/lib/client/schemas/`

### Database tables deprecated (via Alembic migration)
- `FactOrchestrationRun` → drop
- `FactOrchestrationTaskAttempt` → drop
- `python/alembic/versions/20260319_0009_orchestration_analytics_facts.py` — superseded by new migration

### Docs removed/archived
- `docs/orchestration/` (orchestration-specific content)
- Oats-related design specs in `docs/superpowers/specs/`
- Oats-related plans in `docs/superpowers/plans/`

### What stays
- The frontend orchestration page shell (`src/app/orchestration/page.tsx`) — rebuilt
- The orchestration hub component (`orchestration-hub.tsx`) — rebuilt
- All non-orchestration backend/frontend code
- Alembic + SQLite infrastructure
- Examples directory (updated with new spec format)

## Key Design Decisions

1. **Minimal Python: DB helper only.** The skill IS the orchestrator. The only Python code is `helaicopter_db/orchestration.py` — a thin CLI/library for SQLite reads and writes with parameterized queries. No orchestration logic in Python.

2. **Attack plan expansion bridges the context gap.** A superpowers plan produces tightly-scoped steps. The expansion phase enriches each into a self-contained briefing so a cold CLI session has everything it needs.

3. **Dual ID capture.** CLI output parsing + session self-registration via the same DB helper. If one fails, the other catches it.

4. **Auto-cascade with optional review gates.** Tasks dispatch automatically when dependencies clear. `review: true` per task pauses for human approval. POST endpoints allow the frontend to trigger approvals too.

5. **First-class fields for what matters.** `model` and `thinking` are explicit fields. Everything else passes through via `cli_args`. The full constructed command is stored in `orchestration_session.cli_command` for observability.

6. **Superpowers as controlled dependency.** Loaded from `/Users/tony/Code/agent-harness/` — versioned, extensible, not a global plugin.

7. **Crash recovery via resume.** The skill can resume a run by reading SQLite state, checking process liveness, and re-entering the monitor loop. No state is held only in memory.

8. **Acceptance criteria run by the agent.** Validation commands are included in the attack plan and executed by the spawned agent session before it reports completion. The orchestrator trusts the agent's self-reported status.
