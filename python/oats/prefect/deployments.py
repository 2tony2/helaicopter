from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from oats.models import RepoConfig
from oats.prefect.client import PrefectHttpClient
from oats.prefect.compiler import compile_run_definition
from oats.prefect.models import PrefectDeploymentSpec
from oats.run_definition import CanonicalRunDefinition


class PrefectDeploymentClient(Protocol):
    def find_flow_by_name(self, flow_name: str) -> dict[str, Any] | None: ...

    def create_flow(self, flow_name: str) -> dict[str, Any]: ...

    def find_deployment_by_name(
        self,
        *,
        flow_name: str,
        deployment_name: str,
    ) -> dict[str, Any] | None: ...

    def create_deployment(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def update_deployment(
        self,
        deployment_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...

    def create_flow_run_from_deployment(
        self,
        deployment_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...

    def read_flow_run(self, flow_run_id: str) -> dict[str, Any]: ...


class RegisteredDeployment(BaseModel):
    deployment_id: str
    deployment_name: str
    flow_name: str
    created: bool


class TriggeredFlowRun(BaseModel):
    flow_run_id: str
    flow_run_name: str | None = None
    state_type: str | None = None
    state_name: str | None = None
    deployment_id: str


class FlowRunStatus(BaseModel):
    flow_run_id: str
    flow_run_name: str | None = None
    state_type: str | None = None
    state_name: str | None = None


def deploy_run_spec(
    run_definition: CanonicalRunDefinition,
    repo_config: RepoConfig,
    *,
    client: PrefectDeploymentClient | None = None,
) -> RegisteredDeployment:
    deployment_spec = compile_run_definition(run_definition, repo_config)
    return upsert_deployment(deployment_spec, client=client)


def upsert_deployment(
    deployment_spec: PrefectDeploymentSpec,
    *,
    client: PrefectDeploymentClient | None = None,
) -> RegisteredDeployment:
    prefect_client = client or PrefectHttpClient.from_settings()
    flow = prefect_client.find_flow_by_name(deployment_spec.flow_name)
    if flow is None:
        flow = prefect_client.create_flow(deployment_spec.flow_name)
    flow_id = flow.get("id")
    if not isinstance(flow_id, str):
        raise ValueError("Prefect flow response did not include an id")

    create_payload = build_deployment_create_request(deployment_spec, flow_id=flow_id)
    existing = prefect_client.find_deployment_by_name(
        flow_name=deployment_spec.flow_name,
        deployment_name=deployment_spec.deployment_name,
    )
    if existing and isinstance(existing.get("id"), str):
        deployment_id = existing["id"]
        prefect_client.update_deployment(
            deployment_id,
            build_deployment_update_request(deployment_spec),
        )
        return RegisteredDeployment(
            deployment_id=deployment_id,
            deployment_name=deployment_spec.deployment_name,
            flow_name=deployment_spec.flow_name,
            created=False,
        )

    created = prefect_client.create_deployment(create_payload)
    deployment_id = created.get("id")
    if not isinstance(deployment_id, str):
        raise ValueError("Prefect create deployment response did not include an id")
    return RegisteredDeployment(
        deployment_id=deployment_id,
        deployment_name=deployment_spec.deployment_name,
        flow_name=deployment_spec.flow_name,
        created=True,
    )


def trigger_run_spec(
    run_definition: CanonicalRunDefinition,
    repo_config: RepoConfig,
    *,
    client: PrefectDeploymentClient | None = None,
) -> TriggeredFlowRun:
    deployment_spec = compile_run_definition(run_definition, repo_config)
    registration = upsert_deployment(deployment_spec, client=client)
    prefect_client = client or PrefectHttpClient.from_settings()
    response = prefect_client.create_flow_run_from_deployment(
        registration.deployment_id,
        {
            "parameters": deployment_spec.parameters,
            "tags": ["manual"],
        },
    )
    state = _state_payload(response)
    flow_run_id = response.get("id")
    if not isinstance(flow_run_id, str):
        raise ValueError("Prefect create flow-run response did not include an id")
    flow_run_name = response.get("name")
    return TriggeredFlowRun(
        flow_run_id=flow_run_id,
        flow_run_name=flow_run_name if isinstance(flow_run_name, str) else None,
        state_type=state.get("type"),
        state_name=state.get("name"),
        deployment_id=registration.deployment_id,
    )


def read_flow_run_status(
    flow_run_id: str,
    *,
    client: PrefectDeploymentClient | None = None,
) -> FlowRunStatus:
    prefect_client = client or PrefectHttpClient.from_settings()
    response = prefect_client.read_flow_run(flow_run_id)
    state = _state_payload(response)
    flow_run_name = response.get("name")
    return FlowRunStatus(
        flow_run_id=flow_run_id,
        flow_run_name=flow_run_name if isinstance(flow_run_name, str) else None,
        state_type=state.get("type"),
        state_name=state.get("name"),
    )


def build_deployment_create_request(
    deployment_spec: PrefectDeploymentSpec,
    *,
    flow_id: str,
) -> dict[str, Any]:
    return {
        "name": deployment_spec.deployment_name,
        "flow_id": flow_id,
        "entrypoint": deployment_spec.entrypoint,
        "description": deployment_spec.description,
        "path": str(deployment_spec.flow_payload.repo_root),
        "work_pool_name": deployment_spec.work_pool_name,
        "work_queue_name": deployment_spec.work_queue_name,
        "parameters": deployment_spec.parameters,
        "parameter_openapi_schema": {
            "type": "object",
            "properties": {"payload": {"type": "object"}},
            "required": ["payload"],
        },
        "enforce_parameter_schema": False,
        "tags": list(deployment_spec.tags),
    }


def build_deployment_update_request(deployment_spec: PrefectDeploymentSpec) -> dict[str, Any]:
    return {
        "entrypoint": deployment_spec.entrypoint,
        "description": deployment_spec.description,
        "path": str(deployment_spec.flow_payload.repo_root),
        "work_pool_name": deployment_spec.work_pool_name,
        "work_queue_name": deployment_spec.work_queue_name,
        "parameters": deployment_spec.parameters,
        "parameter_openapi_schema": {
            "type": "object",
            "properties": {"payload": {"type": "object"}},
            "required": ["payload"],
        },
        "enforce_parameter_schema": False,
        "tags": list(deployment_spec.tags),
    }


def _state_payload(response: dict[str, Any]) -> dict[str, str | None]:
    state = response.get("state")
    if not isinstance(state, dict):
        return {"type": None, "name": None}
    state_type = state.get("type")
    state_name = state.get("name")
    return {
        "type": state_type if isinstance(state_type, str) else None,
        "name": state_name if isinstance(state_name, str) else None,
    }
