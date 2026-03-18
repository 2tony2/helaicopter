"""Concrete adapter for local OATS runtime and run artifacts."""

from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from helaicopter_api.ports.orchestration import (
    OatsRunStore,
    StoredOatsRunRecord,
    StoredOatsRuntimeState,
)
from oats.models import RunExecutionRecord, RunRuntimeState

_RUN_EXECUTION_RECORD_ADAPTER = TypeAdapter(RunExecutionRecord)
_RUN_RUNTIME_STATE_ADAPTER = TypeAdapter(RunRuntimeState)


class FileOatsRunStore(OatsRunStore):
    """Read repo-local OATS runtime state and execution records from disk."""

    def __init__(self, *, project_root: Path, runtime_dir: Path) -> None:
        self._runtime_dir = runtime_dir
        self._runs_dir = project_root / ".oats" / "runs"

    def list_runtime_states(self) -> list[StoredOatsRuntimeState]:
        return [
            StoredOatsRuntimeState(path=path, state=state)
            for path, state in (
                (path, _load_json_model(path, _RUN_RUNTIME_STATE_ADAPTER))
                for path in sorted(self._runtime_dir.glob("*/state.json"))
            )
            if state is not None
        ]

    def list_run_records(self) -> list[StoredOatsRunRecord]:
        return [
            StoredOatsRunRecord(path=path, record=record)
            for path, record in (
                (path, _load_json_model(path, _RUN_EXECUTION_RECORD_ADAPTER))
                for path in sorted(self._runs_dir.glob("*.json"))
            )
            if record is not None
        ]


def _load_json_model[T](path: Path, adapter: TypeAdapter[T]) -> T | None:
    try:
        return adapter.validate_json(path.read_bytes())
    except (FileNotFoundError, OSError, ValidationError, ValueError):
        return None
