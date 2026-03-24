# Claude Code Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Oats + legacy orchestration orchestration stack with a Claude Code skill-driven orchestrator, SQLite tracking, and rebuilt frontend.

**Architecture:** A superpowers skill acts as the orchestrator within a Claude Code session. It parses markdown run specs, expands tasks into attack plans, dispatches CLI sessions (`claude`/`codex`), and monitors via `/loop`. A small Python DB helper handles all SQLite writes. Six FastAPI endpoints serve the frontend. Four new tables replace the old schema.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0+, Pydantic 2.7+, Alembic, Next.js/React, TypeScript, Zod

**Spec:** `docs/superpowers/specs/2026-03-20-claude-code-orchestrator-design.md`

---

## File Structure

### Files to Create
- `python/helaicopter_db/orchestration.py` — DB helper module (CLI + programmatic API)
- `python/alembic/versions/20260320_orchestration_v2.py` — Alembic migration (drop old tables, create new)
- `python/helaicopter_api/schema/orchestration_v2.py` — New Pydantic response schemas
- `python/helaicopter_api/application/orchestration_v2.py` — New business logic (SQLite reads)
- `python/helaicopter_api/router/orchestration_v2.py` — New FastAPI router (6 endpoints)
- `tests/test_orchestration_db.py` — Tests for DB helper
- `tests/test_orchestration_api.py` — Tests for API routes
- `src/components/orchestration/run-list.tsx` — Run list view
- `src/components/orchestration/run-detail.tsx` — Run detail with DAG + task list
- `src/components/orchestration/task-detail.tsx` — Task detail with session history
- `src/components/orchestration/dag-view.tsx` — DAG visualization component
- `src/lib/client/orchestration.ts` — Frontend client endpoints + types
- `examples/sample_orchestration_run.md` — Example run spec in new format

### Files to Modify
- `python/helaicopter_api/router/router.py` — Remove old orchestration/legacy-orchestration imports, add new router
- `python/helaicopter_api/bootstrap/services.py` — Remove oats/legacy-orchestration services
- `python/helaicopter_api/server/config.py` — Remove legacy orchestration settings if any
- `python/helaicopter_db/models/oltp.py` — Add new SQLAlchemy models
- `pyproject.toml` — Remove legacy orchestration dependency
- `src/app/orchestration/page.tsx` — Rebuild page with new components
- `src/components/orchestration/orchestration-hub.tsx` — Rebuild hub
- `src/lib/client/endpoints.ts` — Remove old orchestration endpoints, add new

### Files to Delete
See deletion scope in spec. ~30 files across backend, frontend, ops, docs.

---

## Task 1: Delete Old Orchestration Infrastructure

**Files:**
- Delete: `ops/legacy-orchestration/`, `ops/launchd/`, `ops/scripts/legacy-orchestration-worker.sh`, `bin/oats-legacy-orchestration-up`
- Delete: `python/oats/` (entire package)
- Delete: `.oats/`, `.oats-worktrees/` (if tracked)
- Modify: `pyproject.toml` — remove `legacy-orchestration` dependency and oats entry points

- [ ] **Step 1: Remove ops infrastructure**

Delete the following directories and files:
```bash
rm -rf ops/legacy-orchestration/ ops/launchd/ ops/scripts/legacy-orchestration-worker.sh bin/oats-legacy-orchestration-up
```

- [ ] **Step 2: Remove the oats Python package**

```bash
rm -rf python/oats/
```

- [ ] **Step 3: Remove legacy orchestration dependency from pyproject.toml**

In `pyproject.toml`, remove `"legacy-orchestration>=3.0.0"` (or similar) from the dependencies list. Also remove any oats-related `[project.scripts]` entry points if present.

- [ ] **Step 4: Verify the project still loads**

```bash
cd /Users/tony/Code/helaicopter && uv run python -c "import helaicopter_api; print('ok')"
```

Expected: `ok` (no import errors from removed oats/legacy-orchestration code — if there are, fix them in next task)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: remove oats CLI and legacy-orchestration infrastructure"
```

---

## Task 2: Delete Old Backend Orchestration Code

**Files:**
- Delete: `python/helaicopter_api/router/orchestration.py`
- Delete: `python/helaicopter_api/router/legacy-orchestration_orchestration.py`
- Delete: `python/helaicopter_api/application/orchestration.py`
- Delete: `python/helaicopter_api/application/legacy-orchestration_orchestration.py`
- Delete: `python/helaicopter_api/application/oats_run_actions.py`
- Delete: `python/helaicopter_api/schema/orchestration.py`
- Delete: `python/helaicopter_api/schema/legacy-orchestration_orchestration.py`
- Delete: `python/helaicopter_api/ports/orchestration.py`
- Delete: `python/helaicopter_api/ports/legacy-orchestration.py`
- Delete: `python/helaicopter_api/adapters/legacy-orchestration_http.py`
- Delete: `python/helaicopter_api/pure/orchestration_analytics.py`
- Delete: `python/helaicopter_db/orchestration_facts.py`
- Modify: `python/helaicopter_api/router/router.py`
- Modify: `python/helaicopter_api/bootstrap/services.py`

- [ ] **Step 1: Delete backend orchestration files**

```bash
rm -f python/helaicopter_api/router/orchestration.py \
      python/helaicopter_api/router/legacy-orchestration_orchestration.py \
      python/helaicopter_api/application/orchestration.py \
      python/helaicopter_api/application/legacy-orchestration_orchestration.py \
      python/helaicopter_api/application/oats_run_actions.py \
      python/helaicopter_api/schema/orchestration.py \
      python/helaicopter_api/schema/legacy-orchestration_orchestration.py \
      python/helaicopter_api/ports/orchestration.py \
      python/helaicopter_api/ports/legacy-orchestration.py \
      python/helaicopter_api/adapters/legacy-orchestration_http.py \
      python/helaicopter_api/pure/orchestration_analytics.py \
      python/helaicopter_db/orchestration_facts.py
