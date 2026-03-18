"""Concrete plan reader – loads markdown files from ``~/.claude/plans/``."""

from __future__ import annotations

from helaicopter_api.adapters.claude_fs.raw import ClaudeArtifactStore, RawArtifact
from helaicopter_api.ports.claude_fs import PlanFile


class FilePlanReader:
    """Reads plan markdown files from ``~/.claude/plans/``."""

    def __init__(self, artifact_store: ClaudeArtifactStore) -> None:
        self._artifact_store = artifact_store

    # -- Port implementation -------------------------------------------------

    def list_plans(self) -> list[PlanFile]:
        results: list[PlanFile] = []
        for path in self._artifact_store.list_plan_files():
            plan = self._read_file(self._artifact_store.read_plan_file(path.stem))
            if plan is not None:
                results.append(plan)
        return results

    def read_plan(self, slug: str) -> PlanFile | None:
        return self._read_file(self._artifact_store.read_plan_file(slug))

    # -- Internal ------------------------------------------------------------

    def _read_file(self, artifact: RawArtifact | None) -> PlanFile | None:
        if artifact is None:
            return None
        return PlanFile(
            slug=artifact.path.stem,
            path=str(artifact.path),
            content=artifact.content,
            modified_at=artifact.modified_at,
        )
