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
    """Refresh the GitHub PR state for an OATS stacked PR run.

    Resolves the runtime state for ``run_id``, calls the OATS ``refresh_run``
    helper to sync PR status from GitHub, and shapes the result into the
    standard orchestration run response.

    Args:
        services: Initialised backend services; ``services.settings.project_root``
            is used as the repository root.
        run_id: Identifier of the OATS run to refresh.

    Returns:
        Updated ``OrchestrationRunResponse`` reflecting the latest PR state.

    Raises:
        RuntimeError: If backend settings are not available on ``services``.
    """
    repo_root = _repo_root(services)
    state = resolve_runtime_state(repo_root, run_id=run_id)
    refreshed = refresh_run(state=state, github_client=_GhCliClient(repo_root))
    return _shape_runtime_response(refreshed)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def resume_oats_run(
    services: InstanceOf[BackendServices],
    run_id: str,
) -> OrchestrationRunResponse:
    """Resume a paused or stalled OATS stacked PR run.

    Calls the OATS ``resume_run`` helper which re-triggers the next pending
    task, then shapes the resulting runtime state into the standard
    orchestration run response.

    Args:
        services: Initialised backend services; ``services.settings.project_root``
            is used as the repository root.
        run_id: Identifier of the OATS run to resume.

    Returns:
        Updated ``OrchestrationRunResponse`` after the resume operation.

    Raises:
        RuntimeError: If backend settings are not available on ``services``.
    """
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
