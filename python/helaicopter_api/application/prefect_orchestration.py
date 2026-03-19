"""Application-layer shaping for Prefect orchestration endpoints."""

from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.prefect import (
    PrefectDeploymentRecord,
    PrefectFlowRunRecord,
    PrefectOatsPayload,
    PrefectWorkPoolRecord,
    PrefectWorkerRecord,
)
from helaicopter_api.schema.prefect_orchestration import (
    PrefectDeploymentResponse,
    PrefectFlowRunResponse,
    PrefectOatsMetadataResponse,
    PrefectWorkPoolResponse,
    PrefectWorkerResponse,
)
from oats.prefect.artifacts import LocalFlowRunMetadata

_LOCAL_FLOW_RUN_METADATA_ADAPTER = TypeAdapter(LocalFlowRunMetadata)


def list_prefect_deployments(services: BackendServices) -> list[PrefectDeploymentResponse]:
    return [
        PrefectDeploymentResponse(
            deployment_id=item.deployment_id,
            deployment_name=item.deployment_name,
            flow_id=item.flow_id,
            flow_name=item.flow_name,
            work_pool_name=item.work_pool_name,
            work_queue_name=item.work_queue_name,
            status=item.status,
            updated_at=item.updated_at,
            tags=list(item.tags),
            oats_metadata=_shape_payload_metadata(item.oats_payload),
        )
        for item in services.prefect_client.list_deployments()
    ]


def list_prefect_flow_runs(services: BackendServices) -> list[PrefectFlowRunResponse]:
    metadata_by_run_id = _load_local_flow_run_metadata(services.settings.project_root)
    return [
        _shape_flow_run(item, metadata_by_run_id.get(item.flow_run_id))
        for item in services.prefect_client.list_flow_runs()
    ]


def get_prefect_flow_run(services: BackendServices, flow_run_id: str) -> PrefectFlowRunResponse:
    metadata_by_run_id = _load_local_flow_run_metadata(services.settings.project_root)
    return _shape_flow_run(
        services.prefect_client.read_flow_run(flow_run_id),
        metadata_by_run_id.get(flow_run_id),
    )


def list_prefect_workers(services: BackendServices) -> list[PrefectWorkerResponse]:
    return [
        PrefectWorkerResponse(
            worker_id=item.worker_id,
            worker_name=item.worker_name,
            work_pool_name=item.work_pool_name,
            status=item.status,
            last_heartbeat_at=item.last_heartbeat_at,
        )
        for item in services.prefect_client.list_workers()
    ]


def list_prefect_work_pools(services: BackendServices) -> list[PrefectWorkPoolResponse]:
    return [
        PrefectWorkPoolResponse(
            work_pool_id=item.work_pool_id,
            work_pool_name=item.work_pool_name,
            type=item.type,
            status=item.status,
            is_paused=item.is_paused,
            concurrency_limit=item.concurrency_limit,
        )
        for item in services.prefect_client.list_work_pools()
    ]


def _shape_flow_run(
    item: PrefectFlowRunRecord,
    local_metadata: _StoredLocalFlowRunMetadata | None,
) -> PrefectFlowRunResponse:
    return PrefectFlowRunResponse(
        flow_run_id=item.flow_run_id,
        flow_run_name=item.flow_run_name,
        deployment_id=item.deployment_id,
        deployment_name=item.deployment_name,
        flow_id=item.flow_id,
        flow_name=item.flow_name,
        work_pool_name=item.work_pool_name,
        work_queue_name=item.work_queue_name,
        state_type=item.state_type,
        state_name=item.state_name,
        created_at=item.created_at,
        updated_at=item.updated_at,
        oats_metadata=(
            PrefectOatsMetadataResponse(
                run_title=local_metadata.metadata.run_title,
                source_path=str(local_metadata.metadata.source_path),
                repo_root=str(local_metadata.metadata.repo_root),
                config_path=str(local_metadata.metadata.config_path),
                local_metadata_path=str(local_metadata.path),
                artifact_root=str(local_metadata.metadata.artifact_root),
            )
            if local_metadata is not None
            else None
        ),
    )


def _shape_payload_metadata(payload: PrefectOatsPayload | None) -> PrefectOatsMetadataResponse | None:
    if payload is None:
        return None
    return PrefectOatsMetadataResponse(
        run_title=payload.run_title,
        source_path=payload.source_path,
        repo_root=payload.repo_root,
        config_path=payload.config_path,
        local_metadata_path=None,
        artifact_root=None,
    )


class _StoredLocalFlowRunMetadata:
    def __init__(self, *, path: Path, metadata: LocalFlowRunMetadata) -> None:
        self.path = path
        self.metadata = metadata


def _load_local_flow_run_metadata(project_root: Path) -> dict[str, _StoredLocalFlowRunMetadata]:
    metadata_root = project_root / ".oats" / "prefect" / "flow-runs"
    items: dict[str, _StoredLocalFlowRunMetadata] = {}
    for path in sorted(metadata_root.glob("*/metadata.json")):
        try:
            metadata = _LOCAL_FLOW_RUN_METADATA_ADAPTER.validate_json(path.read_bytes())
        except (FileNotFoundError, OSError, ValueError):
            continue
        items[metadata.flow_run_id] = _StoredLocalFlowRunMetadata(path=path, metadata=metadata)
    return items