```

- [ ] **Step 2: Clean up router.py**

Open `python/helaicopter_api/router/router.py`. Remove imports and `include_router()` calls for:
- `orchestration_router` (from `.orchestration`)
- `legacy-orchestration_orchestration_router` (from `.legacy-orchestration_orchestration`)

Keep all other routers.

- [ ] **Step 3: Clean up bootstrap/services.py**

Open `python/helaicopter_api/bootstrap/services.py`. Remove:
- `oats_run_store` field and its construction in `build_services()`
- `legacy-orchestration_client` field and its construction
- Any imports from deleted modules

- [ ] **Step 4: Delete old orchestration test files**

```bash
rm -f tests/test_api_orchestration.py tests/test_api_legacy-orchestration_orchestration.py tests/test_orchestration_analytics.py
```

- [ ] **Step 5: Clean up server/config.py**

Open `python/helaicopter_api/server/config.py`. Remove any legacy orchestration-related settings fields (e.g. `legacy-orchestration_api_url`, `legacy-orchestration_work_pool`, etc.). Check `build_services()` in `bootstrap/services.py` — if it references `settings.legacy-orchestration` or similar, remove those references.

- [ ] **Step 6: Fix any remaining import errors**

```bash
cd /Users/tony/Code/helaicopter && uv run python -c "from helaicopter_api.server.main import create_app; print('ok')"
```

Expected: `ok`. If there are import errors, fix them by removing references to deleted modules. Check `server/lifespan.py`, `server/config.py`, and any `__init__.py` files.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "chore: remove old orchestration backend code"
```

**Note:** The codebase is intentionally broken during Tasks 1-4. Existing tests and some imports may fail until the new schema and code are in place (Tasks 5+). This is expected.

---

## Task 3: Delete Old Frontend Orchestration Code

**Files:**
- Delete: `src/components/orchestration/overnight-oats-panel.tsx`
- Delete: `src/components/orchestration/oats-pr-stack.tsx`
- Delete: `src/components/orchestration/legacy-orchestration-ui-embed.tsx`
- Delete: `src/components/orchestration/oats-view-model.ts`
- Delete: `src/components/orchestration/oats-view-model.test.ts`
- Delete: `src/components/orchestration/tabs.ts`
- Delete: `src/components/orchestration/tabs.test.ts`
- Delete: `src/lib/client/legacy-orchestration-normalize.test.ts`
- Modify: `src/lib/client/endpoints.ts` — remove orchestration endpoints
- Modify: `src/lib/client/normalize.ts` — remove orchestration normalizers
- Modify: `src/components/orchestration/orchestration-hub.tsx` — stub placeholder
- Modify: `src/app/orchestration/page.tsx` — stub placeholder

- [ ] **Step 1: Delete old frontend orchestration components**

```bash
rm -f src/components/orchestration/overnight-oats-panel.tsx \
      src/components/orchestration/oats-pr-stack.tsx \
      src/components/orchestration/legacy-orchestration-ui-embed.tsx \
      src/components/orchestration/oats-view-model.ts \
      src/components/orchestration/oats-view-model.test.ts \
      src/components/orchestration/tabs.ts \
      src/components/orchestration/tabs.test.ts \
      src/lib/client/legacy-orchestration-normalize.test.ts
```

- [ ] **Step 2: Remove orchestration endpoints from endpoints.ts**

Open `src/lib/client/endpoints.ts`. Remove all functions related to oats/legacy-orchestration orchestration (e.g. `listOatsRuns`, `getOatsRun`, `getlegacy orchestrationDeployments`, etc.). Keep non-orchestration endpoints.

- [ ] **Step 3: Remove orchestration normalizers from normalize.ts**

Open `src/lib/client/normalize.ts`. Remove orchestration-related normalizer functions. If `legacy-orchestration-normalize.ts` exists as a separate file, delete it.

- [ ] **Step 4: Stub the orchestration hub**

Replace `src/components/orchestration/orchestration-hub.tsx` with a minimal placeholder:

```tsx
"use client";

export function OrchestrationHub() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Orchestration</h1>
      <p className="text-muted-foreground">Orchestration UI is being rebuilt.</p>
    </div>
  );
}
```

- [ ] **Step 5: Update orchestration page if needed**

Ensure `src/app/orchestration/page.tsx` imports from the stubbed hub without errors.

- [ ] **Step 6: Verify frontend builds**

```bash
cd /Users/tony/Code/helaicopter && npm run build
```

Expected: Build succeeds. Fix any TypeScript errors from removed imports.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "chore: remove old frontend orchestration code"
```

---

## Task 4: Delete Old Docs and Examples

**Files:**
- Delete: `docs/oats-legacy-orchestration-cutover.md`
- Delete: `docs/legacy-orchestration-local-ops.md`
- Delete: `docs/orchestration/` (directory)
- Delete: `examples/legacy-orchestration_native_oats_orchestration_run.md`
- Delete: Old oats/legacy-orchestration design specs and plans in `docs/superpowers/specs/` and `docs/superpowers/plans/`

- [ ] **Step 1: Delete old orchestration docs**

```bash
rm -f docs/oats-legacy-orchestration-cutover.md docs/legacy-orchestration-local-ops.md
rm -rf docs/orchestration/
rm -f examples/legacy-orchestration_native_oats_orchestration_run.md
```

- [ ] **Step 2: Delete old oats/legacy-orchestration specs and plans**

Remove specs and plans that are oats/legacy-orchestration-specific. Keep the new claude-code-orchestrator spec. Read each file name and delete only those that reference oats, legacy-orchestration, or overnight:

```bash
rm -f docs/superpowers/specs/2026-03-18-legacy-orchestration-native-oats-orchestration-design.md \
      docs/superpowers/specs/2026-03-19-full-program-oats-legacy-orchestration-overnight-run-design.md \
      docs/superpowers/specs/2026-03-20-oats-stacked-pr-orchestration-design.md \
      docs/superpowers/specs/2026-03-19-data-modeling-design-agents-oats-design.md
```

```bash
rm -f docs/superpowers/plans/2026-03-18-legacy-orchestration-native-oats-orchestration.md \
      docs/superpowers/plans/2026-03-19-full-program-oats-legacy-orchestration-pipeline.md \
      docs/superpowers/plans/2026-03-20-oats-stacked-pr-orchestration.md \
      docs/superpowers/plans/2026-03-20-oats-authoritative-orchestration-tab.md \
      docs/superpowers/plans/2026-03-18-python-backend-type-system-oats-run.md
```

**Note:** Review each file before deleting — only delete oats/legacy-orchestration-specific ones. Keep plans unrelated to orchestration.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: remove old oats/legacy-orchestration docs and specs"
```

---

## Task 5: Alembic Migration — New Schema

**Files:**
- Create: `python/alembic/versions/20260320_orchestration_v2.py`
- Modify: `python/helaicopter_db/models/oltp.py`

- [ ] **Step 1: Add SQLAlchemy models to oltp.py**

Open `python/helaicopter_db/models/oltp.py`. Add four new model classes following existing conventions (`Mapped`, `mapped_column`, `__future__ annotations`):

