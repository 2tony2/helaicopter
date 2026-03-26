"""Shared worker lifecycle transitions for DB and in-memory registry state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from helaicopter_api.application.dispatch import InMemoryWorkerRegistry
from helaicopter_db.models.oltp import WorkerRegistryRecord

_BLOCKED_STATUSES = {"draining", "dead", "auth_expired"}


class _WorkerStateTarget(Protocol):
    status: str
    current_task_id: str | None
    current_run_id: str | None
    last_heartbeat_at: datetime


def _set_auth_status(target: object, value: str) -> None:
    if hasattr(target, "auth_status"):
        setattr(target, "auth_status", value)


def _targets_for(
    engine: Engine | None,
    registry: InMemoryWorkerRegistry | None,
    worker_id: str,
) -> tuple[Session | None, list[_WorkerStateTarget]]:
    session = Session(engine) if engine is not None else None
    targets: list[_WorkerStateTarget] = []
    if session is not None:
        row = session.get(WorkerRegistryRecord, worker_id)
        if row is not None:
            targets.append(row)
    if registry is not None:
        worker = registry.get(worker_id)
        if worker is not None:
            targets.append(worker)
    return session, targets


def _commit_and_close(session: Session | None) -> None:
    if session is None:
        return
    try:
        session.commit()
    finally:
        session.close()


def heartbeat_worker_state(
    *,
    engine: Engine | None,
    registry: InMemoryWorkerRegistry | None,
    worker_id: str,
    status: str,
    current_task_id: str | None = None,
    current_run_id: str | None = None,
) -> bool:
    session, targets = _targets_for(engine, registry, worker_id)
    if not targets:
        if session is not None:
            session.close()
        return False

    now = datetime.now(UTC)
    for target in targets:
        target.last_heartbeat_at = now
        if current_task_id is not None:
            target.current_task_id = current_task_id
        if current_run_id is not None:
            target.current_run_id = current_run_id
        if target.status not in _BLOCKED_STATUSES:
            target.status = status
    _commit_and_close(session)
    return True


def drain_worker_state(
    *,
    engine: Engine | None,
    registry: InMemoryWorkerRegistry | None,
    worker_id: str,
) -> bool:
    session, targets = _targets_for(engine, registry, worker_id)
    if not targets:
        if session is not None:
            session.close()
        return False

    for target in targets:
        if target.status not in {"dead", "auth_expired"}:
            target.status = "draining"
    _commit_and_close(session)
    return True


def mark_worker_dispatched(
    *,
    engine: Engine | None,
    registry: InMemoryWorkerRegistry | None,
    worker_id: str,
    run_id: str,
    task_id: str,
) -> bool:
    session, targets = _targets_for(engine, registry, worker_id)
    if not targets:
        if session is not None:
            session.close()
        return False

    now = datetime.now(UTC)
    for target in targets:
        target.status = "busy"
        target.current_task_id = task_id
        target.current_run_id = run_id
        target.last_heartbeat_at = now
    _commit_and_close(session)
    return True


def complete_worker_task(
    *,
    engine: Engine | None,
    registry: InMemoryWorkerRegistry | None,
    worker_id: str,
) -> bool:
    session, targets = _targets_for(engine, registry, worker_id)
    if not targets:
        if session is not None:
            session.close()
        return False

    now = datetime.now(UTC)
    for target in targets:
        if target.status == "draining":
            next_status = "draining"
        elif target.status in {"dead", "auth_expired"}:
            next_status = target.status
        else:
            next_status = "idle"
        target.status = next_status
        target.current_task_id = None
        target.current_run_id = None
        target.last_heartbeat_at = now
    _commit_and_close(session)
    return True


def mark_worker_auth_expired(
    *,
    engine: Engine | None,
    registry: InMemoryWorkerRegistry | None,
    worker_id: str,
) -> bool:
    session, targets = _targets_for(engine, registry, worker_id)
    if not targets:
        if session is not None:
            session.close()
        return False

    now = datetime.now(UTC)
    for target in targets:
        target.status = "auth_expired"
        target.last_heartbeat_at = now
        _set_auth_status(target, "expired")
    _commit_and_close(session)
    return True


def restore_worker_auth(
    *,
    engine: Engine | None,
    registry: InMemoryWorkerRegistry | None,
    worker_id: str,
) -> bool:
    session, targets = _targets_for(engine, registry, worker_id)
    if not targets:
        if session is not None:
            session.close()
        return False

    now = datetime.now(UTC)
    for target in targets:
        _set_auth_status(target, "valid")
        if target.status == "auth_expired":
            target.status = "idle"
            target.last_heartbeat_at = now
    _commit_and_close(session)
    return True


def mark_worker_dead(
    *,
    engine: Engine | None,
    registry: InMemoryWorkerRegistry | None,
    worker_id: str,
) -> bool:
    session, targets = _targets_for(engine, registry, worker_id)
    if not targets:
        if session is not None:
            session.close()
        return False

    now = datetime.now(UTC)
    for target in targets:
        target.status = "dead"
        target.current_task_id = None
        target.current_run_id = None
        target.last_heartbeat_at = now
    _commit_and_close(session)
    return True
