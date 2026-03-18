"""Schemas for provider subscription settings."""

from __future__ import annotations

from pydantic import BaseModel, Field
from helaicopter_domain.vocab import ProviderName
from helaicopter_api.schema.common import CamelCaseHttpResponseModel, camel_case_request_config

SupportedProvider = ProviderName


class ProviderSubscriptionSettingUpdateRequest(BaseModel):
    """Mutable subscription-setting fields accepted by the PATCH endpoint."""

    model_config = camel_case_request_config(extra="forbid")

    has_subscription: bool | None = None
    monthly_cost: float | None = Field(default=None, ge=0)
    provider: ProviderName | None = None
    updated_at: str | None = None


class SubscriptionSettingsUpdateRequest(BaseModel):
    """Subscription-setting updates keyed by provider."""

    model_config = camel_case_request_config(extra="forbid")

    claude: ProviderSubscriptionSettingUpdateRequest | None = None
    codex: ProviderSubscriptionSettingUpdateRequest | None = None


class ProviderSubscriptionSettingResponse(CamelCaseHttpResponseModel):
    provider: ProviderName
    has_subscription: bool = False
    monthly_cost: float = 0.0
    updated_at: str


class SubscriptionSettingsResponse(CamelCaseHttpResponseModel):
    """Current subscription configuration for all providers."""

    claude: ProviderSubscriptionSettingResponse
    codex: ProviderSubscriptionSettingResponse
