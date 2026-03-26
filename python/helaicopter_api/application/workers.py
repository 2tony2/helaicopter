"""Worker registry CRUD operations."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from helaicopter_api.application.resolver import ResolverLoop, TaskResult
from helaicopter_api.application.worker_state import (
    complete_worker_task,
    drain_worker_state,
    heartbeat_worker_state,
    mark_worker_dispatched,
)
from helaicopter_api.schema.workers import (
    WorkerCapabilitiesResponse,
    WorkerDetailResponse,
    WorkerHeartbeatRequest,
    WorkerRegistrationRequest,
    WorkerRegistrationResponse,
    WorkerTaskReportRequest,
)
from helaicopter_db.models.oltp import WorkerRegistryRecord
from oats.attack_plan import build_attack_plan
from oats.envelope import ExecutionEnvelope, build_execution_envelope


def _generate_worker_id() -> str:
    return f"wkr_{secrets.token_hex(12)}"


def _to_detail(row: WorkerRegistryRecord) -> WorkerDetailResponse:
    caps = json.loads(row.capabilities_json)
    return WorkerDetailResponse(
        worker_id=row.worker_id,
        worker_type=row.worker_type,
        provider=row.provider,
        capabilities=WorkerCapabilitiesResponse(**caps),
        host=row.host,
        pid=row.pid,
        worktree_root=row.worktree_root,
        registered_at=row.registered_at.isoformat(),
        last_heartbeat_at=row.last_heartbeat_at.isoformat(),
        status=row.status,
        current_task_id=row.current_task_id,
        current_run_id=row.current_run_id,
    )


def register_worker(
    engine: Engine,
    request: WorkerRegistrationRequest,
) -> WorkerRegistrationResponse:
    now = datetime.now(UTC)
    worker_id = _generate_worker_id()
    caps_json = json.dumps(request.capabilities.model_dump(by_alias=True))

    record = WorkerRegistryRecord(
        worker_id=worker_id,
        worker_type=request.worker_type,
        provider=request.provider,
        capabilities_json=caps_json,
        host=request.host,
        pid=request.pid,
        worktree_root=request.worktree_root,
        registered_at=now,
        last_heartbeat_at=now,
        status="idle",
    )
    with Session(engine) as session:
        session.add(record)
        session.commit()

    return WorkerRegistrationResponse(worker_id=worker_id, status="idle")


def list_workers(
    engine: Engine,
    *,
    provider: str | None = None,
) -> list[WorkerDetailResponse]:
    stmt = select(WorkerRegistryRecord)
    if provider is not None:
        stmt = stmt.where(WorkerRegistryRecord.provider == provider)
    with Session(engine) as session:
        rows = session.execute(stmt).scalars().all()
        return [_to_detail(row) for row in rows]


def get_worker(engine: Engine, worker_id: str) -> WorkerDetailResponse | None:
    with Session(engine) as session:
        row = session.get(WorkerRegistryRecord, worker_id)
        if row is None:
            return None
        return _to_detail(row)


def heartbeat_worker(
    engine: Engine,
    worker_id: str,
    request: WorkerHeartbeatRequest,
    *,
    registry=None,
) -> bool:
    """Update heartbeat. Returns False if worker not found."""
    return heartbeat_worker_state(
        engine=engine,
        registry=registry,
        worker_id=worker_id,
        status=request.status,
        current_task_id=request.current_task_id,
        current_run_id=request.current_run_id,
    )


def drain_worker(engine: Engine, worker_id: str, *, registry=None) -> bool:
    """Set worker status to draining. Returns False if worker not found."""
    return drain_worker_state(engine=engine, registry=registry, worker_id=worker_id)


def deregister_worker(engine: Engine, worker_id: str) -> bool:
    """Remove worker from registry. Returns False if worker not found."""
    with Session(engine) as session:
        result = session.execute(
            delete(WorkerRegistryRecord).where(WorkerRegistryRecord.worker_id == worker_id)
        )
        session.commit()
        return result.rowcount > 0


def pull_next_task(
    engine: Engine,
    *,
    worker_id: str,
    resolver: ResolverLoop,
    runtime_dir: Path,
) -> ExecutionEnvelope | None:
    """Claim the next ready task matching a worker's capabilities."""
    with Session(engine) as session:
        row = session.get(WorkerRegistryRecord, worker_id)
        if row is None:
            raise KeyError(worker_id)

        capabilities = json.loads(row.capabilities_json)
        models: list[str] = capabilities.get("models", [])
        provider = row.provider

        worker = resolver._registry.get(worker_id)
        if worker is None:
            worker = resolver._registry.register(
                provider=provider,
                models=models,
                worker_id=worker_id,
            )
        worker.status = row.status
        worker.current_task_id = row.current_task_id
        worker.current_run_id = row.current_run_id

        if row.status != "idle":
            return None

        for run_id, graph in resolver._graphs.items():
            for task_id in graph.ready_tasks():
                node = graph.nodes[task_id]
                if node.status != "pending":
                    continue

                agent = resolver._task_agents.get(task_id, provider)
                model = resolver._task_models.get(task_id, "claude-sonnet-4-6")
                if agent != provider:
                    continue
                if models and model not in models:
                    continue

                node.status = "running"
                mark_worker_dispatched(
                    engine=engine,
                    registry=resolver._registry,
                    worker_id=worker_id,
                    run_id=run_id,
                    task_id=task_id,
                )
                resolver.record_dispatch_event(
                    run_id=run_id,
                    task_id=task_id,
                    worker_id=worker_id,
                    provider=agent,
                    model=model,
                )
                attack_plan = build_attack_plan(node, plan_steps=[], context_snippets=[])
                return build_execution_envelope(
                    task=node,
                    run_id=run_id,
                    agent=agent,
                    model=model,
                    worker_id=worker_id,
                    dispatch_mode="pull",
                    worktree_path=str(runtime_dir / run_id / "worktrees" / task_id),
                    parent_branch="main",
                    attack_plan=attack_plan,
                    acceptance_criteria=attack_plan.acceptance_criteria,
                )
        return None


def report_task_result(
    engine: Engine,
    *,
    worker_id: str,
    request: WorkerTaskReportRequest,
    resolver: ResolverLoop,
    runtime_dir: Path,
) -> bool:
    """Persist a worker task result and signal the resolver."""
    with Session(engine) as session:
        row = session.get(WorkerRegistryRecord, worker_id)
        if row is None:
            return False
        worker = resolver._registry.get(worker_id)
        run_id = row.current_run_id or (worker.current_run_id if worker is not None else None)
        if run_id is None:
            return False

        result = TaskResult(
            task_id=request.task_id,
            run_id=run_id,
            worker_id=worker_id,
            status=request.status,
            duration_seconds=request.duration_seconds,
            attempt_id=request.attempt_id,
            branch_name=request.branch_name,
            commit_sha=request.commit_sha,
            error_summary=request.error_summary,
        )
        result_path = runtime_dir / run_id / "results" / request.task_id / f"{request.attempt_id}.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        resolver.submit_completion(result)

        complete_worker_task(
            engine=engine,
            registry=resolver._registry,
            worker_id=worker_id,
        )
        return True
