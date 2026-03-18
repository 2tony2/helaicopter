"""Concrete adapter for local evaluation subprocess jobs."""

from __future__ import annotations

import os
import shlex
from datetime import UTC, datetime
from threading import Lock, Thread
from time import monotonic
from typing import Callable, Protocol

from helaicopter_api.ports.evaluations import EvaluationJobRequest, EvaluationJobResult, EvaluationJobRunner


class SupportsSubprocessRun(Protocol):
    def run(
        self,
        cmd: list[str],
        *,
        cwd: object = None,
        timeout: float | None = 60,
        capture_output: bool = True,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
    ) -> object:
        ...


class LocalCliEvaluationRunner(EvaluationJobRunner):
    """Run evaluation jobs on daemon threads backed by local CLI subprocesses."""

    def __init__(self, *, subprocess_runner: SupportsSubprocessRun) -> None:
        self._subprocess_runner = subprocess_runner
        self._lock = Lock()
        self._threads: dict[str, Thread] = {}

    def describe_command(self, request: EvaluationJobRequest) -> str:
        return _format_command(_build_command(request))

    def submit(
        self,
        request: EvaluationJobRequest,
        on_complete: Callable[[EvaluationJobResult], None],
    ) -> None:
        thread = Thread(
            target=self._run_job,
            args=(request, on_complete),
            name=f"evaluation-job-{request.evaluation_id}",
            daemon=True,
        )
        with self._lock:
            self._threads[request.evaluation_id] = thread
        thread.start()

    def _run_job(
        self,
        request: EvaluationJobRequest,
        on_complete: Callable[[EvaluationJobResult], None],
    ) -> None:
        started_at = monotonic()
        command = _build_command(request)
        command_text = _format_command(command)
        try:
            completed = self._subprocess_runner.run(
                command,
                cwd=request.workspace,
                timeout=request.timeout_seconds,
                capture_output=True,
                input_text=request.prompt,
                env={**os.environ, "CI": "1"},
            )
            duration_ms = int((monotonic() - started_at) * 1000)
            stdout = (completed.stdout or "").strip()
            stderr = (completed.stderr or "").strip()
            raw_output = "\n".join(part for part in (stdout, stderr) if part) or None
            if completed.returncode == 0:
                result = EvaluationJobResult(
                    evaluation_id=request.evaluation_id,
                    status="completed",
                    report_markdown=stdout or raw_output,
                    raw_output=raw_output,
                    error_message=None,
                    command=command_text,
                    finished_at=_now_iso(),
                    duration_ms=duration_ms,
                )
            else:
                result = EvaluationJobResult(
                    evaluation_id=request.evaluation_id,
                    status="failed",
                    report_markdown=None,
                    raw_output=raw_output,
                    error_message=stderr or stdout or f"{command[0]} exited with status {completed.returncode}.",
                    command=command_text,
                    finished_at=_now_iso(),
                    duration_ms=duration_ms,
                )
        except Exception as error:
            result = EvaluationJobResult(
                evaluation_id=request.evaluation_id,
                status="failed",
                report_markdown=None,
                raw_output=None,
                error_message=str(error) or "Evaluation job failed.",
                command=command_text,
                finished_at=_now_iso(),
                duration_ms=int((monotonic() - started_at) * 1000),
            )
        finally:
            with self._lock:
                self._threads.pop(request.evaluation_id, None)

        on_complete(result)


def _build_command(request: EvaluationJobRequest) -> list[str]:
    if request.provider == "claude":
        return [
            "claude",
            "-p",
            "--dangerously-skip-permissions",
            "--model",
            request.model,
        ]
    return [
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        "-C",
        str(request.workspace),
        "-m",
        request.model,
        "-",
    ]


def _format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
