"""Analytics API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from helaicopter_api.application.analytics import get_analytics
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.analytics import AnalyticsDataResponse, AnalyticsQueryParams
from helaicopter_api.server.dependencies import get_services

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


@analytics_router.get("", response_model=AnalyticsDataResponse)
async def analytics_index(
    params: Annotated[
        AnalyticsQueryParams,
        Query(description="Analytics filters for the persisted-conversation dashboard."),
    ],
    services: BackendServices = Depends(get_services),
) -> AnalyticsDataResponse:
    """Return aggregated analytics for persisted conversations.

    Args:
        params: Query parameters controlling the analytics window. Supports
            ``days`` to restrict to a trailing number of days, and ``provider``
            to filter by a specific AI provider (e.g. ``"claude"``,
            ``"codex"``, or ``"all"``).

    Returns:
        Aggregated analytics payload including token counts, estimated costs,
        model and tool breakdowns, daily usage time series, and spend rates.
    """
    return get_analytics(services, days=params.days, provider=params.provider)