```python
class OrchestrationRun(OltpBase):
    __tablename__ = "orchestration_run"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column()
    spec_path: Mapped[str] = mapped_column()
    plan_path: Mapped[str | None] = mapped_column(default=None)
    base_branch: Mapped[str] = mapped_column()
    concurrency: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(default="preparing")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    tasks: Mapped[list[OrchestrationTask]] = relationship(back_populates="run", cascade="all, delete-orphan")


class OrchestrationTask(OltpBase):
    __tablename__ = "orchestration_task"
    __table_args__ = (
        Index("idx_orchestration_task_status", "run_id", "status"),
    )

    run_id: Mapped[str] = mapped_column(ForeignKey("orchestration_run.id", ondelete="CASCADE"), primary_key=True)
    task_id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column()
    plan_steps: Mapped[str | None] = mapped_column(default=None)  # JSON array
    status: Mapped[str] = mapped_column(default="pending")
    agent: Mapped[str] = mapped_column()
    model: Mapped[str | None] = mapped_column(default=None)
    thinking: Mapped[str | None] = mapped_column(default=None)
    worktree_path: Mapped[str | None] = mapped_column(default=None)
    attack_plan_path: Mapped[str | None] = mapped_column(default=None)
    cli_args: Mapped[str | None] = mapped_column(default=None)
    acceptance_criteria: Mapped[str | None] = mapped_column(default=None)  # JSON array
    review_required: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    run: Mapped[OrchestrationRun] = relationship(back_populates="tasks")
    sessions: Mapped[list[OrchestrationSession]] = relationship(back_populates="task", cascade="all, delete-orphan")


class OrchestrationSession(OltpBase):
    __tablename__ = "orchestration_session"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column()
    task_id: Mapped[str] = mapped_column()
    conversation_id: Mapped[str | None] = mapped_column(default=None)
    self_reported_id: Mapped[str | None] = mapped_column(default=None)
    session_name: Mapped[str | None] = mapped_column(default=None)
    pid: Mapped[int | None] = mapped_column(default=None)
    cli_command: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    exit_code: Mapped[int | None] = mapped_column(default=None)
    error_text: Mapped[str | None] = mapped_column(default=None)

    task: Mapped[OrchestrationTask] = relationship(back_populates="sessions")

    __table_args__ = (
        ForeignKeyConstraint(["run_id", "task_id"], ["orchestration_task.run_id", "orchestration_task.task_id"], ondelete="CASCADE"),
        Index("idx_orchestration_session_task", "run_id", "task_id"),
        Index("idx_orchestration_session_status", "status"),
    )


class OrchestrationDependency(OltpBase):
    __tablename__ = "orchestration_dependency"

    run_id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(primary_key=True)
    depends_on_task_id: Mapped[str] = mapped_column(primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(["run_id", "task_id"], ["orchestration_task.run_id", "orchestration_task.task_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["run_id", "depends_on_task_id"], ["orchestration_task.run_id", "orchestration_task.task_id"], ondelete="CASCADE"),
    )
```

- [ ] **Step 2: Generate the Alembic migration**

```bash
cd /Users/tony/Code/helaicopter && uv run alembic -x target=oltp revision --autogenerate -m "orchestration v2: replace oats/legacy-orchestration with skill-driven schema"
```

- [ ] **Step 3: Review and edit the generated migration**

Open the generated file. Verify it:
- Creates the four new tables with correct columns, PKs, FKs, indexes
- Drops old tables: `fact_orchestration_run`, `fact_orchestration_task_attempt` (check actual table names)
- Has a working `downgrade()` that reverses the changes

- [ ] **Step 4: Run the migration**

```bash
cd /Users/tony/Code/helaicopter && uv run alembic -x target=oltp upgrade head
```

Expected: Migration applies cleanly.

- [ ] **Step 5: Verify tables exist**

```bash
cd /Users/tony/Code/helaicopter && uv run python -c "
from sqlalchemy import create_engine, inspect
from helaicopter_db.settings import get_oltp_url
engine = create_engine(get_oltp_url())
inspector = inspect(engine)
tables = inspector.get_table_names()
for t in ['orchestration_run', 'orchestration_task', 'orchestration_session', 'orchestration_dependency']:
    assert t in tables, f'Missing table: {t}'
print('All tables present')
"
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add orchestration v2 schema (skill-driven orchestrator)"
```

---

## Task 6: DB Helper Module

**Files:**
- Create: `python/helaicopter_db/orchestration.py`
- Create: `tests/test_orchestration_db.py`

- [ ] **Step 1: Write failing tests for run CRUD**

Create `tests/test_orchestration_db.py`:

```python
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from helaicopter_db.models.oltp import OltpBase
from helaicopter_db.orchestration import OrchestrationDB


@pytest.fixture()
def db(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    OltpBase.metadata.create_all(engine)
    return OrchestrationDB(engine)


def test_create_and_get_run(db):
    db.create_run(id="run-1", title="Test Run", spec_path="/spec.md", base_branch="main", concurrency=2)
    run = db.get_run("run-1")
    assert run is not None
    assert run["title"] == "Test Run"
    assert run["status"] == "preparing"
    assert run["concurrency"] == 2


def test_update_run_status(db):
    db.create_run(id="run-1", title="Test", spec_path="/spec.md", base_branch="main")
    db.update_run("run-1", status="running")
    run = db.get_run("run-1")
    assert run["status"] == "running"


def test_list_runs(db):
    db.create_run(id="run-1", title="First", spec_path="/a.md", base_branch="main")
    db.create_run(id="run-2", title="Second", spec_path="/b.md", base_branch="main")
    runs = db.list_runs()
    assert len(runs) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/tony/Code/helaicopter && uv run pytest tests/test_orchestration_db.py -v
```

Expected: FAIL (module `helaicopter_db.orchestration` does not exist)

- [ ] **Step 3: Implement OrchestrationDB class — run operations**

