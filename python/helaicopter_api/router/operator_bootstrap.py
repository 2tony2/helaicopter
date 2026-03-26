"""Operator bootstrap readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from helaicopter_api.application.operator_bootstrap import build_operator_bootstrap_summary
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.operator_bootstrap import OperatorBootstrapResponse
from helaicopter_api.server.dependencies import get_services

operator_bootstrap_router = APIRouter(prefix="/operator", tags=["operator"])


@operator_bootstrap_router.get(
    "/bootstrap",
    response_model=OperatorBootstrapResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_200_OK,
    summary="Return operator bootstrap readiness summary.",
)
async def operator_bootstrap(
    request: Request,
    services: BackendServices = Depends(get_services),
) -> OperatorBootstrapResponse:
    resolver = getattr(request.app.state, "resolver", None)
    return build_operator_bootstrap_summary(
        services,
        resolver_running=bool(getattr(resolver, "_running", False)),
    )
