"""Endpoint tests for the orchestration API."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from helaicopter_api.adapters.app_sqlite import SqliteAppStore
from helaicopter_api.adapters.oats_artifacts import FileOatsRunStore
from helaicopter_api.application import orchestration as orchestration_application
from helaicopter_api.application.orchestration import _shape_run_record
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.orchestration import StoredOatsRunRecord
from helaicopter_api.server.config import Settings
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db.models.oltp import (
    ConversationRecord,
    FactOrchestrationRun,
    FactOrchestrationTaskAttempt,
    OltpBase,
)
from oats.models import (
    AgentInvocationResult,
    FeatureBranchSnapshot,
    InvocationRuntimeRecord,
    FinalPullRequestSnapshot,
    OperationHistoryEntry,
    RunExecutionRecord,
    RunRuntimeState,
    TaskPullRequestSnapshot,
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


def _init_sqlite(project_root: Path) -> Settings:
    settings = Settings(project_root=project_root)
    settings.app_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{settings.app_sqlite_path}")
    OltpBase.metadata.create_all(engine)
    engine.dispose()
    return settings


def _insert_conversation_record(
    session: Session,
    *,
    provider: str,
    session_id: str,
    project_path: str,
    route_slug: str,
    started_at: datetime,
) -> None:
    session.add(
        ConversationRecord(
            conversation_id=f"{provider}:{session_id}",
            provider=provider,
            session_id=session_id,
            project_path=project_path,
            project_name=project_path.removeprefix("codex:"),
            thread_type="main",
            first_message=route_slug.replace("-", " "),
            route_slug=route_slug,
            started_at=started_at,
            ended_at=started_at + timedelta(minutes=5),
            message_count=1,
            model=None,
            git_branch=None,
            reasoning_effort=None,
            speed=None,
            total_input_tokens=0,
            total_output_tokens=0,
            total_cache_write_tokens=0,
            total_cache_read_tokens=0,
            total_reasoning_tokens=0,
            tool_use_count=0,
            subagent_count=0,
            task_count=0,
            record_source="test",
            source_file_modified_at=started_at,
            loaded_at=started_at,
            first_ingested_at=started_at,
            last_refreshed_at=started_at,
        )
    )


@contextmanager
def orchestration_client(project_root: Path, **service_attrs: object) -> Iterator[TestClient]:
    application = create_app()
    store = FileOatsRunStore(
        project_root=project_root,
        runtime_dir=project_root / ".oats" / "runtime",
    )
    settings = service_attrs.pop("settings", None) or Settings(project_root=project_root)
    application.dependency_overrides[get_services] = lambda: _services_stub(
        oats_run_store=store,
        settings=settings,
        **service_attrs,
    )
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
    def test_fact_endpoint_prefers_fresh_runtime_state_and_emits_latest_attempt_facts(
        self,
        tmp_path: Path,
    ) -> None:
        now = datetime.now(UTC)
        repo_root = tmp_path
        run_id = "oats-facts-runtime"
        state_path = repo_root / ".oats" / "runtime" / run_id / "state.json"
        record_path = repo_root / ".oats" / "runs" / "runtime-terminal.json"

        _write_model(
            record_path,
            RunExecutionRecord(
                run_id=run_id,
                run_title="Runtime should win while active",
                repo_root=repo_root,
                config_path=repo_root / ".oats" / "config.toml",
                run_spec_path=repo_root / "runs" / "runtime.md",
                mode="writable",
                integration_branch="oats/overnight/runtime-facts",
                task_pr_target="oats/overnight/runtime-facts",
                final_pr_target="main",
                tasks=[
                    TaskExecutionRecord(
                        task_id="task-api",
                        title="Implement route",
                        depends_on=[],
                        invocation=AgentInvocationResult(
                            agent="claude",
                            role="executor",
                            command=["claude", "run"],
                            cwd=repo_root,
                            prompt="implement route",
                            session_id="task-api-terminal",
                            exit_code=0,
                            started_at=now - timedelta(minutes=12),
                            finished_at=now - timedelta(minutes=11),
                        ),
                    )
                ],
                recorded_at=now - timedelta(minutes=10),
            ),
        )
        _write_model(
            state_path,
            RunRuntimeState(
                run_id=run_id,
                run_title="Runtime should win while active",
                repo_root=repo_root,
                config_path=repo_root / ".oats" / "config.toml",
                run_spec_path=repo_root / "runs" / "runtime.md",
                mode="writable",
                integration_branch="oats/overnight/runtime-facts",
                task_pr_target="oats/overnight/runtime-facts",
                final_pr_target="main",
                runtime_dir=state_path.parent,
                status="running",
                active_task_id="task-api",
                started_at=now - timedelta(minutes=6),
                updated_at=now - timedelta(seconds=10),
                heartbeat_at=now - timedelta(seconds=5),
                tasks=[
                    TaskRuntimeRecord(
                        task_id="task-api",
                        title="Implement route",
                        depends_on=[],
                        branch_name="oats/task/task-api",
                        pr_base="oats/overnight/runtime-facts",
                        agent="claude",
                        status="running",
                        attempts=2,
                        invocation=InvocationRuntimeRecord(
                            agent="claude",
                            role="executor",
                            command=["claude", "run"],
                            cwd=repo_root,
                            prompt="implement route",
                            session_id="task-api-runtime",
                            exit_code=None,
                            started_at=now - timedelta(minutes=2),
                            last_heartbeat_at=now - timedelta(seconds=5),
                        ),
                    )
                ],
                final_record_path=record_path,
            ),
        )

        with orchestration_client(repo_root) as client:
            response = client.get("/orchestration/oats/facts")

        assert response.status_code == 200
        payload = response.json()
        assert payload["canonicalRules"] == [
            "prefer fresh runtime snapshots while a run is still active",
            "prefer terminal run records when runtime snapshots are stale or missing",
            "emit one task-attempt fact for the latest observed runtime attempt when history is incomplete",
            "emit one terminal task-attempt fact per recorded task invocation with attempt number 1",
        ]
        assert payload["runFacts"] == [
            {
                "runId": run_id,
                "runTitle": "Runtime should win while active",
                "sourceKind": "runtime_snapshot",
                "canonicalReason": "runtime snapshot is active and fresher than any terminal record",
                "status": "running",
                "taskCount": 1,
                "attemptCount": 2,
                "completedTaskCount": 0,
                "failedTaskCount": 0,
                "pendingTaskCount": 0,
                "runningTaskCount": 1,
                "timedOutTaskCount": 0,
                "activeTaskId": "task-api",
                "isRunning": True,
                "isStale": False,
                "runtimeStatePath": str(state_path),
                "terminalRecordPath": str(record_path),
            }
        ]
        assert payload["taskAttemptFacts"] == [
            {
                "runId": run_id,
                "taskId": "task-api",
                "taskTitle": "Implement route",
                "attemptNumber": 2,
                "sourceKind": "runtime_snapshot",
                "status": "running",
                "agent": "claude",
                "sessionId": "task-api-runtime",
                "exitCode": None,
                "timedOut": False,
            }
        ]

    def test_fact_endpoint_prefers_terminal_record_when_runtime_snapshot_is_stale(
        self,
        tmp_path: Path,
    ) -> None:
        now = datetime.now(UTC)
        repo_root = tmp_path
        run_id = "oats-facts-terminal"
        state_path = repo_root / ".oats" / "runtime" / run_id / "state.json"
        record_path = repo_root / ".oats" / "runs" / "terminal.json"

        _write_model(
            state_path,
            RunRuntimeState(
                run_id=run_id,
                run_title="Terminal should win after staleness",
                repo_root=repo_root,
                config_path=repo_root / ".oats" / "config.toml",
                run_spec_path=repo_root / "runs" / "terminal.md",
                mode="writable",
                integration_branch="oats/overnight/terminal-facts",
                task_pr_target="oats/overnight/terminal-facts",
                final_pr_target="main",
                runtime_dir=state_path.parent,
                status="running",
                active_task_id="task-api",
                started_at=now - timedelta(minutes=20),
                updated_at=now - timedelta(minutes=8),
                heartbeat_at=now - timedelta(minutes=8),
                tasks=[
                    TaskRuntimeRecord(
                        task_id="task-api",
                        title="Implement route",
                        depends_on=[],
                        branch_name="oats/task/task-api",
                        pr_base="oats/overnight/terminal-facts",
                        agent="claude",
                        status="running",
                        attempts=1,
                        invocation=InvocationRuntimeRecord(
                            agent="claude",
                            role="executor",
                            command=["claude", "run"],
                            cwd=repo_root,
                            prompt="implement route",
                            session_id="task-api-runtime",
                            started_at=now - timedelta(minutes=10),
                            last_heartbeat_at=now - timedelta(minutes=8),
                        ),
                    )
                ],
                final_record_path=record_path,
            ),
        )
        _write_model(
            record_path,
            RunExecutionRecord(
                run_id=run_id,
                run_title="Terminal should win after staleness",
                repo_root=repo_root,
                config_path=repo_root / ".oats" / "config.toml",
                run_spec_path=repo_root / "runs" / "terminal.md",
                mode="writable",
                integration_branch="oats/overnight/terminal-facts",
                task_pr_target="oats/overnight/terminal-facts",
                final_pr_target="main",
                tasks=[
                    TaskExecutionRecord(
                        task_id="task-api",
                        title="Implement route",
                        depends_on=[],
                        invocation=AgentInvocationResult(
                            agent="claude",
                            role="executor",
                            command=["claude", "run"],
                            cwd=repo_root,
                            prompt="implement route",
                            session_id="task-api-terminal",
                            exit_code=1,
                            raw_stderr="boom",
                            started_at=now - timedelta(minutes=7),
                            finished_at=now - timedelta(minutes=6),
                        ),
                    )
                ],
                recorded_at=now - timedelta(minutes=6),
            ),
        )

        with orchestration_client(repo_root) as client:
            response = client.get("/orchestration/oats/facts")

        assert response.status_code == 200
        payload = response.json()
        assert payload["runFacts"] == [
            {
                "runId": run_id,
                "runTitle": "Terminal should win after staleness",
                "sourceKind": "terminal_record",
                "canonicalReason": "terminal record wins because the runtime snapshot is stale",
                "status": "failed",
                "taskCount": 1,
                "attemptCount": 1,
                "completedTaskCount": 0,
                "failedTaskCount": 1,
                "pendingTaskCount": 0,
                "runningTaskCount": 0,
                "timedOutTaskCount": 0,
                "activeTaskId": None,
                "isRunning": False,
                "isStale": True,
                "runtimeStatePath": str(state_path),
                "terminalRecordPath": str(record_path),
            }
        ]
        assert payload["taskAttemptFacts"] == [
            {
                "runId": run_id,
                "taskId": "task-api",
                "taskTitle": "Implement route",
                "attemptNumber": 1,
                "sourceKind": "terminal_record",
                "status": "failed",
                "agent": "claude",
                "sessionId": "task-api-terminal",
                "exitCode": 1,
                "timedOut": False,
            }
        ]

    def test_run_list_reads_persisted_oats_facts_and_filters_sample_runs(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        now = datetime.now(UTC)
        repo_root = tmp_path
        settings = _init_sqlite(repo_root)
        engine = create_engine(f"sqlite:///{settings.app_sqlite_path}")
        with Session(engine) as session:
            session.add(
                FactOrchestrationRun(
                    run_fact_id="oats_local:sample-run-1",
                    run_source="oats_local",
                    run_id="sample-run-1",
                    flow_run_name=None,
                    run_title="Run: Auth And Dashboard",
                    source_path=str(repo_root / "examples" / "sample_run.md"),
                    repo_root=str(repo_root),
                    config_path=str(repo_root / ".oats" / "config.toml"),
                    artifact_root=str(repo_root / ".oats" / "runtime" / "sample-run-1"),
                    status="running",
                    canonical_status_source="runtime_state_snapshot",
                    has_runtime_snapshot=True,
                    has_terminal_record=False,
                    task_count=1,
                    completed_task_count=0,
                    running_task_count=1,
                    failed_task_count=0,
                    task_attempt_count=1,
                    started_at=now - timedelta(minutes=15),
                    updated_at=now - timedelta(minutes=10),
                    finished_at=None,
                )
            )
            session.add(
                FactOrchestrationRun(
                    run_fact_id="oats_local:real-run-1",
                    run_source="oats_local",
                    run_id="real-run-1",
                    flow_run_name=None,
                    run_title="Ship real orchestration run",
                    source_path=str(repo_root / "docs" / "superpowers" / "plans" / "run.md"),
                    repo_root=str(repo_root),
                    config_path=str(repo_root / ".oats" / "config.toml"),
                    artifact_root=str(repo_root / ".oats" / "runtime" / "real-run-1"),
                    status="running",
                    canonical_status_source="runtime_state_snapshot",
                    has_runtime_snapshot=True,
                    has_terminal_record=True,
                    task_count=2,
                    completed_task_count=0,
                    running_task_count=1,
                    failed_task_count=0,
                    task_attempt_count=2,
                    started_at=now - timedelta(minutes=12),
                    updated_at=now - timedelta(minutes=8),
                    finished_at=None,
                )
            )
            session.add_all(
                [
                    FactOrchestrationTaskAttempt(
                        task_attempt_fact_id="oats_local:real-run-1:task-api:1",
                        run_fact_id="oats_local:real-run-1",
                        run_source="oats_local",
                        run_id="real-run-1",
                        task_id="task-api",
                        task_title="Implement route",
                        attempt=1,
                        status="running",
                        upstream_task_ids_json="[]",
                        agent="claude",
                        session_id="claude-task-1",
                        model=None,
                        reasoning_effort=None,
                        error=None,
                        output_text="working",
                        started_at=now - timedelta(minutes=10),
                        updated_at=now - timedelta(minutes=8),
                        finished_at=None,
                        last_heartbeat_at=now - timedelta(minutes=8),
                        last_progress_event_at=now - timedelta(minutes=8),
                    ),
                    FactOrchestrationTaskAttempt(
                        task_attempt_fact_id="oats_local:real-run-1:task-tests:1",
                        run_fact_id="oats_local:real-run-1",
                        run_source="oats_local",
                        run_id="real-run-1",
                        task_id="task-tests",
                        task_title="Add endpoint tests",
                        attempt=1,
                        status="blocked",
                        upstream_task_ids_json='["task-api"]',
                        agent="claude",
                        session_id=None,
                        model=None,
                        reasoning_effort=None,
                        error=None,
                        output_text=None,
                        started_at=None,
                        updated_at=now - timedelta(minutes=8),
                        finished_at=None,
                        last_heartbeat_at=None,
                        last_progress_event_at=None,
                    ),
                ]
            )
            _insert_conversation_record(
                session,
                provider="claude",
                session_id="claude-task-1",
                project_path=str(repo_root).replace("/", "-"),
                route_slug="ship-real-orchestration-run-task-api",
                started_at=now - timedelta(minutes=10),
            )
            session.commit()
        engine.dispose()

        monkeypatch.setattr(
            orchestration_application,
            "_resolve_conversation_identity",
            lambda *args, **kwargs: pytest.fail("historical orchestration links should not use the generic resolver"),
        )

        with orchestration_client(
            repo_root,
            settings=settings,
            app_sqlite_store=SqliteAppStore(db_path=settings.app_sqlite_path),
        ) as client:
            response = client.get("/orchestration/oats")

        assert response.status_code == 200
        payload = response.json()
        assert [run["runId"] for run in payload] == ["real-run-1"]

        run = payload[0]
        assert run["contractVersion"] == "oats-runtime-v1"
        assert run["recordPath"] == "oats_local:real-run-1"
        assert run["status"] == "pending"
        assert run["activeTaskId"] is None
        assert run["isRunning"] is False
        assert [task["taskId"] for task in run["tasks"]] == ["task-api", "task-tests"]
        assert [task["status"] for task in run["tasks"]] == ["pending", "blocked"]
        assert run["tasks"][0]["invocation"]["conversationPath"] == (
            "/conversations/by-ref/ship-real-orchestration-run-task-api--claude-claude-task-1"
        )
        assert run["tasks"][1]["dependsOn"] == ["task-api"]
        assert run["planner"] is None
        assert run["dag"]["stats"]["totalNodes"] == 2
        assert run["dag"]["stats"]["activeCount"] == 0
        assert run["dag"]["stats"]["providerBreakdown"] == {"claude": 2}

    def test_run_list_emits_null_for_unresolved_non_null_session_links(self, tmp_path: Path) -> None:
        now = datetime.now(UTC)
        repo_root = tmp_path
        settings = _init_sqlite(repo_root)
        engine = create_engine(f"sqlite:///{settings.app_sqlite_path}")
        with Session(engine) as session:
            session.add(
                FactOrchestrationRun(
                    run_fact_id="oats_local:run-unresolved-link",
                    run_source="oats_local",
                    run_id="run-unresolved-link",
                    flow_run_name=None,
                    run_title="Run with unresolved link",
                    source_path=str(repo_root / "docs" / "superpowers" / "plans" / "run.md"),
                    repo_root=str(repo_root),
                    config_path=str(repo_root / ".oats" / "config.toml"),
                    artifact_root=str(repo_root / ".oats" / "runtime" / "run-unresolved-link"),
                    status="running",
                    canonical_status_source="runtime_state_snapshot",
                    has_runtime_snapshot=True,
                    has_terminal_record=True,
                    task_count=1,
                    completed_task_count=0,
                    running_task_count=1,
                    failed_task_count=0,
                    task_attempt_count=1,
                    started_at=now - timedelta(minutes=6),
                    updated_at=now - timedelta(minutes=3),
                    finished_at=None,
                )
            )
            session.add(
                FactOrchestrationTaskAttempt(
                    task_attempt_fact_id="oats_local:run-unresolved-link:task-api:1",
                    run_fact_id="oats_local:run-unresolved-link",
                    run_source="oats_local",
                    run_id="run-unresolved-link",
                    task_id="task-api",
                    task_title="Implement route",
                    attempt=1,
                    status="running",
                    upstream_task_ids_json="[]",
                    agent="claude",
                    session_id="claude-task-missing",
                    model=None,
                    reasoning_effort=None,
                    error=None,
                    output_text="working",
                    started_at=now - timedelta(minutes=4),
                    updated_at=now - timedelta(minutes=3),
                    finished_at=None,
                    last_heartbeat_at=now - timedelta(minutes=3),
                    last_progress_event_at=now - timedelta(minutes=3),
                )
            )
            session.commit()
        engine.dispose()

        with orchestration_client(
            repo_root,
            settings=settings,
            app_sqlite_store=SqliteAppStore(db_path=settings.app_sqlite_path),
        ) as client:
            response = client.get("/orchestration/oats")

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["tasks"][0]["invocation"]["sessionId"] == "claude-task-missing"
        assert response.json()[0]["tasks"][0]["invocation"]["conversationPath"] is None


    def test_run_record_shapes_canonical_planner_and_task_links(self, tmp_path: Path) -> None:
        now = datetime.now(UTC)
        repo_root = tmp_path
        settings = _init_sqlite(repo_root)
        engine = create_engine(f"sqlite:///{settings.app_sqlite_path}")
        encoded_repo_root = str(repo_root).replace("/", "-")
        with Session(engine) as session:
            _insert_conversation_record(
                session,
                provider="codex",
                session_id="planner-1",
                project_path=f"codex:{encoded_repo_root}",
                route_slug="plan-ship-real-orchestration-run",
                started_at=now - timedelta(minutes=12),
            )
            _insert_conversation_record(
                session,
                provider="claude",
                session_id="executor-1",
                project_path=encoded_repo_root,
                route_slug="implement-ship-real-orchestration-run",
                started_at=now - timedelta(minutes=10),
            )
            session.commit()
        engine.dispose()

        shaped = _shape_run_record(
            StoredOatsRunRecord(
                path=repo_root / ".oats" / "runs" / "terminal.json",
                record=RunExecutionRecord(
                    run_id="run-with-links",
                    run_title="Ship real orchestration run",
                    repo_root=repo_root,
                    config_path=repo_root / ".oats" / "config.toml",
                    run_spec_path=repo_root / "runs" / "run.md",
                    mode="writable",
                    integration_branch="oats/overnight/run-with-links",
                    task_pr_target="oats/overnight/run-with-links",
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
                    tasks=[
                        TaskExecutionRecord(
                            task_id="task-api",
                            title="Implement route",
                            depends_on=[],
                            invocation=AgentInvocationResult(
                                agent="claude",
                                role="executor",
                                command=["claude", "run"],
                                cwd=repo_root,
                                prompt="implement route",
                                session_id="executor-1",
                                exit_code=0,
                                started_at=now - timedelta(minutes=10),
                                finished_at=now - timedelta(minutes=9),
                            ),
                        )
                    ],
                    recorded_at=now - timedelta(minutes=8),
                ),
            ),
            services=_services_stub(
                settings=settings,
                app_sqlite_store=SqliteAppStore(db_path=settings.app_sqlite_path),
            ),
        )

        assert shaped.response.planner is not None
        assert shaped.response.planner.conversation_path == (
            "/conversations/by-ref/plan-ship-real-orchestration-run--codex-planner-1"
        )
        assert shaped.response.tasks[0].invocation is not None
        assert shaped.response.tasks[0].invocation.conversation_path == (
            "/conversations/by-ref/implement-ship-real-orchestration-run--claude-executor-1"
        )

    def test_orchestration_oats_index_includes_feature_branch_and_task_prs(self, tmp_path: Path) -> None:
        repo_root = tmp_path
        state_path = repo_root / ".oats" / "runtime" / "oats-run-1" / "state.json"
        _write_model(state_path, _stacked_runtime_state(repo_root, "oats-run-1"))

        with orchestration_client(repo_root) as client:
            response = client.get("/orchestration/oats")

        assert response.status_code == 200
        payload = response.json()[0]
        assert payload["featureBranch"]["name"] == "oats/overnight/runtime-facts"
        assert payload["tasks"][0]["taskPr"]["mergeGateStatus"] == "awaiting_checks"
        assert payload["finalPr"]["reviewGateStatus"] == "awaiting_human"
        assert payload["tasks"][0]["operationHistory"][0]["kind"] == "pr_create"

    def test_orchestration_refresh_route_returns_updated_run(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_root = tmp_path
        state_path = repo_root / ".oats" / "runtime" / "oats-run-1" / "state.json"
        _write_model(state_path, _stacked_runtime_state(repo_root, "oats-run-1"))
        refreshed = _stacked_runtime_state(repo_root, "oats-run-1")
        refreshed.stack_status = "ready_for_final_review"

        monkeypatch.setattr(
            "helaicopter_api.router.orchestration.refresh_oats_run",
            lambda services, run_id: _runtime_response(refreshed, state_path),
        )

        with orchestration_client(repo_root) as client:
            response = client.post("/orchestration/oats/oats-run-1/refresh")

        assert response.status_code == 200
        assert response.json()["stackStatus"] in {"building", "ready_for_final_review"}

    def test_orchestration_resume_route_reuses_the_existing_run_stack(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_root = tmp_path
        state_path = repo_root / ".oats" / "runtime" / "oats-run-1" / "state.json"
        _write_model(state_path, _stacked_runtime_state(repo_root, "oats-run-1"))
        resumed = _stacked_runtime_state(repo_root, "oats-run-1")

        monkeypatch.setattr(
            "helaicopter_api.router.orchestration.resume_oats_run",
            lambda services, run_id: _runtime_response(resumed, state_path),
        )

        with orchestration_client(repo_root) as client:
            response = client.post("/orchestration/oats/oats-run-1/resume")

        assert response.status_code == 200
        assert response.json()["runId"] == "oats-run-1"
        assert response.json()["featureBranch"]["name"] == "oats/overnight/runtime-facts"

    def test_orchestration_payload_prefers_runtime_graph_over_terminal_record(self, tmp_path: Path) -> None:
        repo_root = tmp_path
        run_id = "oats-run-1"
        state_path = repo_root / ".oats" / "runtime" / run_id / "state.json"
        record_path = repo_root / ".oats" / "runs" / "runtime-terminal.json"
        _write_model(state_path, _stacked_runtime_state(repo_root, run_id))
        _write_model(
            record_path,
            RunExecutionRecord(
                run_id=run_id,
                run_title="Runtime should win",
                repo_root=repo_root,
                config_path=repo_root / ".oats" / "config.toml",
                run_spec_path=repo_root / "runs" / "runtime.md",
                mode="writable",
                integration_branch="oats/overnight/runtime-facts",
                task_pr_target="oats/overnight/runtime-facts",
                final_pr_target="main",
                recorded_at=datetime.now(UTC) - timedelta(minutes=5),
            ),
        )

        with orchestration_client(repo_root) as client:
            response = client.get("/orchestration/oats")

        assert response.status_code == 200
        payload = response.json()[0]
        assert payload["status"] == "running"
        assert payload["stackStatus"] == "awaiting_task_merge"

    def test_openapi_exposes_orchestration_route(self, tmp_path: Path) -> None:
        with orchestration_client(tmp_path) as client:
            response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        orchestration_get = schema["paths"]["/orchestration/oats"]["get"]
        orchestration_refresh = schema["paths"]["/orchestration/oats/{run_id}/refresh"]["post"]
        orchestration_resume = schema["paths"]["/orchestration/oats/{run_id}/resume"]["post"]
        assert orchestration_get["tags"] == ["orchestration"]
        assert orchestration_refresh["tags"] == ["orchestration"]
        assert orchestration_resume["tags"] == ["orchestration"]
        assert orchestration_get["responses"]["200"]["content"]["application/json"]["schema"]["items"][
            "$ref"
        ].endswith("/OrchestrationRunResponse")

        run_schema = schema["components"]["schemas"]["OrchestrationRunResponse"]
        task_schema = schema["components"]["schemas"]["OrchestrationTaskResponse"]
        assert "runId" in run_schema["properties"]
        assert "run_id" not in run_schema["properties"]
        assert "activeTaskId" in run_schema["properties"]
        assert "stackStatus" in run_schema["properties"]
        assert "featureBranch" in run_schema["properties"]
        assert "finalPr" in run_schema["properties"]
        assert "taskId" in task_schema["properties"]
        assert "task_id" not in task_schema["properties"]
        assert "taskPr" in task_schema["properties"]


def _stacked_runtime_state(repo_root: Path, run_id: str) -> RunRuntimeState:
    now = datetime.now(UTC)
    return RunRuntimeState(
        run_id=run_id,
        run_title="Runtime should win",
        repo_root=repo_root,
        config_path=repo_root / ".oats" / "config.toml",
        run_spec_path=repo_root / "runs" / "runtime.md",
        mode="writable",
        integration_branch="oats/overnight/runtime-facts",
        task_pr_target="oats/overnight/runtime-facts",
        final_pr_target="main",
        runtime_dir=repo_root / ".oats" / "runtime" / run_id,
        feature_branch=FeatureBranchSnapshot(
            name="oats/overnight/runtime-facts",
            base_branch="main",
        ),
        status="running",
        stack_status="awaiting_task_merge",
        active_task_id="task-api",
        started_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(seconds=10),
        heartbeat_at=now - timedelta(seconds=5),
        final_pr=FinalPullRequestSnapshot(
            number=42,
            state="open",
            review_gate_status="awaiting_human",
            base_branch="main",
            head_branch="oats/overnight/runtime-facts",
        ),
        tasks=[
            TaskRuntimeRecord(
                task_id="task-api",
                title="Implement route",
                depends_on=[],
                branch_name="oats/task/task-api",
                parent_branch="oats/overnight/runtime-facts",
                pr_base="oats/overnight/runtime-facts",
                agent="claude",
                status="running",
                attempts=2,
                task_pr=TaskPullRequestSnapshot(
                    number=11,
                    state="open",
                    merge_gate_status="awaiting_checks",
                    base_branch="oats/overnight/runtime-facts",
                    head_branch="oats/task/task-api",
                ),
                operation_history=[
                    OperationHistoryEntry(
                        kind="pr_create",
                        status="succeeded",
                    )
                ],
                invocation=InvocationRuntimeRecord(
                    agent="claude",
                    role="executor",
                    command=["claude", "run"],
                    cwd=repo_root,
                    prompt="implement route",
                    session_id="task-api-runtime",
                    started_at=now - timedelta(minutes=2),
                    last_heartbeat_at=now - timedelta(seconds=5),
                ),
            )
        ],
        final_record_path=repo_root / ".oats" / "runs" / "runtime-terminal.json",
    )


def _runtime_response(state: RunRuntimeState, state_path: Path):
    from helaicopter_api.application.orchestration import _shape_runtime_state
    from helaicopter_api.ports.orchestration import StoredOatsRuntimeState

    return _shape_runtime_state(StoredOatsRuntimeState(path=state_path, state=state)).response
