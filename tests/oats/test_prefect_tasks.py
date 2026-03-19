from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from oats.models import AgentInvocationResult
from oats.prefect.artifacts import LocalArtifactCheckpointStore
from oats.prefect.models import PrefectFlowPayload, PrefectTaskEdge, PrefectTaskGraph, PrefectTaskNode
from oats.prefect.tasks import execute_compiled_task_attempt


def test_execute_compiled_task_attempt_persists_live_progress_checkpoint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = _payload(tmp_path)
    task_node = payload.tasks[0]
    artifact_store = LocalArtifactCheckpointStore(
        payload=payload,
        flow_run_id="flow-run-live-progress",
        flow_run_name="Live Progress",
    )
    artifact_store.initialize()
    monkeypatch.setattr(
        "oats.prefect.tasks.load_repo_config",
        lambda _path: SimpleNamespace(agent={"codex": SimpleNamespace(command="codex", args=["exec"])}),
    )
    monkeypatch.setattr(
        "oats.prefect.tasks.prepare_task_worktree",
        lambda _payload, _task_node: SimpleNamespace(worktree_path=tmp_path / "worktree"),
    )

    def fake_invoke_agent(**kwargs):
        kwargs["on_progress"](
            {
                "session_id": "thread-123",
                "session_id_field": "thread_id",
                "output_text": "Implementing the shared layout cleanup.",
            }
        )
        kwargs["on_heartbeat"]()
        return AgentInvocationResult(
            agent="codex",
            role="executor",
            command=["codex", "exec"],
            cwd=kwargs["cwd"],
            prompt=kwargs["prompt"],
            session_id="thread-123",
            session_id_field="thread_id",
            output_text="Implementing the shared layout cleanup.",
            raw_stdout="",
            raw_stderr="",
            exit_code=0,
        )

    monkeypatch.setattr("oats.prefect.tasks.invoke_agent", fake_invoke_agent)

    execute_compiled_task_attempt(
        payload,
        task_node,
        upstream_results={},
        artifact_store=artifact_store,
        attempt=1,
    )

    checkpoint = json.loads(
        (artifact_store.paths.tasks_dir / f"{task_node.task_id}.json").read_text(encoding="utf-8")
    )
    assert checkpoint["status"] == "completed"
    assert checkpoint["session_id"] == "thread-123"
    assert checkpoint["session_id_field"] == "thread_id"
    assert checkpoint["output_text"] == "Implementing the shared layout cleanup."
    assert checkpoint["last_heartbeat_at"] is not None
    assert checkpoint["last_progress_event_at"] is not None


def test_execute_compiled_task_attempt_uses_dangerous_bypass_for_writable_runs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = _payload(tmp_path)
    task_node = payload.tasks[0]
    artifact_store = LocalArtifactCheckpointStore(
        payload=payload,
        flow_run_id="flow-run-permissions",
        flow_run_name="Permissions",
    )
    artifact_store.initialize()
    monkeypatch.setattr(
        "oats.prefect.tasks.load_repo_config",
        lambda _path: SimpleNamespace(agent={"codex": SimpleNamespace(command="codex", args=["exec"])}),
    )
    monkeypatch.setattr(
        "oats.prefect.tasks.prepare_task_worktree",
        lambda _payload, _task_node: SimpleNamespace(worktree_path=tmp_path / "worktree"),
    )

    captured: dict[str, object] = {}

    def fake_invoke_agent(**kwargs):
        captured.update(kwargs)
        return AgentInvocationResult(
            agent="codex",
            role="executor",
            command=["codex", "exec"],
            cwd=kwargs["cwd"],
            prompt=kwargs["prompt"],
            session_id="thread-456",
            session_id_field="thread_id",
            output_text="Running with full permissions.",
            raw_stdout="",
            raw_stderr="",
            exit_code=0,
        )

    monkeypatch.setattr("oats.prefect.tasks.invoke_agent", fake_invoke_agent)

    execute_compiled_task_attempt(
        payload,
        task_node,
        upstream_results={},
        artifact_store=artifact_store,
        attempt=1,
    )

    assert captured["read_only"] is False
    assert captured["dangerous_bypass"] is True


def _payload(tmp_path: Path) -> PrefectFlowPayload:
    task = PrefectTaskNode(
        task_id="frontend_cleanup",
        title="Frontend Cleanup",
        prompt="Tighten the shared frontend layout system.",
        agent="codex",
        model="gpt-5",
        reasoning_effort="high",
    )
    return PrefectFlowPayload(
        run_title="Run: Live Progress",
        source_path=tmp_path / "examples" / "live_progress.md",
        repo_root=tmp_path,
        config_path=tmp_path / ".oats" / "config.toml",
        repo_base_branch="main",
        worktree_dir=".oats-worktrees",
        default_concurrency=1,
        tasks=[task],
        task_graph=PrefectTaskGraph(
            nodes=[task],
            edges=[PrefectTaskEdge(upstream_task_id="frontend_cleanup", downstream_task_id="frontend_cleanup")][
                :0
            ],
        ),
    )
