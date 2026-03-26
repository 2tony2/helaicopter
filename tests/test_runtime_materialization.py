from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from oats.graph import GraphMutation, TaskGraph, TaskKind, TaskNode
from oats.models import OperationHistoryEntry, RunRuntimeState, TaskRuntimeRecord


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_jsonl(path: Path, payloads: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(payload, default=str) for payload in payloads) + "\n",
        encoding="utf-8",
    )


def _build_runtime_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / ".oats" / "runtime" / "run_1"
    now = datetime.now(UTC)
    graph = TaskGraph()
    graph.add_node(
        TaskNode(
            task_id="task_auth",
            kind=TaskKind.IMPLEMENTATION,
            title="Implement auth",
            status="running",
            agent="claude",
            model="claude-sonnet-4-6",
        )
    )
    state = RunRuntimeState(
        run_id="run_1",
        run_title="Runtime truth",
        repo_root=tmp_path,
        config_path=tmp_path / ".oats" / "config.toml",
        run_spec_path=tmp_path / "runs" / "runtime.md",
        mode="writable",
        integration_branch="oats/phase2/runtime",
        task_pr_target="oats/phase2/runtime",
        final_pr_target="main",
        runtime_dir=run_dir,
        status="running",
        started_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(seconds=30),
        heartbeat_at=now - timedelta(seconds=5),
        tasks=[
            TaskRuntimeRecord(
                task_id="task_auth",
                title="Implement auth",
                depends_on=[],
                branch_name="oats/task/task_auth",
                parent_branch="main",
                pr_base="main",
                agent="claude",
                status="running",
                attempts=2,
            )
        ],
        graph=graph,
        graph_mutations=[
            GraphMutation(
                mutation_id="mut_1",
                kind="pause_run",
                discovered_by="operator",
                source="operator",
                nodes_added=["task_auth"],
            )
        ],
        operation_history=[
            OperationHistoryEntry(
                kind="resume",
                status="succeeded",
                details={"task_id": "task_auth"},
            )
        ],
    )
    (run_dir).mkdir(parents=True, exist_ok=True)
    (run_dir / "state.json").write_text(state.model_dump_json(indent=2), encoding="utf-8")
    _write_jsonl(
        run_dir / "graph_mutations.jsonl",
        [
            {
                "mutation_id": "mut_1",
                "kind": "pause_run",
                "discovered_by": "operator",
                "source": "operator",
                "timestamp": now.isoformat(),
                "nodes_added": ["task_auth"],
                "edges_added": [],
            }
        ],
    )
    _write_jsonl(
        tmp_path / ".oats" / "runtime" / "dispatch_history.jsonl",
        [
            {
                "run_id": "run_1",
                "task_id": "task_auth",
                "worker_id": "wkr_1",
                "provider": "claude",
                "model": "claude-sonnet-4-6",
                "dispatched_at": now.isoformat(),
            }
        ],
    )
    _write_json(
        run_dir / "results" / "task_auth.json",
        {
            "task_id": "task_auth",
            "run_id": "run_1",
            "worker_id": "wkr_1",
            "status": "succeeded",
            "duration_seconds": 42.0,
            "attempt_id": "att_2",
            "branch_name": "oats/task/task_auth",
            "commit_sha": "abc123",
            "error_summary": None,
            "provider_session_id": "sess_provider_1",
            "session_reused": True,
            "session_status_after_task": "ready",
        },
    )
    return run_dir


def test_materialize_runtime_run_reads_state_results_and_graph_mutations(tmp_path: Path) -> None:
    from helaicopter_api.application.runtime_materialization import materialize_runtime_run

    run_dir = _build_runtime_dir(tmp_path)

    materialized = materialize_runtime_run(run_dir)

    assert materialized.run_id == "run_1"
    assert materialized.graph_mutations
    assert materialized.graph_mutations[0].source == "operator"
    assert materialized.task_attempts[0].task_id == "task_auth"
    assert materialized.task_attempts[0].attempt_id == "att_2"
    assert materialized.task_attempts[0].provider_session_id == "sess_provider_1"
    assert materialized.task_attempts[0].session_reused is True
    assert materialized.task_attempts[0].session_status_after_task == "ready"
    assert materialized.dispatch_events[0].worker_id == "wkr_1"
    assert [action.action for action in materialized.operator_actions] == ["pause", "resume"]


def test_materialize_runtime_run_prefers_runtime_artifacts_over_missing_sqlite_facts(tmp_path: Path) -> None:
    from helaicopter_api.application.runtime_materialization import materialize_runtime_run

    run_dir = _build_runtime_dir(tmp_path)

    materialized = materialize_runtime_run(run_dir)

    assert materialized.source == "runtime"
