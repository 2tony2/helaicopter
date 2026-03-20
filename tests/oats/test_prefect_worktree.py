from __future__ import annotations

from pathlib import Path
import subprocess

from oats.prefect.compiler import compile_run_definition
from oats.prefect.worktree import (
    prepare_task_worktree,
    remove_task_worktree,
    resolve_task_worktree_path,
)
from oats.run_definition import (
    CanonicalExecutionHints,
    CanonicalRunDefinition,
    CanonicalTaskDefinition,
)


def test_prepare_task_worktree_is_idempotent_and_derives_branches(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    run_definition = _sample_run_definition(tmp_path)
    payload = compile_run_definition(run_definition, _repo_config()).flow_payload
    task_node = payload.tasks[0]

    first = prepare_task_worktree(payload, task_node)
    second = prepare_task_worktree(payload, task_node)

    assert first == second
    assert first.integration_branch == "oats/overnight/run-prefect-worktree-smoke"
    assert first.task_branch == "oats/task/plan"
    assert first.worktree_path == resolve_task_worktree_path(payload, task_node)
    assert first.worktree_path.is_dir()
    assert (first.worktree_path / ".git").exists()
    assert _git(tmp_path, "branch", "--show-current") == "main"
    assert _git(first.worktree_path, "branch", "--show-current") == first.task_branch
    assert _git(first.worktree_path, "rev-parse", "--abbrev-ref", "HEAD@{upstream}") == first.integration_branch


def test_prepare_task_worktree_is_safe_to_rerun_when_worktree_already_exists(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    run_definition = _sample_run_definition(tmp_path)
    payload = compile_run_definition(run_definition, _repo_config()).flow_payload
    task_node = payload.tasks[0]

    context = prepare_task_worktree(payload, task_node)
    marker = context.worktree_path / "rerun-marker.txt"
    marker.write_text("keep me", encoding="utf-8")

    rerun = prepare_task_worktree(payload, task_node)

    assert rerun == context
    assert marker.read_text(encoding="utf-8") == "keep me"
    assert _git(context.worktree_path, "status", "--short") == "?? rerun-marker.txt"


def test_compiled_payload_attaches_repo_execution_context_for_each_task(tmp_path: Path) -> None:
    deployment = compile_run_definition(_sample_run_definition(tmp_path), _repo_config())
    plan_task, verify_task = deployment.flow_payload.tasks

    assert plan_task.repo_context is not None
    assert plan_task.repo_context.integration_branch == "oats/overnight/run-prefect-worktree-smoke"
    assert plan_task.repo_context.parent_branch == "oats/overnight/run-prefect-worktree-smoke"
    assert plan_task.repo_context.pr_base == "oats/overnight/run-prefect-worktree-smoke"
    assert plan_task.repo_context.task_branch == "oats/task/plan"
    assert plan_task.repo_context.worktree_path == Path(".oats-worktrees/run-prefect-worktree-smoke/plan")
    assert plan_task.branch_strategy == "feature_base"
    assert plan_task.initial_task_status == "pending"
    assert verify_task.repo_context is not None
    assert verify_task.repo_context.parent_branch == "oats/task/plan"
    assert verify_task.repo_context.pr_base == "oats/task/plan"
    assert verify_task.repo_context.task_branch == "oats/task/verify"
    assert verify_task.repo_context.worktree_path == Path(".oats-worktrees/run-prefect-worktree-smoke/verify")
    assert verify_task.branch_strategy == "single_parent"
    assert verify_task.initial_task_status == "pending"


def test_remove_task_worktree_is_safe_when_repeated(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    payload = compile_run_definition(_sample_run_definition(tmp_path), _repo_config()).flow_payload
    task_node = payload.tasks[0]

    context = prepare_task_worktree(payload, task_node)

    remove_task_worktree(context)
    remove_task_worktree(context)

    assert not context.worktree_path.exists()


def _sample_run_definition(repo_root: Path) -> CanonicalRunDefinition:
    return CanonicalRunDefinition(
        title="Run: Prefect Worktree Smoke",
        source_path=repo_root / "examples" / "prefect_worktree_smoke.md",
        repo_root=repo_root,
        config_path=repo_root / ".oats" / "config.toml",
        default_validation_commands=["uv run --group dev pytest -q"],
        execution=CanonicalExecutionHints(
            repo_base_branch="main",
            worktree_dir=".oats-worktrees",
            default_concurrency=2,
        ),
        tasks=[
            CanonicalTaskDefinition(task_id="plan", title="Plan", prompt="Write a plan."),
            CanonicalTaskDefinition(
                task_id="verify",
                title="Verify",
                prompt="Run validation.",
                depends_on=["plan"],
            ),
        ],
    )


def _repo_config():
    from oats.models import RepoConfig

    return RepoConfig.model_validate(
        {
            "agent": {
                "codex": {"command": "codex", "args": ["exec"]},
                "claude": {"command": "claude", "args": []},
            }
        }
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-b", "main")
    _git(repo_root, "config", "user.name", "Test User")
    _git(repo_root, "config", "user.email", "test@example.com")
    (repo_root / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "initial")


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
