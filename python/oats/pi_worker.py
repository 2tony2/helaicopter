"""Pi v1 worker shell.

Pi is a long-lived supervisor process that registers with the control plane,
pulls work, spawns a fresh provider subprocess per task, and reports results.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Protocol

import httpx

from oats.envelope import ExecutionEnvelope
from oats.identity import generate_attempt_id, generate_session_id
from oats.provider_session import ProviderSession, ProviderSessionManager


@dataclass
class AgentRunResult:
    exit_code: int
    duration_seconds: float
    branch_name: str | None = None
    commit_sha: str | None = None
    criteria_met: bool | None = None
    error_summary: str | None = None
    session_reused: bool = False


class AgentRunner(Protocol):
    async def run(
        self,
        envelope: ExecutionEnvelope,
        on_heartbeat,
        session: ProviderSession | None = None,
    ) -> AgentRunResult: ...


class ControlPlaneClient(Protocol):
    async def register(self, payload: dict[str, object]) -> dict[str, object]: ...

    async def get_worker_detail(self, worker_id: str) -> dict[str, object]: ...

    async def pull_next_task(self, worker_id: str) -> ExecutionEnvelope | None: ...

    async def heartbeat(self, worker_id: str, payload: dict[str, object]) -> None: ...

    async def report_result(self, worker_id: str, payload: dict[str, object]) -> None: ...


class ControlPlaneUnavailableError(RuntimeError):
    """Raised when Pi cannot register with the control plane."""


class SubprocessAgentRunner:
    """Spawn a fresh provider CLI subprocess for each task."""

    def __init__(self, *, heartbeat_interval: float = 30.0) -> None:
        self.heartbeat_interval = heartbeat_interval

    async def run(
        self,
        envelope: ExecutionEnvelope,
        on_heartbeat,
        session: ProviderSession | None = None,
    ) -> AgentRunResult:
        del session
        worktree = Path(envelope.worktree_path)
        worktree.mkdir(parents=True, exist_ok=True)
        command = self._build_command(envelope, self._build_prompt(envelope))
        started_at = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(worktree),
        )
        while process.returncode is None:
            try:
                await asyncio.wait_for(process.wait(), timeout=self.heartbeat_interval)
            except TimeoutError:
                await on_heartbeat()

        duration = time.monotonic() - started_at
        exit_code = process.returncode or 0
        error_summary = None if exit_code == 0 else f"Agent exited with code {exit_code}"
        return AgentRunResult(
            exit_code=exit_code,
            duration_seconds=duration,
            error_summary=error_summary,
        )

    def _build_command(self, envelope: ExecutionEnvelope, prompt: str) -> list[str]:
        if envelope.agent == "claude":
            return ["claude", "-p", prompt, "--model", envelope.model]
        if envelope.agent == "codex":
            return ["codex", "exec", "--model", envelope.model, prompt]
        raise ValueError(f"unsupported agent: {envelope.agent}")

    def _build_prompt(self, envelope: ExecutionEnvelope) -> str:
        if envelope.attack_plan is not None and envelope.attack_plan.instructions:
            return envelope.attack_plan.instructions
        return f"Complete task {envelope.task_id} for run {envelope.run_id}."


class HttpControlPlaneClient:
    def __init__(
        self,
        *,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self.transport = transport

    async def register(self, payload: dict[str, object]) -> dict[str, object]:
        response = await self._request("POST", "/workers/register", json=payload)
        response.raise_for_status()
        return response.json()

    async def pull_next_task(self, worker_id: str) -> ExecutionEnvelope | None:
        response = await self._request("GET", f"/workers/{worker_id}/next-task")
        if response.status_code == 204:
            return None
        response.raise_for_status()
        return ExecutionEnvelope.model_validate(response.json())

    async def get_worker_detail(self, worker_id: str) -> dict[str, object]:
        response = await self._request("GET", f"/workers/{worker_id}")
        response.raise_for_status()
        return response.json()

    async def heartbeat(self, worker_id: str, payload: dict[str, object]) -> None:
        response = await self._request("POST", f"/workers/{worker_id}/heartbeat", json=payload)
        response.raise_for_status()

    async def report_result(self, worker_id: str, payload: dict[str, object]) -> None:
        response = await self._request("POST", f"/workers/{worker_id}/report", json=payload)
        response.raise_for_status()

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            transport=self.transport,
            timeout=30.0,
        ) as client:
            return await client.request(method, path, **kwargs)


class PiWorker:
    def __init__(
        self,
        *,
        provider: str,
        models: list[str],
        control_plane_url: str,
        agent_runner: AgentRunner | None = None,
        heartbeat_interval: float = 30.0,
        poll_interval: float = 5.0,
        host: str = "local",
        pid: int | None = None,
        worktree_root: str | None = None,
        control_plane_client: ControlPlaneClient | None = None,
        session_manager: ProviderSessionManager | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.provider = provider
        self.models = models
        self.control_plane_url = control_plane_url.rstrip("/")
        self.agent_runner = agent_runner or SubprocessAgentRunner(heartbeat_interval=heartbeat_interval)
        self.heartbeat_interval = heartbeat_interval
        self.poll_interval = poll_interval
        self.host = host
        self.pid = pid
        self.worktree_root = worktree_root
        self.control_plane_client = control_plane_client or HttpControlPlaneClient(
            base_url=self.control_plane_url,
            transport=transport,
        )
        self.session_manager = session_manager or ProviderSessionManager(provider=provider)

        self.worker_id: str | None = None
        self.status = "idle"
        self._running = False

    def preflight(self) -> list[str]:
        issues: list[str] = []
        if not self.models:
            issues.append("No model capabilities configured.")
        if not self.control_plane_url:
            issues.append("Control plane URL is required.")
        if self.provider == "codex" and not (Path.home() / ".codex").exists():
            issues.append("Codex local CLI session is not configured.")
        return issues

    async def register(self) -> str:
        payload = {
            "workerType": "pi_shell",
            "provider": self.provider,
            "capabilities": {
                "provider": self.provider,
                "models": self.models,
                "maxConcurrentTasks": 1,
                "supportsDiscovery": False,
                "supportsResume": False,
                "tags": [],
            },
            "host": self.host,
            "pid": self.pid,
            "worktreeRoot": self.worktree_root,
        }
        try:
            body = await self.control_plane_client.register(payload)
        except Exception as exc:
            raise ControlPlaneUnavailableError(
                f"Unable to register {self.provider} worker with control plane {self.control_plane_url}: {exc}"
            ) from exc
        self.worker_id = body["workerId"]
        self.status = body["status"]
        return self.worker_id

    async def run_loop(self) -> None:
        if self.worker_id is None:
            await self.register()
        self._running = True
        while self._running:
            await self.run_one_cycle()
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        self._running = False

    async def run_one_cycle(self) -> dict[str, str] | None:
        if self.worker_id is None:
            await self.register()
        await self._reconcile_session_reset_request()

        envelope = await self._pull_next_task()
        if envelope is None:
            self.status = "idle"
            return None

        try:
            final_envelope, result = await self._run_with_redispatch(envelope)
        except Exception as exc:
            await self._report_result(
                envelope,
                AgentRunResult(
                    exit_code=1,
                    duration_seconds=0.0,
                    error_summary=str(exc) or "Provider session bootstrap failed.",
                ),
            )
            self.status = "idle"
            return {"status": "reported", "task_id": envelope.task_id}
        await self._report_result(final_envelope, result)
        self.status = "idle"
        return {"status": "reported", "task_id": envelope.task_id}

    async def _pull_next_task(self) -> ExecutionEnvelope | None:
        assert self.worker_id is not None
        envelope = await self.control_plane_client.pull_next_task(self.worker_id)
        if envelope is None:
            return None
        self.status = "busy"
        return envelope

    async def _run_with_redispatch(
        self,
        envelope: ExecutionEnvelope,
    ) -> tuple[ExecutionEnvelope, AgentRunResult]:
        current_envelope = envelope
        last_result = await self._execute_task(current_envelope)
        max_attempts = max(current_envelope.retry_policy.max_attempts, 1)
        attempts_used = 1

        while not await self._check_acceptance_criteria(current_envelope, last_result):
            if attempts_used >= max_attempts:
                last_result.exit_code = 1
                last_result.error_summary = self._default_error_summary(
                    current_envelope,
                    last_result,
                    fallback="Acceptance criteria not met after redispatch budget exhausted.",
                )
                return current_envelope, last_result
            attempts_used += 1
            current_envelope = self._redispatch(current_envelope)
            last_result = await self._execute_task(current_envelope)

        if last_result.exit_code != 0 and last_result.error_summary is None:
            last_result.error_summary = self._default_error_summary(current_envelope, last_result)
        return current_envelope, last_result

    async def _execute_task(self, envelope: ExecutionEnvelope) -> AgentRunResult:
        current_session = getattr(self.session_manager, "session", None)
        session_reused = current_session is not None and self.session_manager.status == "ready"
        session = self.session_manager.ensure_session()
        result = await self.agent_runner.run(
            envelope,
            lambda: self._emit_heartbeat(envelope),
            session=session,
        )
        result.session_reused = session_reused
        return result

    async def _reconcile_session_reset_request(self) -> None:
        assert self.worker_id is not None
        payload = await self.control_plane_client.get_worker_detail(self.worker_id)
        if payload.get("sessionResetRequestedAt") is None:
            return
        self.session_manager.reset(reason="operator_requested")
        self.status = "idle"
        await self.control_plane_client.heartbeat(
            self.worker_id,
            {
                "status": "idle",
                "currentTaskId": None,
                "currentRunId": None,
                **self._session_payload(),
            },
        )

    async def _check_acceptance_criteria(
        self,
        envelope: ExecutionEnvelope,
        execution_result: AgentRunResult,
    ) -> bool:
        if execution_result.exit_code != 0:
            return False
        if not envelope.acceptance_criteria:
            return True
        criteria_met = getattr(execution_result, "criteria_met", None)
        if criteria_met is None:
            criteria_met = getattr(execution_result, "acceptance_criteria_met", None)
        if criteria_met is not None:
            return criteria_met
        return False

    def _redispatch(self, envelope: ExecutionEnvelope) -> ExecutionEnvelope:
        refocused = envelope.attack_plan.instructions if envelope.attack_plan is not None else ""
        if envelope.acceptance_criteria:
            criteria_text = "\n".join(f"- {item.description}" for item in envelope.acceptance_criteria)
            refocused = (
                f"{refocused}\n\n# Remaining Acceptance Criteria\n\n{criteria_text}\n"
                "Focus only on the unmet items."
            ).strip()
        attack_plan = envelope.attack_plan
        if attack_plan is not None:
            attack_plan = attack_plan.model_copy(update={"instructions": refocused})
        return envelope.model_copy(
            update={
                "attempt_id": generate_attempt_id(),
                "session_id": generate_session_id(),
                "attack_plan": attack_plan,
            }
        )

    async def _emit_heartbeat(self, envelope: ExecutionEnvelope) -> None:
        assert self.worker_id is not None
        await self.control_plane_client.heartbeat(
            self.worker_id,
            {
                "status": "busy",
                "currentTaskId": envelope.task_id,
                "currentRunId": envelope.run_id,
                **self._session_payload(),
            },
        )

    async def _report_result(self, envelope: ExecutionEnvelope, result: AgentRunResult) -> None:
        assert self.worker_id is not None
        status = "succeeded" if result.exit_code == 0 else "failed"
        await self.control_plane_client.report_result(
            self.worker_id,
            {
                "taskId": envelope.task_id,
                "attemptId": envelope.attempt_id,
                "status": status,
                "durationSeconds": result.duration_seconds,
                "branchName": result.branch_name,
                "commitSha": result.commit_sha,
                "errorSummary": result.error_summary,
                "sessionReused": result.session_reused,
                **self._session_payload(),
            },
        )

    def _session_payload(self) -> dict[str, object]:
        session = getattr(self.session_manager, "session", None)
        return {
            "providerSessionId": session.session_id if session is not None else None,
            "sessionStatus": self.session_manager.status,
            "sessionStartedAt": session.started_at.isoformat() if session is not None else None,
            "sessionLastUsedAt": session.last_used_at.isoformat() if session is not None else None,
            "sessionFailureReason": self.session_manager.failure_reason,
        }

    def _default_error_summary(
        self,
        envelope: ExecutionEnvelope,
        result: AgentRunResult,
        *,
        fallback: str | None = None,
    ) -> str:
        if result.error_summary:
            return result.error_summary
        if envelope.agent == "codex":
            return "Codex local CLI session may be missing or expired."
        if envelope.agent == "claude":
            return "Claude local CLI session may be missing or expired."
        if fallback is not None:
            return fallback
        return f"Agent exited with code {result.exit_code}"
