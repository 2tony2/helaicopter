"""Schemas for the auth credential store API."""

from __future__ import annotations

from pydantic import BaseModel

from helaicopter_api.schema.common import CamelCaseHttpResponseModel, camel_case_request_config


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateCredentialRequest(BaseModel):
    """Body for ``POST /auth/credentials``."""

    model_config = camel_case_request_config(extra="forbid")

    provider: str
    credential_type: str  # oauth_token | api_key | local_cli_session

    # oauth_token fields
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: str | None = None
    oauth_scopes: list[str] | None = None

    # api_key fields
    api_key: str | None = None

    # local_cli_session fields
    cli_config_path: str | None = None

    # subscription metadata
    subscription_id: str | None = None
    subscription_tier: str | None = None
    rate_limit_tier: str | None = None


class RecordCostRequest(BaseModel):
    """Body for ``POST /auth/credentials/{id}/record-cost``."""

    model_config = camel_case_request_config(extra="forbid")

    cost_usd: float


class OAuthInitiateRequest(BaseModel):
    """Body for ``POST /auth/credentials/oauth/initiate``."""

    model_config = camel_case_request_config(extra="forbid")

    provider: str


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class CredentialResponse(CamelCaseHttpResponseModel):
    """Credential detail — never exposes secrets."""

    credential_id: str
    provider: str
    credential_type: str
    status: str
    token_expires_at: str | None = None
    cli_config_path: str | None = None
    subscription_id: str | None = None
    subscription_tier: str | None = None
    rate_limit_tier: str | None = None
    created_at: str
    last_used_at: str | None = None
    last_refreshed_at: str | None = None
    cumulative_cost_usd: float = 0.0
    cost_since_reset: float = 0.0


class OAuthInitiateResponse(CamelCaseHttpResponseModel):
    """OAuth initiation details for the frontend."""

    redirect_url: str
    state: str
