from __future__ import annotations

from pathlib import Path
import json
from types import SimpleNamespace

import pytest
from prefect.testing.utilities import prefect_test_harness

from oats.prefect.flows import execute_compiled_flow_graph, run_compiled_oats_flow
from oats.prefect.models import PrefectFlowPayload, PrefectTaskEdge, PrefectTaskGraph, PrefectTaskNode
from oats.prefect.tasks import CompiledTaskResult


@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    with prefect_test_harness():
        yield


def test_execute_compiled_flow_graph_preserves_dependency_order_and_writes_metadata(
    tmp_path: Path,
) -> None:
    payload = _sample_payload(tmp_path)
    execution_order: list[str] = []

    def executor(
        payload: PrefectFlowPayload,
        task_node: PrefectTaskNode,
        upstream_results: dict[str, dict[str, object]],
        attempt: int,
        worktree_path: Path,
    ) -> dict[str, object]:
        del payload, worktree_path
        execution_order.append(task_node.task_id)
        return {
            "task_id": task_node.task_id,
            "attempt": attempt,
            "upstream_task_ids": sorted(upstream_results),
        }

    result = execute_compiled_flow_graph(
        payload,
        executor=executor,
        flow_run_id="flow-run-123",
        flow_run_name="Prefect Test Run",
    )

    assert execution_order == ["plan", "build", "verify"]
    assert result.execution_order == ["plan", "build", "verify"]

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["flow_run_id"] == "flow-run-123"
    assert metadata["flow_run_name"] == "Prefect Test Run"
    assert metadata["run_title"] == payload.run_title
    assert metadata["artifact_root"].endswith("/.oats/prefect/flow-runs/flow-run-123")

    verify_checkpoint = json.loads(
        (result.artifact_root / "tasks" / "verify.json").read_text(encoding="utf-8")
    )
    assert verify_checkpoint["status"] == "completed"
    assert verify_checkpoint["attempt"] == 1
    assert verify_checkpoint["upstream_task_ids"] == ["build", "plan"]


