from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator
from helaicopter_domain.vocab import ProviderName


class CanonicalExecutionHints(BaseModel):
    repo_base_branch: str
    worktree_dir: str
    default_concurrency: int = Field(ge=1)


class CanonicalTaskDefinition(BaseModel):
    task_id: str
    title: str
    prompt: str
    depends_on: list[str] = Field(default_factory=list)
    agent: ProviderName | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)


class CanonicalRunDefinition(BaseModel):
    title: str
    source_path: Path
    repo_root: Path
    config_path: Path
    default_validation_commands: list[str] = Field(default_factory=list)
    execution: CanonicalExecutionHints
    tasks: list[CanonicalTaskDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_task_ids(self) -> "CanonicalRunDefinition":
        seen: set[str] = set()
        duplicates: list[str] = []

        for task in self.tasks:
            if task.task_id in seen:
                duplicates.append(task.task_id)
            seen.add(task.task_id)

        if duplicates:
            joined = ", ".join(sorted(set(duplicates)))
            raise ValueError(f"Duplicate canonical task ids found: {joined}")
        return self
