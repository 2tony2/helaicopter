"""Platform gateway direction API endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from helaicopter_api.application.gateway import describe_gateway_direction
from helaicopter_api.schema.gateway import GatewayDirectionResponse

gateway_router = APIRouter(prefix="/gateway", tags=["gateway"])


@gateway_router.get(
    "/direction",
    response_model=GatewayDirectionResponse,
    response_model_by_alias=True,
    summary="Describe the primary backend gateway direction across platform surfaces.",
)
async def gateway_direction() -> GatewayDirectionResponse:
    """Return the primary backend gateway direction across platform surfaces.

    Returns:
        Gateway direction metadata describing which backend surfaces are active
        and how requests should be routed across them.
    """
    return describe_gateway_direction()
