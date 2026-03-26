"""Port protocols for OATS orchestration run artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from oats.models import RunExecutionRecord, RunRuntimeState


@dataclass(frozen=True, slots=True)
class StoredOatsRuntimeState:
    path: Path
    state: RunRuntimeState


@dataclass(frozen=True, slots=True)
class StoredOatsRunRecord:
    path: Path
    record: RunExecutionRecord


@runtime_checkable
class OatsRunStore(Protocol):
    """Read locally persisted OATS runtime and execution artifacts."""

    def list_runtime_states(self) -> list[StoredOatsRuntimeState]:
        """Return parsed runtime state snapshots from local artifacts."""
        ...

    def list_run_records(self) -> list[StoredOatsRunRecord]:
        """Return parsed terminal run records from local artifacts."""
        ...

    def get_runtime_state(self, run_id: str) -> StoredOatsRuntimeState | None:
        """Return one parsed runtime state snapshot by run ID, if present."""
        ...
