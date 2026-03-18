"""Schemas for provider subscription settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SupportedProvider = Literal["claude", "codex"]


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class SubscriptionCamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class ProviderSubscriptionSettingUpdateRequest(SubscriptionCamelModel):
    """Mutable subscription-setting fields accepted by the PATCH endpoint."""

    has_subscription: bool | None = None
    monthly_cost: float | None = Field(default=None, ge=0)
    provider: SupportedProvider | None = None
    updated_at: str | None = None

    def to_store_update(self) -> dict[str, object]:
        update: dict[str, object] = {}
        if self.has_subscription is not None:
            update["has_subscription"] = self.has_subscription
        if self.monthly_cost is not None:
            update["monthly_cost"] = self.monthly_cost
        return update


class SubscriptionSettingsUpdateRequest(SubscriptionCamelModel):
    """Subscription-setting updates keyed by provider."""

    claude: ProviderSubscriptionSettingUpdateRequest | None = None
    codex: ProviderSubscriptionSettingUpdateRequest | None = None

    def to_store_updates(self) -> dict[SupportedProvider, dict[str, object]]:
        updates: dict[SupportedProvider, dict[str, object]] = {}
        if self.claude is not None:
            updates["claude"] = self.claude.to_store_update()
        if self.codex is not None:
            updates["codex"] = self.codex.to_store_update()
        return updates


class ProviderSubscriptionSettingResponse(SubscriptionCamelModel):
    provider: SupportedProvider
    has_subscription: bool = False
    monthly_cost: float = 0.0
    updated_at: str


class SubscriptionSettingsResponse(SubscriptionCamelModel):
    """Current subscription configuration for all providers."""

    claude: ProviderSubscriptionSettingResponse
    codex: ProviderSubscriptionSettingResponse
