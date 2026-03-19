from __future__ import annotations

from pathlib import Path
import subprocess

from pydantic import BaseModel

from oats.prefect.models import PrefectFlowPayload, PrefectTaskNode, PrefectTaskRepoContext
from oats.pr import build_integration_branch_name, build_task_branch_name, slugify_branch_component


class PreparedTaskWorktree(BaseModel):
    repo_root: Path
    integration_branch: str
    task_branch: str
    worktree_path: Path


def build_task_repo_context(
    *,
    run_title: str,
    task_id: str,
    worktree_dir: str,
    task_branch_prefix: str = "oats/task/",
    integration_branch_prefix: str = "oats/overnight/",
) -> PrefectTaskRepoContext:
    run_slug = slugify_branch_component(run_title, fallback="run")
    task_slug = slugify_branch_component(task_id, fallback="task")
    return PrefectTaskRepoContext(
        integration_branch=build_integration_branch_name(integration_branch_prefix, run_title),
        task_branch=build_task_branch_name(task_branch_prefix, task_id),
        worktree_path=Path(worktree_dir) / run_slug / task_slug,
    )


def resolve_task_worktree_path(
    payload: PrefectFlowPayload,
    task_node: PrefectTaskNode,
) -> Path:
    repo_context = task_node.repo_context or build_task_repo_context(
        run_title=payload.run_title,
        task_id=task_node.task_id,
        worktree_dir=payload.worktree_dir,
    )
    return payload.repo_root / repo_context.worktree_path


def prepare_task_worktree(
    payload: PrefectFlowPayload,
    task_node: PrefectTaskNode,
) -> PreparedTaskWorktree:
    repo_context = task_node.repo_context or build_task_repo_context(
        run_title=payload.run_title,
        task_id=task_node.task_id,
        worktree_dir=payload.worktree_dir,
    )
    task_node.repo_context = repo_context

    worktree_path = payload.repo_root / repo_context.worktree_path
    if not _is_git_repository(payload.repo_root):
        return PreparedTaskWorktree(
            repo_root=payload.repo_root,
            integration_branch=repo_context.integration_branch,
            task_branch=repo_context.task_branch,
            worktree_path=worktree_path,
        )

    _ensure_local_branch(
        repo_root=payload.repo_root,
        branch_name=repo_context.integration_branch,
        start_point=payload.repo_base_branch,
    )

    if worktree_path.exists():
        current_branch = _git(worktree_path, "branch", "--show-current")
        if current_branch != repo_context.task_branch:
            raise RuntimeError(
                f"Existing worktree at {worktree_path} is on branch {current_branch!r}, "
                f"expected {repo_context.task_branch!r}"
            )
    else:
        if _local_branch_exists(payload.repo_root, repo_context.task_branch):
            _git(payload.repo_root, "worktree", "add", str(worktree_path), repo_context.task_branch)
        else:
            _git(
                payload.repo_root,
                "worktree",
                "add",
                "-b",
                repo_context.task_branch,
                str(worktree_path),
                repo_context.integration_branch,
            )

    _set_branch_upstream(
        worktree_path=worktree_path,
        task_branch=repo_context.task_branch,
        upstream_branch=repo_context.integration_branch,
    )
    return PreparedTaskWorktree(
        repo_root=payload.repo_root,
        integration_branch=repo_context.integration_branch,
        task_branch=repo_context.task_branch,
        worktree_path=worktree_path,
    )


def remove_task_worktree(context: PreparedTaskWorktree) -> None:
    if context.worktree_path.exists():
        _git(context.repo_root, "worktree", "remove", "--force", str(context.worktree_path))
    if _local_branch_exists(context.repo_root, context.task_branch):
        _git(context.repo_root, "branch", "-D", context.task_branch)


def _ensure_local_branch(
    *,
    repo_root: Path,
    branch_name: str,
    start_point: str,
) -> None:
    if _local_branch_exists(repo_root, branch_name):
        return
    _git(repo_root, "branch", branch_name, start_point)


def _local_branch_exists(repo_root: Path, branch_name: str) -> bool:
    return bool(_git(repo_root, "branch", "--list", branch_name))


def _set_branch_upstream(
    *,
    worktree_path: Path,
    task_branch: str,
    upstream_branch: str,
) -> None:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(worktree_path),
            "branch",
            "--set-upstream-to",
            upstream_branch,
            task_branch,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 and "already exists" not in completed.stderr.lower():
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())


def _is_git_repository(path: Path) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
