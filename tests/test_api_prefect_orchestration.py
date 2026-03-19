"""Endpoint tests for the Prefect orchestration API."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.prefect import (
    PrefectDeploymentRecord,
    PrefectFlowRunRecord,
    PrefectOatsPayload,
    PrefectWorkPoolRecord,
    PrefectWorkerRecord,
)
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_api.server.config import Settings


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def prefect_client(
    *,
    prefect_client: object,
    project_root: Path,
) -> Iterator[TestClient]:
    application = create_app()
    settings = Settings(project_root=project_root)
    application.dependency_overrides[get_services] = lambda: _services_stub(
        prefect_client=prefect_client,
        settings=settings,
    )
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()


class StubPrefectClient:
    def list_deployments(self) -> list[PrefectDeploymentRecord]:
        return [
            PrefectDeploymentRecord(
                deployment_id="deployment-1",
                deployment_name="helaicopter-run-prefect-api",
                flow_id="flow-1",
                flow_name="oats-compiled-run",
                work_pool_name="local-macos",
                work_queue_name="scheduled",
                status="READY",
                updated_at="2026-03-18T10:00:00Z",
                tags=["oats", "backend"],
                oats_payload=PrefectOatsPayload(
                    run_title="Run: Prefect Native Oats Orchestration",
                    source_path="/repo/examples/prefect_native_oats_orchestration_run.md",
                    repo_root="/repo",
                    config_path="/repo/.oats/config.toml",
                ),
            )
        ]

    def list_flow_runs(self) -> list[PrefectFlowRunRecord]:
        return [
            PrefectFlowRunRecord(
                flow_run_id="flow-run-1",
                flow_run_name="run-prefect-api-1",
                deployment_id="deployment-1",
                deployment_name="helaicopter-run-prefect-api",
                flow_id="flow-1",
                flow_name="oats-compiled-run",
                work_pool_name="local-macos",
                work_queue_name="scheduled",
                state_type="RUNNING",
                state_name="Running",
                created_at="2026-03-18T10:05:00Z",
                updated_at="2026-03-18T10:06:00Z",
            )
        ]

    def read_flow_run(self, flow_run_id: str) -> PrefectFlowRunRecord:
        assert flow_run_id == "flow-run-1"
        return PrefectFlowRunRecord(
            flow_run_id="flow-run-1",
            flow_run_name="run-prefect-api-1",
            deployment_id="deployment-1",
            deployment_name="helaicopter-run-prefect-api",
            flow_id="flow-1",
            flow_name="oats-compiled-run",
            work_pool_name="local-macos",
            work_queue_name="scheduled",
            state_type="RUNNING",
            state_name="Running",
            created_at="2026-03-18T10:05:00Z",
            updated_at="2026-03-18T10:06:00Z",
        )

    def list_workers(self) -> list[PrefectWorkerRecord]:
        return [
            PrefectWorkerRecord(
                worker_id="worker-1",
                worker_name="mac-mini-worker",
                work_pool_name="local-macos",
                status="ONLINE",
                last_heartbeat_at="2026-03-18T10:06:30Z",
            )
        ]

    def list_work_pools(self) -> list[PrefectWorkPoolRecord]:
        return [
            PrefectWorkPoolRecord(
                work_pool_id="pool-1",
                work_pool_name="local-macos",
                type="process",
                status="READY",
                is_paused=False,
                concurrency_limit=4,
            )
        ]


def test_list_deployments_exposes_normalized_prefect_payloads(tmp_path: Path) -> None:
    with prefect_client(prefect_client=StubPrefectClient(), project_root=tmp_path) as client:
        response = client.get("/orchestration/prefect/deployments")

    assert response.status_code == 200
    assert response.json() == [
        {
            "deploymentId": "deployment-1",
            "deploymentName": "helaicopter-run-prefect-api",
            "flowId": "flow-1",
            "flowName": "oats-compiled-run",
            "workPoolName": "local-macos",
            "workQueueName": "scheduled",
            "status": "READY",
            "updatedAt": "2026-03-18T10:00:00Z",
            "tags": ["oats", "backend"],
            "oatsMetadata": {
                "runTitle": "Run: Prefect Native Oats Orchestration",
                "sourcePath": "/repo/examples/prefect_native_oats_orchestration_run.md",
                "repoRoot": "/repo",
                "configPath": "/repo/.oats/config.toml",
                "localMetadataPath": None,
                "artifactRoot": None,
            },
        }
    ]


def test_list_flow_runs_joins_repo_local_oats_metadata_when_available(tmp_path: Path) -> None:
    metadata_dir = tmp_path / ".oats" / "prefect" / "flow-runs" / "flow-run-1"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "metadata.json").write_text(
        """
        {
          "flow_run_id": "flow-run-1",
          "flow_run_name": "run-prefect-api-1",
          "run_title": "Run: Prefect Native Oats Orchestration",
          "source_path": "/repo/examples/prefect_native_oats_orchestration_run.md",
          "repo_root": "/repo",
          "config_path": "/repo/.oats/config.toml",
          "artifact_root": "/repo/.oats/prefect/flow-runs/flow-run-1",
          "created_at": "2026-03-18T10:05:00Z",
          "updated_at": "2026-03-18T10:06:00Z",
          "completed_at": null
        }
        """.strip(),
        encoding="utf-8",
    )

    with prefect_client(prefect_client=StubPrefectClient(), project_root=tmp_path) as client:
        response = client.get("/orchestration/prefect/flow-runs")

    assert response.status_code == 200
    assert response.json() == [
        {
            "flowRunId": "flow-run-1",
            "flowRunName": "run-prefect-api-1",
            "deploymentId": "deployment-1",
            "deploymentName": "helaicopter-run-prefect-api",
            "flowId": "flow-1",
            "flowName": "oats-compiled-run",
            "workPoolName": "local-macos",
            "workQueueName": "scheduled",
            "stateType": "RUNNING",
            "stateName": "Running",
            "createdAt": "2026-03-18T10:05:00Z",
            "updatedAt": "2026-03-18T10:06:00Z",
            "oatsMetadata": {
                "runTitle": "Run: Prefect Native Oats Orchestration",
                "sourcePath": "/repo/examples/prefect_native_oats_orchestration_run.md",
                "repoRoot": "/repo",
                "configPath": "/repo/.oats/config.toml",
                "localMetadataPath": str(metadata_dir / "metadata.json"),
                "artifactRoot": "/repo/.oats/prefect/flow-runs/flow-run-1",
            },
        }
    ]


def test_flow_run_detail_returns_normalized_state_and_local_metadata(tmp_path: Path) -> None:
    metadata_dir = tmp_path / ".oats" / "prefect" / "flow-runs" / "flow-run-1"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "metadata.json").write_text(
        """
        {
          "flow_run_id": "flow-run-1",
          "flow_run_name": "run-prefect-api-1",
          "run_title": "Run: Prefect Native Oats Orchestration",
          "source_path": "/repo/examples/prefect_native_oats_orchestration_run.md",
          "repo_root": "/repo",
          "config_path": "/repo/.oats/config.toml",
          "artifact_root": "/repo/.oats/prefect/flow-runs/flow-run-1",
          "created_at": "2026-03-18T10:05:00Z",
          "updated_at": "2026-03-18T10:06:00Z",
          "completed_at": null
        }
        """.strip(),
        encoding="utf-8",
    )

    with prefect_client(prefect_client=StubPrefectClient(), project_root=tmp_path) as client:
        response = client.get("/orchestration/prefect/flow-runs/flow-run-1")

    assert response.status_code == 200
    body = response.json()
    assert body["flowRunId"] == "flow-run-1"
    assert body["stateType"] == "RUNNING"
    assert body["stateName"] == "Running"
    assert body["oatsMetadata"]["localMetadataPath"] == str(metadata_dir / "metadata.json")


def test_worker_and_pool_endpoints_report_prefect_capacity_state(tmp_path: Path) -> None:
    with prefect_client(prefect_client=StubPrefectClient(), project_root=tmp_path) as client:
        workers_response = client.get("/orchestration/prefect/workers")
        pools_response = client.get("/orchestration/prefect/work-pools")

    assert workers_response.status_code == 200
    assert workers_response.json() == [
        {
            "workerId": "worker-1",
            "workerName": "mac-mini-worker",
            "workPoolName": "local-macos",
            "status": "ONLINE",
            "lastHeartbeatAt": "2026-03-18T10:06:30Z",
        }
    ]

    assert pools_response.status_code == 200
    assert pools_response.json() == [
        {
            "workPoolId": "pool-1",
            "workPoolName": "local-macos",
            "type": "process",
            "status": "READY",
            "isPaused": False,
            "concurrencyLimit": 4,
        }
    ]


def test_openapi_positions_prefect_routes_as_primary_and_oats_routes_as_documented_surfaces(
    tmp_path: Path,
) -> None:
    with prefect_client(prefect_client=StubPrefectClient(), project_root=tmp_path) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    prefect_flow_runs = schema["paths"]["/orchestration/prefect/flow-runs"]["get"]
    oats_route = schema["paths"]["/orchestration/oats"]["get"]

    assert prefect_flow_runs["tags"] == ["orchestration"]
    assert oats_route["tags"] == ["orchestration"]
    assert prefect_flow_runs["summary"] == "List primary Prefect flow runs for orchestration."
    assert oats_route["summary"] == "List OATS local-runtime records."
