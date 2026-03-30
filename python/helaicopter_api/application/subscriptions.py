"""Application-layer subscription settings logic."""

from __future__ import annotations

from pydantic import ConfigDict, InstanceOf, validate_call

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.app_sqlite import (
    ProviderSubscriptionSettingUpdate,
    SubscriptionSettings,
    SubscriptionSettingsUpdate,
)
from helaicopter_api.schema.subscriptions import (
    ProviderSubscriptionSettingUpdateRequest,
    SubscriptionSettingsResponse,
    SubscriptionSettingsUpdateRequest,
)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def get_subscription_settings(services: InstanceOf[BackendServices]) -> SubscriptionSettingsResponse:
    """Return the current subscription settings from the app-local store.

    Args:
        services: Initialised backend services providing the SQLite settings
            store.

    Returns:
        Current ``SubscriptionSettingsResponse`` for all configured providers.
    """
    settings = services.app_sqlite_store.get_subscription_settings()
    return _to_response(settings)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def update_subscription_settings(
    services: InstanceOf[BackendServices],
    body: SubscriptionSettingsUpdateRequest,
) -> SubscriptionSettingsResponse:
    """Persist subscription-setting updates in the app-local store.

    Args:
        services: Initialised backend services providing the SQLite settings
            store.
        body: Update request containing optional per-provider subscription
            details (``has_subscription``, ``monthly_cost``).

    Returns:
        Updated ``SubscriptionSettingsResponse`` reflecting the persisted
        changes.
    """
    settings = services.app_sqlite_store.update_subscription_settings(_to_store_updates(body))
    return _to_response(settings)


def _to_response(settings: SubscriptionSettings) -> SubscriptionSettingsResponse:
    return SubscriptionSettingsResponse.model_validate(settings.model_dump(mode="python"))


def _to_store_updates(body: SubscriptionSettingsUpdateRequest) -> SubscriptionSettingsUpdate:
    return SubscriptionSettingsUpdate(
        claude=_to_store_update(body.claude),
        codex=_to_store_update(body.codex),
    )


def _to_store_update(
    body: ProviderSubscriptionSettingUpdateRequest | None,
) -> ProviderSubscriptionSettingUpdate | None:
    if body is None:
        return None
    return ProviderSubscriptionSettingUpdate(
        has_subscription=body.has_subscription,
        monthly_cost=body.monthly_cost,
    )