Create `python/helaicopter_db/orchestration.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from helaicopter_db.models.oltp import (
    OrchestrationDependency,
    OrchestrationRun,
    OrchestrationSession,
    OrchestrationTask,
)


class OrchestrationDB:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # --- Run operations ---

    def create_run(
        self,
        *,
        id: str,
        title: str,
        spec_path: str,
        base_branch: str,
        plan_path: str | None = None,
        concurrency: int = 1,
    ) -> None:
        with Session(self._engine) as session:
            session.add(OrchestrationRun(
                id=id, title=title, spec_path=spec_path, plan_path=plan_path,
                base_branch=base_branch, concurrency=concurrency,
                status="preparing", created_at=datetime.now(UTC),
            ))
            session.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with Session(self._engine) as session:
            row = session.get(OrchestrationRun, run_id)
            if row is None:
                return None
            return {c.name: getattr(row, c.name) for c in row.__table__.columns}

    def list_runs(self) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            rows = session.execute(select(OrchestrationRun).order_by(OrchestrationRun.created_at.desc())).scalars().all()
            return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]

    def update_run(self, run_id: str, **kwargs: Any) -> None:
        with Session(self._engine) as session:
            if "status" in kwargs and kwargs["status"] in ("running",):
                kwargs["started_at"] = datetime.now(UTC)
            if "status" in kwargs and kwargs["status"] in ("completed", "failed"):
                kwargs["finished_at"] = datetime.now(UTC)
            session.execute(update(OrchestrationRun).where(OrchestrationRun.id == run_id).values(**kwargs))
            session.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/tony/Code/helaicopter && uv run pytest tests/test_orchestration_db.py -v -k "run"
```

Expected: 3 tests PASS

- [ ] **Step 5: Write failing tests for task + dependency operations**

Add to `tests/test_orchestration_db.py`:

```python
def test_create_and_get_task(db):
    db.create_run(id="run-1", title="Test", spec_path="/spec.md", base_branch="main")
    db.create_task(run_id="run-1", task_id="task-1", title="First task", agent="claude", model="sonnet")
    task = db.get_task("run-1", "task-1")
    assert task is not None
    assert task["title"] == "First task"
    assert task["status"] == "pending"


def test_add_dependency_and_get_ready_tasks(db):
    db.create_run(id="run-1", title="Test", spec_path="/spec.md", base_branch="main")
    db.create_task(run_id="run-1", task_id="task-1", title="First", agent="claude")
    db.create_task(run_id="run-1", task_id="task-2", title="Second", agent="claude")
    db.add_dependency(run_id="run-1", task_id="task-2", depends_on="task-1")

    ready = db.get_ready_tasks("run-1")
    assert len(ready) == 1
    assert ready[0]["task_id"] == "task-1"

    # Complete task-1, now task-2 should be ready
    db.update_task("run-1", "task-1", status="completed")
    ready = db.get_ready_tasks("run-1")
    assert len(ready) == 1
    assert ready[0]["task_id"] == "task-2"


def test_get_tasks_for_run(db):
    db.create_run(id="run-1", title="Test", spec_path="/spec.md", base_branch="main")
    db.create_task(run_id="run-1", task_id="task-1", title="First", agent="claude")
    db.create_task(run_id="run-1", task_id="task-2", title="Second", agent="codex")
    tasks = db.get_tasks("run-1")
    assert len(tasks) == 2
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
cd /Users/tony/Code/helaicopter && uv run pytest tests/test_orchestration_db.py -v -k "task or dependency"
```

Expected: FAIL

- [ ] **Step 7: Implement task + dependency operations**

Add to `OrchestrationDB` in `python/helaicopter_db/orchestration.py`:

```python
    # --- Task operations ---

    def create_task(
        self,
        *,
        run_id: str,
        task_id: str,
        title: str,
        agent: str,
        model: str | None = None,
        thinking: str | None = None,
        plan_steps: str | None = None,
        cli_args: str | None = None,
        acceptance_criteria: str | None = None,
        review_required: bool = False,
    ) -> None:
        with Session(self._engine) as session:
            session.add(OrchestrationTask(
                run_id=run_id, task_id=task_id, title=title, agent=agent,
                model=model, thinking=thinking, plan_steps=plan_steps,
                cli_args=cli_args, acceptance_criteria=acceptance_criteria,
                review_required=review_required, status="pending",
                created_at=datetime.now(UTC),
            ))
            session.commit()

    def get_task(self, run_id: str, task_id: str) -> dict[str, Any] | None:
        with Session(self._engine) as session:
            row = session.get(OrchestrationTask, (run_id, task_id))
            if row is None:
                return None
            return {c.name: getattr(row, c.name) for c in row.__table__.columns}

    def get_tasks(self, run_id: str) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            rows = session.execute(
                select(OrchestrationTask).where(OrchestrationTask.run_id == run_id)
            ).scalars().all()
            return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]

    def update_task(self, run_id: str, task_id: str, **kwargs: Any) -> None:
        with Session(self._engine) as session:
            if "status" in kwargs and kwargs["status"] == "running":
                kwargs.setdefault("started_at", datetime.now(UTC))
            if "status" in kwargs and kwargs["status"] in ("completed", "failed", "review"):
                kwargs.setdefault("finished_at", datetime.now(UTC))
            session.execute(
                update(OrchestrationTask)
                .where(OrchestrationTask.run_id == run_id, OrchestrationTask.task_id == task_id)
                .values(**kwargs)
            )
            session.commit()

    # --- Dependency operations ---

    def add_dependency(self, *, run_id: str, task_id: str, depends_on: str) -> None:
        with Session(self._engine) as session:
            session.add(OrchestrationDependency(
                run_id=run_id, task_id=task_id, depends_on_task_id=depends_on,
            ))
            session.commit()

    def get_ready_tasks(self, run_id: str) -> list[dict[str, Any]]:
        """Return tasks that are pending and have all dependencies completed."""
        with Session(self._engine) as session:
            # Get all pending tasks
            pending = session.execute(
                select(OrchestrationTask)
                .where(OrchestrationTask.run_id == run_id, OrchestrationTask.status == "pending")
            ).scalars().all()

            ready = []
            for task in pending:
                # Check if all dependencies are completed
                deps = session.execute(
                    select(OrchestrationDependency)
                    .where(
                        OrchestrationDependency.run_id == run_id,
                        OrchestrationDependency.task_id == task.task_id,
                    )
                ).scalars().all()

                all_met = True
                for dep in deps:
                    dep_task = session.get(OrchestrationTask, (run_id, dep.depends_on_task_id))
                    if dep_task is None or dep_task.status != "completed":
                        all_met = False
                        break

                if all_met:
                    ready.append({c.name: getattr(task, c.name) for c in task.__table__.columns})

            return ready
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd /Users/tony/Code/helaicopter && uv run pytest tests/test_orchestration_db.py -v -k "task or dependency"
```

Expected: 3 tests PASS

- [ ] **Step 9: Write failing tests for session operations**

Add to `tests/test_orchestration_db.py`:

