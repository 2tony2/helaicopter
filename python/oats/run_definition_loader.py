from __future__ import annotations

from pathlib import Path

from oats.parser import parse_run_spec
from oats.repo_config import find_repo_config, load_repo_config
from oats.run_definition import (
    CanonicalExecutionHints,
    CanonicalRunDefinition,
    CanonicalTaskDefinition,
)


class UnsupportedRunDefinitionInputError(ValueError):
    """Raised when a run-definition input format is not supported."""


def load_run_definition(
    run_spec_path: Path,
    *,
    repo_root: Path | None = None,
) -> CanonicalRunDefinition:
    resolved_run_spec_path = run_spec_path.resolve()
    _ensure_markdown_run_spec(resolved_run_spec_path)

    config_search_root = repo_root.resolve() if repo_root is not None else resolved_run_spec_path.parent
    config_path = find_repo_config(config_search_root)
    config = load_repo_config(config_path)
    run_spec = parse_run_spec(resolved_run_spec_path)
    repo_path = config_path.parent.parent.resolve()

    return CanonicalRunDefinition(
        title=run_spec.title,
        source_path=run_spec.source_path.resolve(),
        repo_root=repo_path,
        config_path=config_path.resolve(),
        default_validation_commands=list(config.validation.commands),
        execution=CanonicalExecutionHints(
            repo_base_branch=config.repo.base_branch,
            worktree_dir=config.repo.worktree_dir,
            default_concurrency=config.repo.default_concurrency,
        ),
        tasks=[
            CanonicalTaskDefinition(
                task_id=task.id,
                title=_task_title(task.id, task.title),
                prompt=task.prompt,
                depends_on=list(task.depends_on),
                agent=task.agent,
                model=task.model,
                reasoning_effort=task.reasoning_effort,
                acceptance_criteria=list(task.acceptance_criteria),
                notes=list(task.notes),
                validation_commands=list(
                    task.validation_override or config.validation.commands
                ),
            )
            for task in run_spec.tasks
        ],
    )


def _task_title(task_id: str, explicit_title: str | None) -> str:
    if explicit_title:
        return explicit_title
    normalized = task_id.replace("_", " ").replace("-", " ").strip()
    return normalized.title() if normalized else task_id


def _ensure_markdown_run_spec(path: Path) -> Path:
    if path.suffix.lower() != ".md":
        raise UnsupportedRunDefinitionInputError(
            f"Markdown run specs are the only supported input in this rollout: {path}"
        )
    return path
