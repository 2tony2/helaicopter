"""Concrete adapter for local OATS runtime and run artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from helaicopter_api.ports.orchestration import (
    OatsRunStore,
    StoredOatsRunRecord,
    StoredOatsRuntimeState,
)
from oats.models import RunExecutionRecord, RunRuntimeState

TModel = TypeVar("TModel", bound=BaseModel)


class FileOatsRunStore(OatsRunStore):
    """Read repo-local OATS runtime state and execution records from disk."""

    def __init__(self, *, project_root: Path, runtime_dir: Path) -> None:
        self._runtime_dir = runtime_dir
        self._runs_dir = project_root / ".oats" / "runs"

    def list_runtime_states(self) -> list[StoredOatsRuntimeState]:
        return [
            StoredOatsRuntimeState(path=path, state=state)
            for path, state in (
                (path, self._load_model(path, RunRuntimeState))
                for path in sorted(self._runtime_dir.glob("*/state.json"))
            )
            if state is not None
        ]

    def list_run_records(self) -> list[StoredOatsRunRecord]:
        return [
            StoredOatsRunRecord(path=path, record=record)
            for path, record in (
                (path, self._load_model(path, RunExecutionRecord))
                for path in sorted(self._runs_dir.glob("*.json"))
            )
            if record is not None
        ]

    def _load_model(self, path: Path, model_type: type[TModel]) -> TModel | None:
        try:
            return model_type.model_validate_json(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValidationError, ValueError):
            return None