```python
def test_create_and_get_sessions(db):
    db.create_run(id="run-1", title="Test", spec_path="/spec.md", base_branch="main")
    db.create_task(run_id="run-1", task_id="task-1", title="First", agent="claude")
    db.create_session(run_id="run-1", task_id="task-1", pid=12345, cli_command="claude -p test")
    sessions = db.get_sessions("run-1", "task-1")
    assert len(sessions) == 1
    assert sessions[0]["pid"] == 12345
    assert sessions[0]["status"] == "running"


def test_register_and_complete_session(db):
    db.create_run(id="run-1", title="Test", spec_path="/spec.md", base_branch="main")
    db.create_task(run_id="run-1", task_id="task-1", title="First", agent="claude")
    db.create_session(run_id="run-1", task_id="task-1", pid=12345, cli_command="claude -p test")
    db.register_session(run_id="run-1", task_id="task-1", conversation_id="conv-abc")
    db.complete_session(run_id="run-1", task_id="task-1", status="completed")
    sessions = db.get_sessions("run-1", "task-1")
    assert sessions[0]["conversation_id"] == "conv-abc"
    assert sessions[0]["status"] == "completed"


def test_get_running_sessions(db):
    db.create_run(id="run-1", title="Test", spec_path="/spec.md", base_branch="main")
    db.create_task(run_id="run-1", task_id="task-1", title="First", agent="claude")
    db.create_task(run_id="run-1", task_id="task-2", title="Second", agent="claude")
    db.create_session(run_id="run-1", task_id="task-1", pid=111, cli_command="c1")
    db.create_session(run_id="run-1", task_id="task-2", pid=222, cli_command="c2")
    db.complete_session(run_id="run-1", task_id="task-1", status="completed")
    running = db.get_running_sessions("run-1")
    assert len(running) == 1
    assert running[0]["task_id"] == "task-2"
```

- [ ] **Step 10: Run tests to verify they fail**

```bash
cd /Users/tony/Code/helaicopter && uv run pytest tests/test_orchestration_db.py -v -k "session"
```

Expected: FAIL

- [ ] **Step 11: Implement session operations**

Add to `OrchestrationDB`:

```python
    # --- Session operations ---

    def create_session(
        self,
        *,
        run_id: str,
        task_id: str,
        pid: int | None = None,
        cli_command: str | None = None,
        session_name: str | None = None,
    ) -> int:
        with Session(self._engine) as session:
            row = OrchestrationSession(
                run_id=run_id, task_id=task_id, pid=pid, cli_command=cli_command,
                session_name=session_name, status="running",
                started_at=datetime.now(UTC),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id

    def register_session(self, *, run_id: str, task_id: str, conversation_id: str) -> None:
        """Register conversation ID for the most recent session of a task."""
        with Session(self._engine) as session:
            row = session.execute(
                select(OrchestrationSession)
                .where(
                    OrchestrationSession.run_id == run_id,
                    OrchestrationSession.task_id == task_id,
                    OrchestrationSession.status == "running",
                )
                .order_by(OrchestrationSession.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row:
                row.conversation_id = conversation_id
                session.commit()

    def complete_session(
        self, *, run_id: str, task_id: str, status: str,
        exit_code: int | None = None, error_text: str | None = None,
    ) -> None:
        """Complete the most recent running session of a task."""
        with Session(self._engine) as session:
            row = session.execute(
                select(OrchestrationSession)
                .where(
                    OrchestrationSession.run_id == run_id,
                    OrchestrationSession.task_id == task_id,
                    OrchestrationSession.status == "running",
                )
                .order_by(OrchestrationSession.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row:
                row.status = status
                row.finished_at = datetime.now(UTC)
                row.exit_code = exit_code
                row.error_text = error_text
                session.commit()

    def get_sessions(self, run_id: str, task_id: str) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            rows = session.execute(
                select(OrchestrationSession)
                .where(OrchestrationSession.run_id == run_id, OrchestrationSession.task_id == task_id)
                .order_by(OrchestrationSession.id)
            ).scalars().all()
            return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]

    def get_running_sessions(self, run_id: str) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            rows = session.execute(
                select(OrchestrationSession)
                .where(OrchestrationSession.run_id == run_id, OrchestrationSession.status == "running")
            ).scalars().all()
            return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]

    def get_dependencies(self, run_id: str) -> list[dict[str, str]]:
        with Session(self._engine) as session:
            rows = session.execute(
                select(OrchestrationDependency)
                .where(OrchestrationDependency.run_id == run_id)
            ).scalars().all()
            return [{"task_id": r.task_id, "depends_on_task_id": r.depends_on_task_id} for r in rows]
```

- [ ] **Step 12: Run all tests to verify they pass**

```bash
cd /Users/tony/Code/helaicopter && uv run pytest tests/test_orchestration_db.py -v
```

Expected: All 9 tests PASS

- [ ] **Step 13: Add CLI `__main__` entrypoint**

Add to the bottom of `python/helaicopter_db/orchestration.py`:

```python
def _cli() -> None:
    """CLI entrypoint for `python -m helaicopter_db.orchestration`."""
    import argparse
    import json

    from helaicopter_db.settings import get_oltp_url
    from sqlalchemy import create_engine

    parser = argparse.ArgumentParser(prog="helaicopter_db.orchestration")
    sub = parser.add_subparsers(dest="command", required=True)

    # create-run
    p = sub.add_parser("create-run")
    p.add_argument("--id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--spec-path", required=True)
    p.add_argument("--plan-path")
    p.add_argument("--base-branch", required=True)
    p.add_argument("--concurrency", type=int, default=1)

    # update-run
    p = sub.add_parser("update-run")
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True)

    # create-task
    p = sub.add_parser("create-task")
    p.add_argument("--run-id", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--model")
    p.add_argument("--thinking")
    p.add_argument("--review-required", action="store_true")

    # update-task
    p = sub.add_parser("update-task")
    p.add_argument("--run-id", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--status")
    p.add_argument("--worktree-path")
    p.add_argument("--attack-plan-path")

    # add-dependency
    p = sub.add_parser("add-dependency")
    p.add_argument("--run-id", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--depends-on", required=True)

    # create-session
    p = sub.add_parser("create-session")
    p.add_argument("--run-id", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--pid", type=int)
    p.add_argument("--cli-command")

    # register-session
    p = sub.add_parser("register-session")
    p.add_argument("--run-id", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--conversation-id", required=True)

    # complete-session
    p = sub.add_parser("complete-session")
    p.add_argument("--run-id", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--error")

    # get-running-sessions
    p = sub.add_parser("get-running-sessions")
    p.add_argument("--run-id", required=True)

    # get-ready-tasks
    p = sub.add_parser("get-ready-tasks")
    p.add_argument("--run-id", required=True)

    args = parser.parse_args()
    engine = create_engine(get_oltp_url())
    db = OrchestrationDB(engine)

    match args.command:
        case "create-run":
            db.create_run(id=args.id, title=args.title, spec_path=args.spec_path,
                          plan_path=args.plan_path, base_branch=args.base_branch,
                          concurrency=args.concurrency)
        case "update-run":
            db.update_run(args.id, status=args.status)
        case "create-task":
            db.create_task(run_id=args.run_id, task_id=args.task_id, title=args.title,
                           agent=args.agent, model=args.model, thinking=args.thinking,
                           review_required=args.review_required)
        case "update-task":
            kwargs = {k: v for k, v in {"status": args.status, "worktree_path": args.worktree_path,
                      "attack_plan_path": args.attack_plan_path}.items() if v is not None}
            db.update_task(args.run_id, args.task_id, **kwargs)
        case "add-dependency":
            db.add_dependency(run_id=args.run_id, task_id=args.task_id, depends_on=args.depends_on)
        case "create-session":
            sid = db.create_session(run_id=args.run_id, task_id=args.task_id,
                                    pid=args.pid, cli_command=args.cli_command)
            print(json.dumps({"session_id": sid}))
        case "register-session":
            db.register_session(run_id=args.run_id, task_id=args.task_id,
                                conversation_id=args.conversation_id)
        case "complete-session":
            db.complete_session(run_id=args.run_id, task_id=args.task_id,
                                status=args.status, error_text=args.error)
        case "get-running-sessions":
            print(json.dumps(db.get_running_sessions(args.run_id), default=str))
        case "get-ready-tasks":
            print(json.dumps(db.get_ready_tasks(args.run_id), default=str))


if __name__ == "__main__":
    _cli()
```

