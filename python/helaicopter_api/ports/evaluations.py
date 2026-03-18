"""Port protocol for locally executed evaluation jobs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

from helaicopter_domain.ids import EvaluationId
from helaicopter_domain.vocab import EvaluationStatus, ProviderName


@dataclass(frozen=True, slots=True)
class EvaluationJobRequest:
    evaluation_id: EvaluationId
    provider: ProviderName
    model: str
    workspace: Path
    prompt: str
    timeout_seconds: float = 60


@dataclass(frozen=True, slots=True)
class EvaluationJobResult:
    evaluation_id: EvaluationId
    status: EvaluationStatus
    report_markdown: str | None
    raw_output: str | None
    error_message: str | None
    command: str
    finished_at: str
    duration_ms: int


@runtime_checkable
class EvaluationJobRunner(Protocol):
    """Submit evaluation work to a backend-owned local runner."""

    def describe_command(self, request: EvaluationJobRequest) -> str:
        """Return the human-readable CLI command that will execute the job."""
        ...

    def submit(
        self,
        request: EvaluationJobRequest,
        on_complete: Callable[[EvaluationJobResult], None],
    ) -> None:
        """Start the job and invoke ``on_complete`` once the subprocess finishes."""
        ...
