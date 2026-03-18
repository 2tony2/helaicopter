"""Application-layer subscription settings orchestration."""

from __future__ import annotations

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.app_sqlite import SubscriptionSettings
from helaicopter_api.schema.subscriptions import (
    SubscriptionSettingsResponse,
    SubscriptionSettingsUpdateRequest,
)


def get_subscription_settings(services: BackendServices) -> SubscriptionSettingsResponse:
    """Return the current subscription settings from the app-local store."""
    settings = services.app_sqlite_store.get_subscription_settings()
    return _to_response(settings)


def update_subscription_settings(
    services: BackendServices,
    body: SubscriptionSettingsUpdateRequest,
) -> SubscriptionSettingsResponse:
    """Persist subscription-setting updates in the app-local store."""
    settings = services.app_sqlite_store.update_subscription_settings(body.to_store_updates())
    return _to_response(settings)


def _to_response(settings: SubscriptionSettings) -> SubscriptionSettingsResponse:
    return SubscriptionSettingsResponse.model_validate(settings.model_dump(mode="python"))
