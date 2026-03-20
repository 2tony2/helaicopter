from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from oats.prefect.artifacts import LocalFlowRunMetadata, LocalTaskCheckpoint

_LOCAL_FLOW_RUN_METADATA_ADAPTER = TypeAdapter(LocalFlowRunMetadata)
_LOCAL_TASK_CHECKPOINT_ADAPTER = TypeAdapter(LocalTaskCheckpoint)
_SUCCESSFUL_TASK_STATUSES = {"completed", "succeeded", "skipped"}
_FAILED_TASK_STATUSES = {"failed", "timed_out", "crashed", "cancelled", "canceled"}
_RUNNING_TASK_STATUSES = {"running", "pending", "blocked"}


class LocalFlowRunAnalytics(BaseModel):
    flow_run_id: str
    run_status: str
    task_count: int = 0
    completed_task_count: int = 0
    running_task_count: int = 0
    failed_task_count: int = 0
    task_attempt_count: int = 0
    last_updated_at: str | None = None


class StoredLocalFlowRunArtifacts(BaseModel):
    metadata_path: Path
    metadata: LocalFlowRunMetadata
    checkpoints: list[LocalTaskCheckpoint] = []
    attempts: list[LocalTaskCheckpoint] = []
    analytics: LocalFlowRunAnalytics


def load_local_flow_run_analytics(project_root: Path) -> dict[str, LocalFlowRunAnalytics]:
    return {
        flow_run_id: stored.analytics
        for flow_run_id, stored in load_local_flow_run_artifacts(project_root).items()
    }


def load_local_flow_run_artifacts(project_root: Path) -> dict[str, StoredLocalFlowRunArtifacts]:
    metadata_root = project_root / ".oats" / "prefect" / "flow-runs"
    items: dict[str, StoredLocalFlowRunArtifacts] = {}
    for path in sorted(metadata_root.glob("*/metadata.json")):
        try:
            metadata = _LOCAL_FLOW_RUN_METADATA_ADAPTER.validate_json(path.read_bytes())
        except (FileNotFoundError, OSError, ValueError):
            continue
        checkpoints = _load_task_checkpoints(path.parent / "tasks")
        attempts = _load_attempt_checkpoints(path.parent / "attempts")
        items[metadata.flow_run_id] = StoredLocalFlowRunArtifacts(
            metadata_path=path,
            metadata=metadata,
            checkpoints=checkpoints,
            attempts=attempts,
            analytics=_build_analytics(metadata, checkpoints, attempts),
        )
    return items


def _load_task_checkpoints(tasks_dir: Path) -> list[LocalTaskCheckpoint]:
    checkpoints: list[LocalTaskCheckpoint] = []
    for path in sorted(tasks_dir.glob("*.json")):
        try:
            checkpoints.append(_LOCAL_TASK_CHECKPOINT_ADAPTER.validate_json(path.read_bytes()))
        except (FileNotFoundError, OSError, ValueError):
            continue
    return checkpoints


def _load_attempt_checkpoints(attempts_dir: Path) -> list[LocalTaskCheckpoint]:
    checkpoints: list[LocalTaskCheckpoint] = []
    for path in sorted(attempts_dir.glob("*/*.json")):
        try:
            checkpoints.append(_LOCAL_TASK_CHECKPOINT_ADAPTER.validate_json(path.read_bytes()))
        except (FileNotFoundError, OSError, ValueError):
            continue
    return checkpoints


def _build_analytics(
    metadata: LocalFlowRunMetadata,
    checkpoints: list[LocalTaskCheckpoint],
    attempts: list[LocalTaskCheckpoint],
) -> LocalFlowRunAnalytics:
    normalized_statuses = {
        checkpoint.status.strip().lower()
        for checkpoint in checkpoints
        if checkpoint.status.strip()
    }
    task_count = len(checkpoints)
    completed_task_count = sum(
        1 for checkpoint in checkpoints if checkpoint.status.strip().lower() in _SUCCESSFUL_TASK_STATUSES
    )
    running_task_count = sum(
        1 for checkpoint in checkpoints if checkpoint.status.strip().lower() in _RUNNING_TASK_STATUSES
    )
    failed_task_count = sum(
        1 for checkpoint in checkpoints if checkpoint.status.strip().lower() in _FAILED_TASK_STATUSES
    )
    timestamps = [
        timestamp
        for timestamp in [
            metadata.created_at,
            metadata.updated_at,
            metadata.completed_at,
            *[checkpoint.updated_at for checkpoint in checkpoints],
            *[checkpoint.updated_at for checkpoint in attempts],
        ]
        if timestamp
    ]
    last_updated_at = max(timestamps, key=_sort_timestamp, default=None)
    run_status = _derive_run_status(
        normalized_statuses=normalized_statuses,
        has_completed_at=metadata.completed_at is not None,
        task_count=task_count,
        completed_task_count=completed_task_count,
        failed_task_count=failed_task_count,
        running_task_count=running_task_count,
    )
    return LocalFlowRunAnalytics(
        flow_run_id=metadata.flow_run_id,
        run_status=run_status,
        task_count=task_count,
        completed_task_count=completed_task_count,
        running_task_count=running_task_count,
        failed_task_count=failed_task_count,
        task_attempt_count=len(attempts),
        last_updated_at=last_updated_at,
    )


def _derive_run_status(
    *,
    normalized_statuses: set[str],
    has_completed_at: bool,
    task_count: int,
    completed_task_count: int,
    failed_task_count: int,
    running_task_count: int,
) -> str:
    if failed_task_count > 0 or normalized_statuses & _FAILED_TASK_STATUSES:
        return "failed"
    if running_task_count > 0 or normalized_statuses & _RUNNING_TASK_STATUSES:
        return "running"
    if has_completed_at or (task_count > 0 and completed_task_count == task_count):
        return "completed"
    return "pending"


def _sort_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
