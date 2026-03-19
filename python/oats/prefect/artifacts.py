from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import json
import os
import tempfile

from pydantic import BaseModel

from oats.prefect.models import PrefectFlowPayload, PrefectTaskNode


class FlowRunArtifactPaths(BaseModel):
    artifact_root: Path
    metadata_path: Path
    tasks_dir: Path
    attempts_dir: Path


class LocalFlowRunMetadata(BaseModel):
    flow_run_id: str
    flow_run_name: str | None = None
    run_title: str
    source_path: Path
    repo_root: Path
    config_path: Path
    artifact_root: Path
    created_at: str
    updated_at: str
    completed_at: str | None = None


class LocalTaskCheckpoint(BaseModel):
    flow_run_id: str
    flow_run_name: str | None = None
    task_id: str
    task_title: str
    status: str
    attempt: int
    upstream_task_ids: list[str]
    session_id: str | None = None
    session_id_field: str | None = None
    requested_session_id: str | None = None
    output_text: str | None = None
    last_heartbeat_at: str | None = None
    last_progress_event_at: str | None = None
    result: dict[str, object] | None = None
    error: str | None = None
    updated_at: str


class LocalArtifactCheckpointStore:
    def __init__(
        self,
        *,
        payload: PrefectFlowPayload,
        flow_run_id: str,
        flow_run_name: str | None = None,
    ) -> None:
        artifact_root = payload.repo_root / ".oats" / "prefect" / "flow-runs" / flow_run_id
        self._payload = payload
        self._flow_run_id = flow_run_id
        self._flow_run_name = flow_run_name
        self.paths = FlowRunArtifactPaths(
            artifact_root=artifact_root,
            metadata_path=artifact_root / "metadata.json",
            tasks_dir=artifact_root / "tasks",
            attempts_dir=artifact_root / "attempts",
        )

    @property
    def metadata_path(self) -> Path:
        return self.paths.metadata_path

    def initialize(self) -> Path:
        self.paths.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.paths.attempts_dir.mkdir(parents=True, exist_ok=True)
        metadata = LocalFlowRunMetadata(
            flow_run_id=self._flow_run_id,
            flow_run_name=self._flow_run_name,
            run_title=self._payload.run_title,
            source_path=self._payload.source_path,
            repo_root=self._payload.repo_root,
            config_path=self._payload.config_path,
            artifact_root=self.paths.artifact_root,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        _atomic_write_json(self.paths.metadata_path, metadata.model_dump(mode="json"))
        return self.paths.metadata_path

    def finalize(self) -> Path:
        metadata = LocalFlowRunMetadata.model_validate_json(
            self.paths.metadata_path.read_text(encoding="utf-8")
        )
        metadata.updated_at = _utc_now()
        metadata.completed_at = _utc_now()
        _atomic_write_json(self.paths.metadata_path, metadata.model_dump(mode="json"))
        return self.paths.metadata_path

    def write_task_checkpoint(
        self,
        task_node: PrefectTaskNode,
        *,
        status: str,
        attempt: int,
        upstream_task_ids: list[str],
        session_id: str | None = None,
        session_id_field: str | None = None,
        requested_session_id: str | None = None,
        output_text: str | None = None,
        last_heartbeat_at: str | None = None,
        last_progress_event_at: str | None = None,
        result: dict[str, object] | None = None,
        error: str | None = None,
    ) -> Path:
        checkpoint = LocalTaskCheckpoint(
            flow_run_id=self._flow_run_id,
            flow_run_name=self._flow_run_name,
            task_id=task_node.task_id,
            task_title=task_node.title,
            status=status,
            attempt=attempt,
            upstream_task_ids=sorted(upstream_task_ids),
            session_id=session_id,
            session_id_field=session_id_field,
            requested_session_id=requested_session_id,
            output_text=output_text,
            last_heartbeat_at=last_heartbeat_at,
            last_progress_event_at=last_progress_event_at,
            result=result,
            error=error,
            updated_at=_utc_now(),
        )
        current_checkpoint = self.paths.tasks_dir / f"{task_node.task_id}.json"
        attempt_dir = self.paths.attempts_dir / task_node.task_id
        attempt_dir.mkdir(parents=True, exist_ok=True)
        attempt_checkpoint = attempt_dir / f"attempt-{attempt}.json"
        payload = checkpoint.model_dump(mode="json")
        _atomic_write_json(attempt_checkpoint, payload)
        _atomic_write_json(current_checkpoint, payload)
        self._touch_metadata()
        return current_checkpoint

    def _touch_metadata(self) -> None:
        metadata = LocalFlowRunMetadata.model_validate_json(
            self.paths.metadata_path.read_text(encoding="utf-8")
        )
        metadata.updated_at = _utc_now()
        _atomic_write_json(self.paths.metadata_path, metadata.model_dump(mode="json"))


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