- [ ] **Step 14: Test CLI entrypoint**

```bash
cd /Users/tony/Code/helaicopter && uv run python -m helaicopter_db.orchestration --help
```

Expected: Shows help text with all subcommands.

- [ ] **Step 15: Commit**

```bash
git add -A && git commit -m "feat: add orchestration DB helper module with CLI"
```

---

## Task 7: Backend API — Schemas

**Files:**
- Create: `python/helaicopter_api/schema/orchestration_v2.py`

- [ ] **Step 1: Write response schemas**

Create `python/helaicopter_api/schema/orchestration_v2.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str | None
    self_reported_id: str | None
    session_name: str | None
    pid: int | None
    cli_command: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    exit_code: int | None
    error_text: str | None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    task_id: str
    title: str
    plan_steps: str | None
    status: str
    agent: str
    model: str | None
    thinking: str | None
    worktree_path: str | None
    attack_plan_path: str | None
    review_required: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    sessions: list[SessionResponse] = []


class RunSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: str
    concurrency: int
    task_count: int
    completed_count: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    spec_path: str
    plan_path: str | None
    base_branch: str
    concurrency: int
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    tasks: list[TaskResponse]


class TaskDetailResponse(TaskResponse):
    attack_plan_content: str | None = None


class DagNode(BaseModel):
    task_id: str
    title: str
    status: str
    agent: str


class DagEdge(BaseModel):
    from_task: str
    to_task: str


class DagResponse(BaseModel):
    nodes: list[DagNode]
    edges: list[DagEdge]
```

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "feat: add orchestration v2 response schemas"
```

---

## Task 8: Backend API — Application Layer + Router

**Files:**
- Create: `python/helaicopter_api/application/orchestration_v2.py`
- Create: `python/helaicopter_api/router/orchestration_v2.py`
- Modify: `python/helaicopter_api/router/router.py`
- Create: `tests/test_orchestration_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_orchestration_api.py`. Note: adapt the fixture to match the existing test harness pattern. Check `tests/test_api_smoke.py` or `tests/test_api_evaluation_prompts.py` for how the test client is constructed in this project. The pattern below shows the intent:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from helaicopter_db.models.oltp import OltpBase
from helaicopter_db.orchestration import OrchestrationDB
from helaicopter_api.server.main import create_app


@pytest.fixture()
def seeded_client(tmp_path):
    """Create a test app with seeded orchestration data."""
    # Create a temporary SQLite DB with schema
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    OltpBase.metadata.create_all(engine)

    # Seed data
    db = OrchestrationDB(engine)
    db.create_run(id="run-1", title="Test Run", spec_path="/spec.md", base_branch="main", concurrency=2)
    db.create_task(run_id="run-1", task_id="task-1", title="Task One", agent="claude", model="sonnet")
    db.create_task(run_id="run-1", task_id="task-2", title="Task Two", agent="codex")
    db.add_dependency(run_id="run-1", task_id="task-2", depends_on="task-1")

    # Create app and inject engine — adapt this to match the project's test pattern.
    # Check existing test files for how BackendServices is constructed in tests.
    app = create_app()
    app.state.services.sqlite_engine = engine
    with TestClient(app) as client:
        yield client


def test_list_runs(seeded_client):
    resp = seeded_client.get("/orchestration/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "run-1"
    assert data[0]["task_count"] == 2


def test_get_run_detail(seeded_client):
    resp = seeded_client.get("/orchestration/runs/run-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "run-1"
    assert len(data["tasks"]) == 2


def test_get_dag(seeded_client):
    resp = seeded_client.get("/orchestration/runs/run-1/dag")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert data["edges"][0]["from_task"] == "task-1"
    assert data["edges"][0]["to_task"] == "task-2"
```

- [ ] **Step 2: Implement application layer**

Create `python/helaicopter_api/application/orchestration_v2.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_db.orchestration import OrchestrationDB


def _db(services: BackendServices) -> OrchestrationDB:
    return OrchestrationDB(services.sqlite_engine)


def list_runs(services: BackendServices) -> list[dict[str, Any]]:
    db = _db(services)
    runs = db.list_runs()
    for run in runs:
        tasks = db.get_tasks(run["id"])
        run["task_count"] = len(tasks)
        run["completed_count"] = sum(1 for t in tasks if t["status"] == "completed")
    return runs


def get_run_detail(services: BackendServices, run_id: str) -> dict[str, Any] | None:
    db = _db(services)
    run = db.get_run(run_id)
    if run is None:
        return None
    tasks = db.get_tasks(run_id)
    for task in tasks:
        task["sessions"] = db.get_sessions(run_id, task["task_id"])
    run["tasks"] = tasks
    return run


def get_task_detail(services: BackendServices, run_id: str, task_id: str) -> dict[str, Any] | None:
    db = _db(services)
    task = db.get_task(run_id, task_id)
    if task is None:
        return None
    task["sessions"] = db.get_sessions(run_id, task_id)
    # Read attack plan content if path exists
    if task.get("attack_plan_path"):
        path = Path(task["attack_plan_path"])
        task["attack_plan_content"] = path.read_text() if path.exists() else None
    else:
        task["attack_plan_content"] = None
    return task


def get_dag(services: BackendServices, run_id: str) -> dict[str, Any] | None:
    db = _db(services)
    run = db.get_run(run_id)
    if run is None:
        return None
    tasks = db.get_tasks(run_id)
    nodes = [{"task_id": t["task_id"], "title": t["title"], "status": t["status"], "agent": t["agent"]} for t in tasks]
    deps = db.get_dependencies(run_id)
    edges = [{"from_task": d["depends_on_task_id"], "to_task": d["task_id"]} for d in deps]
    return {"nodes": nodes, "edges": edges}


def approve_task(services: BackendServices, run_id: str, task_id: str) -> bool:
    db = _db(services)
    task = db.get_task(run_id, task_id)
    if task is None or task["status"] != "review":
        return False
    db.update_task(run_id, task_id, status="completed")
    return True


def retry_task(services: BackendServices, run_id: str, task_id: str) -> bool:
    db = _db(services)
    task = db.get_task(run_id, task_id)
    if task is None or task["status"] != "failed":
        return False
    db.update_task(run_id, task_id, status="pending")
    return True
```

