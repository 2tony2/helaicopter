from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from typer.testing import CliRunner

from oats.cli import app
from oats.envelope import AcceptanceCriterion, ExecutionEnvelope


def _run(coro):
    return asyncio.run(coro)


def _build_envelope(*, acceptance_criteria: list[AcceptanceCriterion] | None = None) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        session_id="sess_test",
        attempt_id="att_test",
        task_id="task_auth",
        run_id="run_123",
        agent="claude",
        model="claude-sonnet-4-6",
        worker_id="wkr_test",
        dispatch_mode="pull",
        worktree_path="/tmp/oats/task_auth",
        parent_branch="main",
        timeout_seconds=300,
        acceptance_criteria=acceptance_criteria or [],
    )


@dataclass
class FakeRunResult:
    exit_code: int = 0
    duration_seconds: float = 0.1
    branch_name: str | None = "oats/task/task_auth"
    commit_sha: str | None = "abc123"
    error_summary: str | None = None
    acceptance_criteria_met: bool = True
    heartbeat_ticks: int = 0


class FakeAgentRunner:
    def __init__(self, results: list[FakeRunResult] | None = None) -> None:
        self.results = list(results or [FakeRunResult()])
        self.dispatch_count = 0

    async def run(self, envelope: ExecutionEnvelope, on_heartbeat) -> FakeRunResult:
        del envelope
        self.dispatch_count += 1
        result = self.results[min(self.dispatch_count - 1, len(self.results) - 1)]
        for _ in range(result.heartbeat_ticks):
            await on_heartbeat()
        return result


class FakeControlPlane:
    def __init__(self, *, queued_tasks: list[ExecutionEnvelope] | None = None) -> None:
        self.worker_id = "wkr_test_123"
        self.queued_tasks = list(queued_tasks or [])
        self.registered_payloads: list[dict[str, Any]] = []
        self.heartbeat_payloads: list[dict[str, Any]] = []
        self.report_payloads: list[dict[str, Any]] = []

    async def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.registered_payloads.append(payload)
        return {"workerId": self.worker_id, "status": "idle"}

    async def pull_next_task(self, worker_id: str) -> ExecutionEnvelope | None:
        assert worker_id == self.worker_id
        if self.queued_tasks:
            return self.queued_tasks.pop(0)
        return None

    async def heartbeat(self, worker_id: str, payload: dict[str, Any]) -> None:
        assert worker_id == self.worker_id
        self.heartbeat_payloads.append(payload)

    async def report_result(self, worker_id: str, payload: dict[str, Any]) -> None:
        assert worker_id == self.worker_id
        self.report_payloads.append(payload)


def test_pi_registers_with_control_plane() -> None:
    from oats.pi_worker import PiWorker

    control_plane = FakeControlPlane()
    worker = PiWorker(
        provider="claude",
        models=["claude-sonnet-4-6"],
        control_plane_url="http://control-plane.test",
        control_plane_client=control_plane,
    )

    _run(worker.register())

    assert worker.worker_id == "wkr_test_123"
    assert control_plane.registered_payloads == [{
        "workerType": "pi_shell",
        "provider": "claude",
        "capabilities": {
            "provider": "claude",
            "models": ["claude-sonnet-4-6"],
            "maxConcurrentTasks": 1,
            "supportsDiscovery": False,
            "supportsResume": False,
            "tags": [],
        },
        "host": "local",
        "pid": None,
        "worktreeRoot": None,
    }]


def test_pi_pulls_executes_and_reports_result() -> None:
    from oats.pi_worker import PiWorker

    control_plane = FakeControlPlane(queued_tasks=[_build_envelope()])
    runner = FakeAgentRunner([FakeRunResult(exit_code=0)])
    worker = PiWorker(
        provider="claude",
        models=["claude-sonnet-4-6"],
        control_plane_url="http://control-plane.test",
        control_plane_client=control_plane,
        agent_runner=runner,
    )

    _run(worker.register())
    _run(worker.run_one_cycle())

    assert worker.status == "idle"
    assert runner.dispatch_count == 1
    assert control_plane.report_payloads == [{
        "taskId": "task_auth",
        "attemptId": "att_test",
        "status": "succeeded",
        "durationSeconds": 0.1,
        "branchName": "oats/task/task_auth",
        "commitSha": "abc123",
        "errorSummary": None,
    }]


def test_pi_redispatches_when_acceptance_criteria_are_unmet() -> None:
    from oats.pi_worker import PiWorker

    control_plane = FakeControlPlane(
        queued_tasks=[_build_envelope(acceptance_criteria=[AcceptanceCriterion(description="Create files")])]
    )
    runner = FakeAgentRunner(
        [
            FakeRunResult(exit_code=0, acceptance_criteria_met=False),
            FakeRunResult(exit_code=0, acceptance_criteria_met=True),
        ]
    )
    worker = PiWorker(
        provider="claude",
        models=["claude-sonnet-4-6"],
        control_plane_url="http://control-plane.test",
        control_plane_client=control_plane,
        agent_runner=runner,
    )

    _run(worker.register())
    _run(worker.run_one_cycle())

    assert runner.dispatch_count == 2
    assert control_plane.report_payloads[-1]["status"] == "succeeded"


def test_pi_emits_heartbeats_during_execution() -> None:
    from oats.pi_worker import PiWorker

    control_plane = FakeControlPlane(queued_tasks=[_build_envelope()])
    runner = FakeAgentRunner([FakeRunResult(exit_code=0, heartbeat_ticks=3)])
    worker = PiWorker(
        provider="claude",
        models=["claude-sonnet-4-6"],
        control_plane_url="http://control-plane.test",
        control_plane_client=control_plane,
        agent_runner=runner,
        heartbeat_interval=1.0,
    )

    _run(worker.register())
    _run(worker.run_one_cycle())

    assert len(control_plane.heartbeat_payloads) >= 3
    assert all(payload["status"] == "busy" for payload in control_plane.heartbeat_payloads)


def test_pi_handles_no_tasks_gracefully() -> None:
    from oats.pi_worker import PiWorker

    control_plane = FakeControlPlane()
    worker = PiWorker(
        provider="claude",
        models=["claude-sonnet-4-6"],
        control_plane_url="http://control-plane.test",
        control_plane_client=control_plane,
    )

    _run(worker.register())
    _run(worker.run_one_cycle())

    assert worker.status == "idle"
    assert control_plane.report_payloads == []


def test_cli_pi_start_runs_worker(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakePiWorker:
        def __init__(self, **kwargs: object) -> None:
            calls.append({"init": kwargs})

        async def run_loop(self) -> None:
            calls.append({"run_loop": True})

    monkeypatch.setattr("oats.pi_worker.PiWorker", FakePiWorker)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "pi",
            "start",
            "--provider",
            "claude",
            "--model",
            "claude-sonnet-4-6",
            "--control-plane",
            "http://control-plane.test",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert calls == [
        {
            "init": {
                "provider": "claude",
                "models": ["claude-sonnet-4-6"],
                "control_plane_url": "http://control-plane.test",
                "heartbeat_interval": 30.0,
                "poll_interval": 5.0,
            }
        },
        {"run_loop": True},
    ]
