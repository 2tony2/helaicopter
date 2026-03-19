from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib import error, parse, request

from oats.prefect.settings import PrefectSettings, load_prefect_settings


class PrefectApiError(RuntimeError):
    """Raised when the Prefect API returns an error."""


@dataclass(slots=True)
class PrefectHttpClient:
    api_url: str
    timeout_seconds: float = 30.0

    @classmethod
    def from_settings(cls, settings: PrefectSettings | None = None) -> "PrefectHttpClient":
        resolved_settings = settings or load_prefect_settings()
        return cls(api_url=resolved_settings.api_url)

    def find_deployment_by_name(
        self,
        *,
        flow_name: str,
        deployment_name: str,
    ) -> dict[str, Any] | None:
        response = self._request(
            "POST",
            "/deployments/filter",
            json_body={
                "flows": {"operator": "and_", "name": {"any_": [flow_name]}},
                "deployments": {"operator": "and_", "name": {"any_": [deployment_name]}},
                "limit": 1,
            },
        )
        if not response:
            return None
        first = response[0]
        return first if isinstance(first, dict) else None

    def create_deployment(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request("POST", "/deployments/", json_body=payload)
        if not isinstance(response, dict):
            raise PrefectApiError("Prefect create deployment response was not an object")
        return response

    def update_deployment(
        self,
        deployment_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._request("PATCH", f"/deployments/{deployment_id}", json_body=payload)
        return {"id": deployment_id, **payload}

    def create_flow_run_from_deployment(
        self,
        deployment_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._request(
            "POST",
            f"/deployments/{deployment_id}/create_flow_run",
            json_body=payload,
        )
        if not isinstance(response, dict):
            raise PrefectApiError("Prefect create flow-run response was not an object")
        return response

    def read_work_pool(self, pool_name: str) -> dict[str, Any]:
        response = self._request("GET", f"/work_pools/{parse.quote(pool_name, safe='')}")
        if not isinstance(response, dict):
            raise PrefectApiError("Prefect work-pool response was not an object")
        return response

    def read_flow_run(self, flow_run_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/flow_runs/{flow_run_id}")
        if not isinstance(response, dict):
            raise PrefectApiError("Prefect flow-run response was not an object")
        return response

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.api_url.rstrip('/')}/{path.lstrip('/')}"
        data = None
        headers = {"Accept": "application/json"}
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(
            url=url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                payload = response.read().decode("utf-8").strip()
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace").strip()
            raise PrefectApiError(
                f"Prefect API request failed with {exc.code} for {method} {url}: {details}"
            ) from exc
        except error.URLError as exc:
            raise PrefectApiError(f"Prefect API request failed for {method} {url}: {exc.reason}") from exc

        if not payload:
            return None
        return json.loads(payload)