- [ ] **Step 3: Implement router**

Create `python/helaicopter_api/router/orchestration_v2.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from helaicopter_api.application import orchestration_v2 as app
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.orchestration_v2 import (
    DagResponse,
    RunDetailResponse,
    RunSummaryResponse,
    TaskDetailResponse,
)
from helaicopter_api.server.dependencies import get_services

orchestration_v2_router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@orchestration_v2_router.get("/runs", response_model=list[RunSummaryResponse])
async def list_runs(services: BackendServices = Depends(get_services)):
    return app.list_runs(services)


@orchestration_v2_router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(run_id: str, services: BackendServices = Depends(get_services)):
    result = app.get_run_detail(services, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@orchestration_v2_router.get("/runs/{run_id}/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(run_id: str, task_id: str, services: BackendServices = Depends(get_services)):
    result = app.get_task_detail(services, run_id, task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@orchestration_v2_router.get("/runs/{run_id}/dag", response_model=DagResponse)
async def get_dag(run_id: str, services: BackendServices = Depends(get_services)):
    result = app.get_dag(services, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@orchestration_v2_router.post("/runs/{run_id}/tasks/{task_id}/approve")
async def approve_task(run_id: str, task_id: str, services: BackendServices = Depends(get_services)):
    if not app.approve_task(services, run_id, task_id):
        raise HTTPException(status_code=400, detail="Task not in review status")
    return {"status": "approved"}


@orchestration_v2_router.post("/runs/{run_id}/tasks/{task_id}/retry")
async def retry_task(run_id: str, task_id: str, services: BackendServices = Depends(get_services)):
    if not app.retry_task(services, run_id, task_id):
        raise HTTPException(status_code=400, detail="Task not in failed status")
    return {"status": "retrying"}
```

- [ ] **Step 4: Register router in router.py**

Open `python/helaicopter_api/router/router.py`. Add:

```python
from .orchestration_v2 import orchestration_v2_router
root_router.include_router(orchestration_v2_router)
```

- [ ] **Step 5: Run API tests**

```bash
cd /Users/tony/Code/helaicopter && uv run pytest tests/test_orchestration_api.py -v
```

Expected: All tests PASS. If the test fixture setup doesn't match the existing test harness pattern, adapt accordingly.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add orchestration v2 API routes (6 endpoints)"
```

---

## Task 9: Frontend Client Layer

**Files:**
- Create: `src/lib/client/orchestration.ts`
- Modify: `src/lib/client/endpoints.ts`

- [ ] **Step 1: Add endpoint builders**

Open `src/lib/client/endpoints.ts`. Add the new orchestration endpoints following existing patterns:

```typescript
export function orchestrationRuns() { return api("/orchestration/runs"); }
export function orchestrationRun(runId: string) { return api(`/orchestration/runs/${enc(runId)}`); }
export function orchestrationTask(runId: string, taskId: string) { return api(`/orchestration/runs/${enc(runId)}/tasks/${enc(taskId)}`); }
export function orchestrationDag(runId: string) { return api(`/orchestration/runs/${enc(runId)}/dag`); }
export function orchestrationApprove(runId: string, taskId: string) { return api(`/orchestration/runs/${enc(runId)}/tasks/${enc(taskId)}/approve`); }
export function orchestrationRetry(runId: string, taskId: string) { return api(`/orchestration/runs/${enc(runId)}/tasks/${enc(taskId)}/retry`); }
```

- [ ] **Step 2: Create orchestration client module with types and hooks**

Create `src/lib/client/orchestration.ts`:

```typescript
import useSWR from "swr";
import { orchestrationRuns, orchestrationRun, orchestrationDag } from "./endpoints";

// Types matching backend schemas
export interface SessionInfo {
  id: number;
  conversation_id: string | null;
  self_reported_id: string | null;
  session_name: string | null;
  pid: number | null;
  cli_command: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  exit_code: number | null;
  error_text: string | null;
}

export interface TaskInfo {
  run_id: string;
  task_id: string;
  title: string;
  plan_steps: string | null;
  status: string;
  agent: string;
  model: string | null;
  thinking: string | null;
  worktree_path: string | null;
  attack_plan_path: string | null;
  review_required: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  sessions: SessionInfo[];
}

