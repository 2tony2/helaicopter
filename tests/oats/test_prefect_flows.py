from __future__ import annotations

from pathlib import Path
import json

from oats.prefect.flows import execute_compiled_flow_graph, run_compiled_oats_flow
from oats.prefect.models import PrefectFlowPayload, PrefectTaskEdge, PrefectTaskGraph, PrefectTaskNode


def test_execute_compiled_flow_graph_preserves_dependency_order_and_writes_metadata(
    tmp_path: Path,
) -> None:
    payload = _sample_payload(tmp_path)
    execution_order: list[str] = []

    def executor(
        task_node: PrefectTaskNode,
        upstream_results: dict[str, dict[str, object]],
        attempt: int,
    ) -> dict[str, object]:
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
        task_node: PrefectTaskNode,
        upstream_results: dict[str, dict[str, object]],
        attempt: int,
    ) -> dict[str, object]:
        del task_node
        del upstream_results
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
        task_node: PrefectTaskNode,
        upstream_results: dict[str, dict[str, object]],
        attempt: int,
    ) -> dict[str, object]:
        del upstream_results
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
            PrefectTaskNode(task_id="plan", title="Plan", prompt="Write a plan."),
            PrefectTaskNode(
                task_id="build",
                title="Build",
                prompt="Implement the runtime.",
                depends_on=["plan"],
            ),
            PrefectTaskNode(
                task_id="verify",
                title="Verify",
                prompt="Run validation.",
                depends_on=["plan", "build"],
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
        tasks=[PrefectTaskNode(task_id="plan", title="Plan", prompt="Write a plan.")],
        task_graph=PrefectTaskGraph(nodes=[], edges=[]),
    )
