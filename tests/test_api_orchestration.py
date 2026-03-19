"""Endpoint tests for the orchestration API."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from helaicopter_api.adapters.oats_artifacts import FileOatsRunStore
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from oats.models import (
    AgentInvocationResult,
    InvocationRuntimeRecord,
    RunExecutionRecord,
    RunRuntimeState,
    TaskExecutionRecord,
    TaskRuntimeRecord,
)


def _write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def orchestration_client(project_root: Path) -> Iterator[TestClient]:
    application = create_app()
    store = FileOatsRunStore(
        project_root=project_root,
        runtime_dir=project_root / ".oats" / "runtime",
    )
    application.dependency_overrides[get_services] = lambda: _services_stub(oats_run_store=store)
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()


class TestOatsArtifactStore:
    def test_store_uses_cached_json_validators_for_runtime_and_run_artifacts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        now = datetime.now(UTC)
        run_id = "oats-run-1"
        repo_root = tmp_path
        state_path = repo_root / ".oats" / "runtime" / run_id / "state.json"
        record_path = repo_root / ".oats" / "runs" / "sample-record.json"

        _write_model(
            state_path,
            RunRuntimeState(
                run_id=run_id,
                run_title="Ship orchestration API",
                repo_root=repo_root,
                config_path=repo_root / ".oats" / "config.toml",
                run_spec_path=repo_root / "runs" / "sample.md",
                mode="writable",
                integration_branch="oats/overnight/orchestration-api",
                task_pr_target="oats/overnight/orchestration-api",
                final_pr_target="main",
                runtime_dir=state_path.parent,
                status="running",
                active_task_id="task-api",
                started_at=now - timedelta(minutes=10),
                updated_at=now - timedelta(minutes=1),
                heartbeat_at=now - timedelta(seconds=5),
                planner=None,
                tasks=[],
                final_record_path=record_path,
            ),
        )
        _write_model(
            record_path,
            RunExecutionRecord(
                run_id=run_id,
                run_title="Ship orchestration API",
                repo_root=repo_root,
                config_path=repo_root / ".oats" / "config.toml",
                run_spec_path=repo_root / "runs" / "sample.md",
                mode="writable",
                integration_branch="oats/overnight/orchestration-api",
                task_pr_target="oats/overnight/orchestration-api",
                final_pr_target="main",
                planner=AgentInvocationResult(
                    agent="codex",
                    role="planner",
                    command=["codex", "exec"],
                    cwd=repo_root,
                    prompt="plan the run",
                    session_id="planner-1",
                    exit_code=0,
                    started_at=now - timedelta(minutes=12),
                    finished_at=now - timedelta(minutes=11),
                ),
                tasks=[],
                recorded_at=now - timedelta(minutes=10),
            ),
        )

        monkeypatch.setattr(
            RunRuntimeState,
            "model_validate_json",
            classmethod(
                lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                    AssertionError("runtime states should use cached JSON adapters")
                )
            ),
        )
        monkeypatch.setattr(
            RunExecutionRecord,
            "model_validate_json",
            classmethod(
                lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                    AssertionError("run records should use cached JSON adapters")
                )
            ),
        )

        store = FileOatsRunStore(
            project_root=repo_root,
            runtime_dir=repo_root / ".oats" / "runtime",
        )

        runtime_states = store.list_runtime_states()
        run_records = store.list_run_records()

        assert [item.state.run_id for item in runtime_states] == [run_id]
        assert [item.record.run_id for item in run_records] == [run_id]


class TestOrchestrationEndpoint:
    def test_runtime_state_response_is_camel_cased_and_preferred_over_stale_run_record(
        self,
        tmp_path: Path,
    ) -> None:
        now = datetime.now(UTC)
        repo_root = tmp_path
        run_id = "oats-runtime-1"
        record_path = repo_root / ".oats" / "runs" / "sample-older.json"
        state_path = repo_root / ".oats" / "runtime" / run_id / "state.json"

        stale_record = RunExecutionRecord(
            run_id=run_id,
            run_title="Ship orchestration API",
            repo_root=repo_root,
            config_path=repo_root / ".oats" / "config.toml",
            run_spec_path=repo_root / "runs" / "sample.md",
            mode="writable",
            integration_branch="oats/overnight/orchestration-api",
            task_pr_target="oats/overnight/orchestration-api",
            final_pr_target="main",
            planner=AgentInvocationResult(
                agent="codex",
                role="planner",
                command=["codex", "exec"],
                cwd=repo_root,
                prompt="plan the run",
                session_id="planner-old",
                exit_code=0,
                started_at=now - timedelta(minutes=20),
                finished_at=now - timedelta(minutes=19),
            ),
            tasks=[],
            recorded_at=now - timedelta(minutes=18),
        )
        _write_model(record_path, stale_record)

        runtime_state = RunRuntimeState(
            run_id=run_id,
            run_title="Ship orchestration API",
            repo_root=repo_root,
            config_path=repo_root / ".oats" / "config.toml",
            run_spec_path=repo_root / "runs" / "sample.md",
            mode="writable",
            integration_branch="oats/overnight/orchestration-api",
            task_pr_target="oats/overnight/orchestration-api",
            final_pr_target="main",
            runtime_dir=state_path.parent,
            status="running",
            active_task_id="task-api",
            started_at=now - timedelta(minutes=10),
            updated_at=now - timedelta(seconds=5),
            heartbeat_at=now - timedelta(seconds=2),
            planner=InvocationRuntimeRecord(
                agent="codex",
                role="planner",
                command=["codex", "exec"],
                cwd=repo_root,
                prompt="plan the run",
                session_id="planner-live",
                exit_code=0,
                started_at=now - timedelta(minutes=10),
                last_heartbeat_at=now - timedelta(minutes=9),
                finished_at=now - timedelta(minutes=9),
            ),
            tasks=[
                TaskRuntimeRecord(
                    task_id="task-api",
                    title="Implement route",
                    depends_on=[],
                    branch_name="oats/task/task-api",
                    pr_base="oats/overnight/orchestration-api",
                    agent="claude",
                    status="running",
                    attempts=1,
                    invocation=InvocationRuntimeRecord(
                        agent="claude",
                        role="executor",
                        command=["claude", "run"],
                        cwd=repo_root,
                        prompt="implement the route",
                        session_id="claude-task-1",
                        output_text="working",
                        started_at=now - timedelta(minutes=3),
                        last_heartbeat_at=now - timedelta(seconds=2),
                    ),
                ),
                TaskRuntimeRecord(
                    task_id="task-tests",
                    title="Add endpoint tests",
                    depends_on=["task-api"],
                    branch_name="oats/task/task-tests",
                    pr_base="oats/overnight/orchestration-api",
                    agent="claude",
                    status="pending",
                    attempts=0,
                    invocation=None,
                ),
            ],
            final_record_path=record_path,
        )
        _write_model(state_path, runtime_state)

        with orchestration_client(repo_root) as client:
            response = client.get("/orchestration/oats")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1

        run = payload[0]
        encoded_codex_project = quote(f"codex:{str(repo_root).replace('/', '-')}", safe="")
        encoded_claude_project = quote(str(repo_root).replace("/", "-"), safe="")

        assert run["contractVersion"] == "oats-runtime-v1"
        assert run["runId"] == run_id
        assert run["recordPath"].endswith(f"/.oats/runtime/{run_id}/state.json")
        assert run["status"] == "running"
        assert run["activeTaskId"] == "task-api"
        assert run["isRunning"] is True
        assert run["planner"]["conversationPath"] == f"/conversations/{encoded_codex_project}/planner-live"
        assert run["tasks"][0]["taskId"] == "task-api"
        assert run["tasks"][0]["invocation"]["conversationPath"] == (
            f"/conversations/{encoded_claude_project}/claude-task-1"
        )
        assert run["tasks"][1]["dependsOn"] == ["task-api"]
        assert run["tasks"][1]["invocation"]["agent"] == "claude"
        assert run["tasks"][1]["invocation"]["conversationPath"] is None
        assert run["dag"]["stats"]["totalNodes"] == 3
        assert run["dag"]["stats"]["totalEdges"] == 2
        assert run["dag"]["stats"]["activeCount"] == 1
        assert "contract_version" not in run
        assert "task_id" not in run["tasks"][0]

    def test_run_record_response_shapes_terminal_summary_without_runtime_state(
        self,
        tmp_path: Path,
    ) -> None:
        now = datetime.now(UTC)
        repo_root = tmp_path
        record_path = repo_root / ".oats" / "runs" / "sample-record.json"
        record = RunExecutionRecord(
            run_id="oats-record-1",
            run_title="Fix rollout failures",
            repo_root=repo_root,
            config_path=repo_root / ".oats" / "config.toml",
            run_spec_path=repo_root / "runs" / "failures.md",
            mode="read-only",
            integration_branch="oats/overnight/fix-rollout-failures",
            task_pr_target="oats/overnight/fix-rollout-failures",
            final_pr_target="main",
            planner=AgentInvocationResult(
                agent="codex",
                role="planner",
                command=["codex", "exec"],
                cwd=repo_root,
                prompt="plan the run",
                session_id="planner-1",
                exit_code=0,
                started_at=now - timedelta(minutes=7),
                finished_at=now - timedelta(minutes=6),
            ),
            tasks=[
                TaskExecutionRecord(
                    task_id="task-one",
                    title="Inspect failure",
                    depends_on=[],
                    invocation=AgentInvocationResult(
                        agent="claude",
                        role="executor",
                        command=["claude", "run"],
                        cwd=repo_root,
                        prompt="inspect failure",
                        session_id="task-thread-1",
                        exit_code=1,
                        raw_stderr="boom",
                        started_at=now - timedelta(minutes=5),
                        finished_at=now - timedelta(minutes=4),
                    ),
                )
            ],
            recorded_at=now - timedelta(minutes=3),
        )
        _write_model(record_path, record)
        (repo_root / ".oats" / "runs" / "ignore-me.json").write_text("{not json", encoding="utf-8")

        with orchestration_client(repo_root) as client:
            response = client.get("/orchestration/oats")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1

        run = payload[0]
        encoded_claude_project = quote(str(repo_root).replace("/", "-"), safe="")

        assert run["contractVersion"] == "oats-run-v1"
        assert run["status"] == "failed"
        assert run["isRunning"] is False
        assert run["finishedAt"] == run["recordedAt"]
        assert run["tasks"][0]["status"] == "failed"
        assert run["tasks"][0]["invocation"]["conversationPath"] == (
            f"/conversations/{encoded_claude_project}/task-thread-1"
        )
        assert run["dag"]["stats"]["failedCount"] == 2
        assert run["dag"]["stats"]["providerBreakdown"] == {"codex": 1, "claude": 1}

    def test_openapi_exposes_orchestration_route(self, tmp_path: Path) -> None:
        with orchestration_client(tmp_path) as client:
            response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        orchestration_get = schema["paths"]["/orchestration/oats"]["get"]
        assert orchestration_get["tags"] == ["orchestration-legacy"]
        assert orchestration_get["responses"]["200"]["content"]["application/json"]["schema"]["items"][
            "$ref"
        ].endswith("/OrchestrationRunResponse")

        run_schema = schema["components"]["schemas"]["OrchestrationRunResponse"]
        task_schema = schema["components"]["schemas"]["OrchestrationTaskResponse"]
        assert "runId" in run_schema["properties"]
        assert "run_id" not in run_schema["properties"]
        assert "activeTaskId" in run_schema["properties"]
        assert "taskId" in task_schema["properties"]
        assert "task_id" not in task_schema["properties"]
