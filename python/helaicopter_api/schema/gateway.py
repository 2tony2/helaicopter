"""Schemas for the platform API gateway direction contract."""

from __future__ import annotations

from helaicopter_api.schema.common import CamelCaseHttpResponseModel


class GatewaySurfaceResponse(CamelCaseHttpResponseModel):
    """Descriptor for a single API surface registered with the platform gateway."""

    key: str
    owner: str
    serving_class: str
    integration_type: str
    is_primary: bool = False
    path_prefixes: list[str] = []
    note: str


class GatewayDirectionResponse(CamelCaseHttpResponseModel):
    """Overall gateway routing direction and registered API surfaces."""

    gateway_direction: str = "fastapi-first"
    frontend_calls_via: str = "fastapi"
    backend_entrypoint: str = "fastapi"
    surfaces: list[GatewaySurfaceResponse] = []
