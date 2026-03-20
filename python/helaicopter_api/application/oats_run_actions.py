"""Mutating runtime actions for OATS stacked PR runs."""

from __future__ import annotations

from pathlib import Path

from pydantic import ConfigDict, InstanceOf, validate_call

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.orchestration import StoredOatsRuntimeState
from helaicopter_api.schema.orchestration import OrchestrationRunResponse
from oats.cli import _GhCliClient
from oats.pr import refresh_run, resume_run
from oats.runtime_state import resolve_runtime_state


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def refresh_oats_run(
    services: InstanceOf[BackendServices],
    run_id: str,
) -> OrchestrationRunResponse:
    repo_root = _repo_root(services)
    state = resolve_runtime_state(repo_root, run_id=run_id)
    refreshed = refresh_run(state=state, github_client=_GhCliClient(repo_root))
    return _shape_runtime_response(refreshed)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def resume_oats_run(
    services: InstanceOf[BackendServices],
    run_id: str,
) -> OrchestrationRunResponse:
    repo_root = _repo_root(services)
    resumed = resume_run(run_id=run_id, repo_root=repo_root, github_client=_GhCliClient(repo_root))
    return _shape_runtime_response(resumed)


def _shape_runtime_response(state) -> OrchestrationRunResponse:
    from helaicopter_api.application.orchestration import _shape_runtime_state

    return _shape_runtime_state(
        StoredOatsRuntimeState(path=state.runtime_dir / "state.json", state=state)
    ).response


def _repo_root(services: BackendServices) -> Path:
    settings = getattr(services, "settings", None)
    if settings is None:
        raise RuntimeError("Backend settings are not available")
    return settings.project_root