def test_execute_compiled_flow_graph_retries_without_corrupting_local_artifacts(
    tmp_path: Path,
) -> None:
    payload = _single_task_payload(tmp_path)
    attempts: list[int] = []

    def flaky_executor(
        payload: PrefectFlowPayload,
        task_node: PrefectTaskNode,
        upstream_results: dict[str, dict[str, object]],
        attempt: int,
        worktree_path: Path,
    ) -> dict[str, object]:
        del payload, task_node, upstream_results, worktree_path
        attempts.append(attempt)
        if attempt == 1:
            raise RuntimeError("transient failure")
        return {"attempt": attempt}

    result = execute_compiled_flow_graph(
        payload,
        executor=flaky_executor,
        flow_run_id="flow-run-retry",
        max_retries=1,
    )

    assert attempts == [1, 2]
    checkpoint = json.loads((result.artifact_root / "tasks" / "plan.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "completed"
    assert checkpoint["attempt"] == 2

    first_attempt = json.loads(
        (result.artifact_root / "attempts" / "plan" / "attempt-1.json").read_text(encoding="utf-8")
    )
    second_attempt = json.loads(
        (result.artifact_root / "attempts" / "plan" / "attempt-2.json").read_text(encoding="utf-8")
    )
    assert first_attempt["status"] == "failed"
    assert first_attempt["error"] == "transient failure"
    assert second_attempt["status"] == "completed"


def test_shared_prefect_flow_entrypoint_accepts_serialized_payload(tmp_path: Path) -> None:
    payload = _single_task_payload(tmp_path)
    seen: list[str] = []

    def executor(
        payload: PrefectFlowPayload,
        task_node: PrefectTaskNode,
        upstream_results: dict[str, dict[str, object]],
        attempt: int,
        worktree_path: Path,
    ) -> dict[str, object]:
        del payload, upstream_results, worktree_path
        seen.append(f"{task_node.task_id}:{attempt}")
        return {"attempt": attempt}

    result = run_compiled_oats_flow.fn(
        payload=payload.model_dump(mode="json"),
        flow_run_id="flow-run-entrypoint",
        executor=executor,
    )

    assert seen == ["plan:1"]
    assert result.flow_run_id == "flow-run-entrypoint"
    assert result.execution_order == ["plan"]


def test_execute_compiled_flow_graph_submits_prefect_tasks_for_each_node(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = _sample_payload(tmp_path)
    submissions: list[tuple[str, tuple[str, ...]]] = []

    class FakePrefectTask:
        def submit(
            self,
            payload: PrefectFlowPayload,
            task_node: PrefectTaskNode,
            *,
            upstream_results,
            artifact_store,
            executor=None,
            attempt=None,
            wait_for=(),
        ):
            del payload, artifact_store, executor, attempt
            submissions.append(
                (
                    task_node.task_id,
                    tuple(
                        future.result().task_id
                        for future in wait_for
                    ),
                )
            )
            result = CompiledTaskResult(
                task_id=task_node.task_id,
                attempt=1,
                status="completed",
                upstream_task_ids=sorted(upstream_results),
                result={
                    "task_id": task_node.task_id,
                    "upstream_task_ids": sorted(upstream_results),
                },
            )
            return SimpleNamespace(result=lambda: result)

    monkeypatch.setattr("oats.prefect.flows.prefect_compiled_task", FakePrefectTask())

    result = run_compiled_oats_flow(
        payload,
        flow_run_id="flow-run-prefect-submit",
    )

    assert submissions == [
        ("plan", ()),
        ("build", ("plan",)),
        ("verify", ("plan", "build")),
    ]
    assert result.execution_order == ["plan", "build", "verify"]


def test_run_compiled_oats_flow_uses_oats_executor_for_deployed_tasks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = _sample_payload(tmp_path)
    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()
    invocations: list[dict[str, object]] = []

    class FakeAgentResult:
        agent = "codex"
        session_id = "session-123"
        output_text = "implemented"
        exit_code = 0
        timed_out = False
        raw_stderr = ""

    monkeypatch.setattr(
        "oats.prefect.tasks.load_repo_config",
        lambda _path: _repo_config_stub(),
    )
    monkeypatch.setattr(
        "oats.prefect.tasks.prepare_task_worktree",
        lambda _payload, _task_node: SimpleNamespace(worktree_path=worktree_path),
    )

    def fake_invoke_agent(**kwargs):
        invocations.append(kwargs)
        return FakeAgentResult()

    monkeypatch.setattr("oats.prefect.tasks.invoke_agent", fake_invoke_agent)

    result = run_compiled_oats_flow(
        payload,
        flow_run_id="flow-run-agent-exec",
    )

    assert [entry["cwd"] for entry in invocations] == [worktree_path, worktree_path, worktree_path]
    assert len(invocations) == 3
    assert "Implement the task now in the current worktree." in str(invocations[0]["prompt"])
    assert invocations[0]["agent_name"] == "codex"
    assert invocations[0]["model"] == "gpt-5"
    assert invocations[0]["reasoning_effort"] == "high"
    assert invocations[1]["agent_name"] == "claude"
    assert invocations[1]["model"] == "claude-sonnet-4-5"
    assert invocations[1]["reasoning_effort"] == "max"
    assert result.execution_order == ["plan", "build", "verify"]
    assert result.task_results["plan"].result["session_id"] == "session-123"
    assert result.task_results["plan"].result["model"] == "gpt-5"
    assert result.task_results["plan"].result["reasoning_effort"] == "high"


def _sample_payload(tmp_path: Path) -> PrefectFlowPayload:
    repo_root = tmp_path
    return PrefectFlowPayload(
        run_title="Run: Prefect Flow Runtime",
        source_path=repo_root / "examples" / "prefect_flow_runtime.md",
        repo_root=repo_root,
        config_path=repo_root / ".oats" / "config.toml",
        repo_base_branch="main",
        worktree_dir=".oats-worktrees",
        default_concurrency=2,
        tasks=[
            PrefectTaskNode(
                task_id="plan",
                title="Plan",
                prompt="Write a plan.",
                agent="codex",
                model="gpt-5",
                reasoning_effort="high",
            ),
            PrefectTaskNode(
                task_id="build",
                title="Build",
                prompt="Implement the runtime.",
                depends_on=["plan"],
                agent="claude",
                model="claude-sonnet-4-5",
                reasoning_effort="max",
            ),
            PrefectTaskNode(
                task_id="verify",
                title="Verify",
                prompt="Run validation.",
                depends_on=["plan", "build"],
                agent="codex",
            ),
        ],
        task_graph=PrefectTaskGraph(
            nodes=[],
            edges=[
                PrefectTaskEdge(upstream_task_id="plan", downstream_task_id="build"),
                PrefectTaskEdge(upstream_task_id="plan", downstream_task_id="verify"),
                PrefectTaskEdge(upstream_task_id="build", downstream_task_id="verify"),
            ],
        ),
    )


def _single_task_payload(tmp_path: Path) -> PrefectFlowPayload:
    repo_root = tmp_path
    return PrefectFlowPayload(
        run_title="Run: Retry Safe Task",
        source_path=repo_root / "examples" / "prefect_retry_safe.md",
        repo_root=repo_root,
        config_path=repo_root / ".oats" / "config.toml",
        repo_base_branch="main",
        worktree_dir=".oats-worktrees",
        default_concurrency=1,
        tasks=[PrefectTaskNode(task_id="plan", title="Plan", prompt="Write a plan.", agent="codex")],
        task_graph=PrefectTaskGraph(nodes=[], edges=[]),
    )


def _repo_config_stub():
    from oats.models import RepoConfig

    return RepoConfig.model_validate(
        {
            "agent": {
                "codex": {"command": "codex", "args": ["exec"]},
                "claude": {"command": "claude", "args": []},
            }
        }
    )
