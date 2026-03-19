"""HTTP adapter for the Prefect REST API."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib import error, parse, request

from helaicopter_api.ports.prefect import (
    PrefectDeploymentRecord,
    PrefectFlowRunRecord,
    PrefectOatsPayload,
    PrefectOrchestrationPort,
    PrefectWorkPoolRecord,
    PrefectWorkerRecord,
)
from helaicopter_api.server.config import PrefectApiSettings


class PrefectHttpError(RuntimeError):
    """Raised when the Prefect API request fails."""


@dataclass(slots=True)
class PrefectHttpAdapter(PrefectOrchestrationPort):
    api_url: str
    timeout_seconds: float = 30.0

    @classmethod
    def from_settings(cls, settings: PrefectApiSettings) -> "PrefectHttpAdapter":
        return cls(api_url=settings.api_url, timeout_seconds=settings.timeout_seconds)

    def list_deployments(self) -> list[PrefectDeploymentRecord]:
        payload = self._request("POST", "/deployments/filter", json_body={"limit": 200})
        if not isinstance(payload, list):
            return []
        return [_shape_deployment(item) for item in payload if isinstance(item, dict)]

    def list_flow_runs(self) -> list[PrefectFlowRunRecord]:
        payload = self._request("POST", "/flow_runs/filter", json_body={"limit": 200})
        if not isinstance(payload, list):
            return []
        return [_shape_flow_run(item) for item in payload if isinstance(item, dict)]

    def read_flow_run(self, flow_run_id: str) -> PrefectFlowRunRecord:
        payload = self._request("GET", f"/flow_runs/{parse.quote(flow_run_id, safe='')}")
        if not isinstance(payload, dict):
            raise PrefectHttpError("Prefect flow-run response was not an object")
        return _shape_flow_run(payload)

    def list_workers(self) -> list[PrefectWorkerRecord]:
        payload = self._request("POST", "/workers/filter", json_body={"limit": 200})
        if not isinstance(payload, list):
            return []
        return [_shape_worker(item) for item in payload if isinstance(item, dict)]

    def list_work_pools(self) -> list[PrefectWorkPoolRecord]:
        payload = self._request("POST", "/work_pools/filter", json_body={"limit": 200})
        if not isinstance(payload, list):
            return []
        return [_shape_work_pool(item) for item in payload if isinstance(item, dict)]

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
    ) -> Any:
        url = f"{self.api_url.rstrip('/')}/{path.lstrip('/')}"
        body = None
        headers = {"Accept": "application/json"}
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(url=url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw_payload = response.read().decode("utf-8").strip()
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace").strip()
            raise PrefectHttpError(
                f"Prefect API request failed with {exc.code} for {method} {url}: {details}"
            ) from exc
        except error.URLError as exc:
            raise PrefectHttpError(f"Prefect API request failed for {method} {url}: {exc.reason}") from exc
        if not raw_payload:
            return None
        return json.loads(raw_payload)


def _shape_deployment(payload: dict[str, Any]) -> PrefectDeploymentRecord:
    parameters = payload.get("parameters")
    oats_payload: PrefectOatsPayload | None = None
    if isinstance(parameters, dict):
        raw_oats_payload = parameters.get("payload")
        if isinstance(raw_oats_payload, dict):
            oats_payload = PrefectOatsPayload(
                run_title=_as_optional_str(raw_oats_payload.get("run_title")),
                source_path=_as_optional_str(raw_oats_payload.get("source_path")),
                repo_root=_as_optional_str(raw_oats_payload.get("repo_root")),
                config_path=_as_optional_str(raw_oats_payload.get("config_path")),
            )
    return PrefectDeploymentRecord(
        deployment_id=_required_str(payload.get("id"), fallback=""),
        deployment_name=_required_str(payload.get("name"), fallback=""),
        flow_id=_as_optional_str(payload.get("flow_id")),
        flow_name=_flow_name(payload),
        work_pool_name=_as_optional_str(payload.get("work_pool_name")),
        work_queue_name=_as_optional_str(payload.get("work_queue_name")),
        status=_as_optional_str(payload.get("status")),
        updated_at=_as_optional_str(payload.get("updated_at")),
        tags=_string_list(payload.get("tags")),
        oats_payload=oats_payload,
    )


def _shape_flow_run(payload: dict[str, Any]) -> PrefectFlowRunRecord:
    state = payload.get("state")
    state_type = None
    state_name = None
    if isinstance(state, dict):
        state_type = _as_optional_str(state.get("type"))
        state_name = _as_optional_str(state.get("name"))
    return PrefectFlowRunRecord(
        flow_run_id=_required_str(payload.get("id"), fallback=""),
        flow_run_name=_as_optional_str(payload.get("name")),
        deployment_id=_as_optional_str(payload.get("deployment_id")),
        deployment_name=_as_optional_str(payload.get("deployment_name")),
        flow_id=_as_optional_str(payload.get("flow_id")),
        flow_name=_flow_name(payload),
        work_pool_name=_as_optional_str(payload.get("work_pool_name")),
        work_queue_name=_as_optional_str(payload.get("work_queue_name")),
        state_type=state_type,
        state_name=state_name,
        created_at=_as_optional_str(payload.get("created_at")),
        updated_at=_as_optional_str(payload.get("updated_at")),
    )


def _shape_worker(payload: dict[str, Any]) -> PrefectWorkerRecord:
    return PrefectWorkerRecord(
        worker_id=_required_str(payload.get("id"), fallback=""),
        worker_name=_required_str(payload.get("name"), fallback=""),
        work_pool_name=_as_optional_str(payload.get("work_pool_name")),
        status=_as_optional_str(payload.get("status")),
        last_heartbeat_at=_as_optional_str(payload.get("last_heartbeat_time")),
    )


def _shape_work_pool(payload: dict[str, Any]) -> PrefectWorkPoolRecord:
    return PrefectWorkPoolRecord(
        work_pool_id=_required_str(payload.get("id"), fallback=""),
        work_pool_name=_required_str(payload.get("name"), fallback=""),
        type=_as_optional_str(payload.get("type")),
        status=_as_optional_str(payload.get("status")),
        is_paused=bool(payload.get("is_paused", False)),
        concurrency_limit=_as_optional_int(payload.get("concurrency_limit")),
    )


def _flow_name(payload: dict[str, Any]) -> str | None:
    if isinstance(payload.get("flow_name"), str):
        return payload["flow_name"]
    flow = payload.get("flow")
    if isinstance(flow, dict):
        return _as_optional_str(flow.get("name"))
    return None


def _required_str(value: object, *, fallback: str) -> str:
    return value if isinstance(value, str) else fallback


def _as_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