export interface RunSummary {
  id: string;
  title: string;
  status: string;
  concurrency: number;
  task_count: number;
  completed_count: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RunDetail {
  id: string;
  title: string;
  spec_path: string;
  plan_path: string | null;
  base_branch: string;
  concurrency: number;
  status: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  tasks: TaskInfo[];
}

export interface DagNode {
  task_id: string;
  title: string;
  status: string;
  agent: string;
}

export interface DagEdge {
  from_task: string;
  to_task: string;
}

export interface DagData {
  nodes: DagNode[];
  edges: DagEdge[];
}

const fetcher = (url: string) => fetch(url).then(r => r.json());

export function useOrchestrationRuns() {
  return useSWR<RunSummary[]>(orchestrationRuns(), fetcher, { refreshInterval: 5000 });
}

export function useOrchestrationRun(runId: string) {
  return useSWR<RunDetail>(orchestrationRun(runId), fetcher, { refreshInterval: 3000 });
}

export function useOrchestrationDag(runId: string) {
  return useSWR<DagData>(orchestrationDag(runId), fetcher, { refreshInterval: 3000 });
}
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: add orchestration v2 frontend client layer"
```

---

## Task 10: Frontend — Orchestration Components

**Files:**
- Create: `src/components/orchestration/run-list.tsx`
- Create: `src/components/orchestration/run-detail.tsx`
- Create: `src/components/orchestration/task-detail.tsx`
- Create: `src/components/orchestration/dag-view.tsx`
- Modify: `src/components/orchestration/orchestration-hub.tsx`
- Modify: `src/app/orchestration/page.tsx`

- [ ] **Step 1: Create RunList component**

Create `src/components/orchestration/run-list.tsx`. Displays a table of runs with status badges and task progress. Uses `useOrchestrationRuns()` hook. Each row clicks through to run detail.

Key elements: status badge (colored by status), progress indicator (completed/total tasks), timestamps, title.

- [ ] **Step 2: Create DagView component**

Create `src/components/orchestration/dag-view.tsx`. Renders the task dependency graph. Uses `useOrchestrationDag()` hook. Nodes colored by status. Edges show dependencies. Can use a simple CSS-based layout or a library like `dagre` / `reactflow` if available.

For a minimal first version, render a vertical list of nodes with connecting lines. Can be enhanced later.

- [ ] **Step 3: Create TaskDetail component**

Create `src/components/orchestration/task-detail.tsx`. Expandable card showing:
- Task metadata (agent, model, thinking, status)
- Attack plan content (rendered markdown)
- Session history table (conversation ID as link, PID, status, timestamps)
- Action buttons: Approve (if `status === "review"`), Retry (if `status === "failed"`)

Approve/Retry buttons POST to the respective endpoints.

- [ ] **Step 4: Create RunDetail component**

Create `src/components/orchestration/run-detail.tsx`. Two-panel layout:
- Left: `DagView` component
- Right: Task list using `TaskDetail` components

Uses `useOrchestrationRun()` hook. Includes back navigation to run list.

- [ ] **Step 5: Rebuild orchestration hub**

Update `src/components/orchestration/orchestration-hub.tsx`:

```tsx
"use client";

import { useState } from "react";
import { RunList } from "./run-list";
import { RunDetail } from "./run-detail";

export function OrchestrationHub() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  if (selectedRunId) {
    return <RunDetail runId={selectedRunId} onBack={() => setSelectedRunId(null)} />;
  }

  return <RunList onSelectRun={setSelectedRunId} />;
}
```

- [ ] **Step 6: Update orchestration page**

Ensure `src/app/orchestration/page.tsx` renders `OrchestrationHub` correctly.

- [ ] **Step 7: Verify frontend builds**

```bash
cd /Users/tony/Code/helaicopter && npm run build
```

Expected: Build succeeds.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: rebuild orchestration frontend (run list, DAG, task detail)"
```

---

## Task 11: Example Run Spec

**Files:**
- Create: `examples/sample_orchestration_run.md`

- [ ] **Step 1: Write example run spec**

Create `examples/sample_orchestration_run.md`:

```markdown
# Run: Example Feature Implementation

## Config
concurrency: 2
base_branch: main
plan: docs/superpowers/plans/2026-03-20-example-plan.md

## Defaults
agent: claude
model: sonnet
thinking: high
cli_args: --max-turns 50

## Tasks

### task-1: Set up data models
plan_steps: [1]
context:
  - python/helaicopter_db/models/oltp.py

### task-2: Implement API endpoints
plan_steps: [2, 3]
depends_on: [task-1]
context:
  - python/helaicopter_api/router/
  - python/helaicopter_api/schema/

### task-3: Add frontend components
plan_steps: [4]
depends_on: [task-2]
model: opus
thinking: extended
context:
  - src/components/
review: true

### task-4: Write integration tests
plan_steps: [5]
depends_on: [task-1]
agent: codex
acceptance_criteria: uv run pytest tests/ -v
```

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "docs: add example run spec for new orchestration format"
```

---

## Task 12: Orchestrator Skill (SKILL.md)

**Files:**
- Create: Orchestrator skill at the agent-harness location (or document the skill content for later placement)

This task produces the `SKILL.md` file for `superpowers:orchestrate-run`. Since the skill lives at `/Users/tony/Code/agent-harness/skills/orchestrate-run/SKILL.md`, and that repo may not exist yet, write the skill content to `docs/orchestrate-run-skill.md` in this repo as a staging location.

- [ ] **Step 1: Write the orchestrator skill**

Create `docs/orchestrate-run-skill.md` containing the full SKILL.md content. The skill must cover all phases:
- PARSE: Read run spec, extract config/tasks/deps, validate DAG, write to SQLite
- EXPAND: For each task, read plan steps + context, explore codebase, write attack-plan.md
- REVIEW: Present attack plans to human, accept edits
- DISPATCH: Build CLI commands, spawn background processes, capture PIDs + session IDs
- MONITOR: `/loop` polling, process liveness checks, cascade dispatch, review gates
- RETRY: Resume vs fresh start strategies
- RECOVERY: Resume a run by ID

Include the exact CLI commands for both Claude Code and Codex dispatch. Include the DB helper commands for SQLite writes.

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "docs: add orchestrate-run skill draft for agent-harness"
```

---

## Task 13: Final Verification

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/tony/Code/helaicopter && uv run pytest tests/ -v
```

Expected: All tests pass. Fix any failures.

- [ ] **Step 2: Run frontend build**

```bash
cd /Users/tony/Code/helaicopter && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Run linter**

```bash
cd /Users/tony/Code/helaicopter && uv run ruff check python/
```

Expected: No errors.

- [ ] **Step 4: Start the app and verify orchestration page loads**

```bash
cd /Users/tony/Code/helaicopter && npm run dev &
# Visit http://localhost:3000/orchestration
```

Expected: Orchestration page renders the (empty) run list without errors.

- [ ] **Step 5: Test DB helper CLI end-to-end**

```bash
cd /Users/tony/Code/helaicopter && uv run python -m helaicopter_db.orchestration create-run --id test-1 --title "E2E Test" --spec-path /tmp/spec.md --base-branch main
uv run python -m helaicopter_db.orchestration create-task --run-id test-1 --task-id task-1 --title "Test Task" --agent claude
uv run python -m helaicopter_db.orchestration get-ready-tasks --run-id test-1
```

Expected: Returns JSON with task-1 as ready.

- [ ] **Step 6: Verify API returns seeded data**

```bash
curl http://localhost:3000/api/orchestration/runs | python -m json.tool
```

Expected: Returns the test run.

- [ ] **Step 7: Final commit if any fixes were needed**

```bash
git add -A && git commit -m "fix: final verification fixes for orchestration v2"
```
