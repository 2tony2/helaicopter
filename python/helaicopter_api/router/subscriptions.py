"""Subscription settings API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from helaicopter_api.application.subscriptions import (
    get_subscription_settings,
    update_subscription_settings,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.subscriptions import (
    SubscriptionSettingsResponse,
    SubscriptionSettingsUpdateRequest,
)
from helaicopter_api.server.dependencies import get_services

subscriptions_router = APIRouter(prefix="/subscription-settings", tags=["subscriptions"])


@subscriptions_router.get("", response_model=SubscriptionSettingsResponse, response_model_by_alias=True)
async def subscriptions_index(
    services: BackendServices = Depends(get_services),
) -> SubscriptionSettingsResponse:
    """Return the current provider subscription settings."""
    return get_subscription_settings(services)


@subscriptions_router.patch("", response_model=SubscriptionSettingsResponse, response_model_by_alias=True)
async def subscriptions_update(
    body: SubscriptionSettingsUpdateRequest = Body(default_factory=SubscriptionSettingsUpdateRequest),
    services: BackendServices = Depends(get_services),
) -> SubscriptionSettingsResponse:
    """Persist provider subscription settings and return the merged result."""
    return update_subscription_settings(services, body)
