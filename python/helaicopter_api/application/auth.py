"""Auth credential CRUD and managed OAuth lifecycle operations."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from helaicopter_api.schema.auth import (
    CreateCredentialRequest,
    CredentialResponse,
    OAuthInitiateResponse,
    RecordCostRequest,
)
from helaicopter_db.models.oltp import AuthCredentialRecord

# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

_FERNET_KEY: bytes | None = None


def _get_fernet() -> Fernet:
    global _FERNET_KEY
    if _FERNET_KEY is None:
        _FERNET_KEY = Fernet.generate_key()
    return Fernet(_FERNET_KEY)


def _encrypt(value: str | None) -> bytes | None:
    if value is None:
        return None
    return _get_fernet().encrypt(value.encode())


def _decrypt(value: bytes | None) -> str | None:
    if value is None:
        return None
    return _get_fernet().decrypt(value).decode()


# ---------------------------------------------------------------------------
# OAuth provider hooks
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class OAuthTokenBundle:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: list[str]


class OAuthProviderClient(Protocol):
    def build_authorization_url(self, *, state: str, code_challenge: str) -> str: ...

    def exchange_code(self, *, code: str, code_verifier: str) -> OAuthTokenBundle: ...

    def refresh_access_token(self, *, refresh_token: str) -> OAuthTokenBundle: ...


@dataclass(slots=True)
class PendingOAuthState:
    provider: str
    code_verifier: str
    created_at: datetime


_OAUTH_CLIENTS: dict[str, OAuthProviderClient] = {}
_PENDING_OAUTH_STATES: dict[str, PendingOAuthState] = {}


def _get_oauth_client(provider: str) -> OAuthProviderClient:
    client = _OAUTH_CLIENTS.get(provider)
    if client is None:
        raise ValueError(f"OAuth client is not configured for provider '{provider}'")
    return client


def _pkce_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_credential_id() -> str:
    return f"cred_{secrets.token_hex(12)}"


@dataclass(frozen=True, slots=True)
class CredentialProviderStatus:
    code: str
    message: str
    runnable: bool


def _to_response(row: AuthCredentialRecord) -> CredentialResponse:
    provider_status = credential_provider_status_from_record(row)
    return CredentialResponse(
        credential_id=row.credential_id,
        provider=row.provider,
        credential_type=row.credential_type,
        status=row.status,
        provider_status_code=provider_status.code,
        provider_status_message=provider_status.message,
        token_expires_at=row.token_expires_at.isoformat() if row.token_expires_at else None,
        cli_config_path=row.cli_config_path,
        subscription_id=row.subscription_id,
        subscription_tier=row.subscription_tier,
        rate_limit_tier=row.rate_limit_tier,
        created_at=row.created_at.isoformat(),
        last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
        last_refreshed_at=row.last_refreshed_at.isoformat() if row.last_refreshed_at else None,
        cumulative_cost_usd=row.cumulative_cost_usd,
        cost_since_reset=row.cost_since_reset,
    )


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return _ensure_utc_datetime(datetime.fromisoformat(value))


def _ensure_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def credential_is_provider_active(credential: CredentialResponse) -> bool:
    return credential_provider_status_from_response(credential).runnable


def credential_provider_status_from_response(
    credential: CredentialResponse,
) -> CredentialProviderStatus:
    if credential.provider_status_code and credential.provider_status_message:
        return CredentialProviderStatus(
            code=credential.provider_status_code,
            message=credential.provider_status_message,
            runnable=credential.provider_status_code == "ready",
        )
    expires_at = _parse_timestamp(credential.token_expires_at)
    return _credential_provider_status(
        status=credential.status,
        credential_type=credential.credential_type,
        cli_config_path=credential.cli_config_path,
        token_expires_at=expires_at,
    )


def credential_provider_status_from_record(
    credential: AuthCredentialRecord,
) -> CredentialProviderStatus:
    return _credential_provider_status(
        status=credential.status,
        credential_type=credential.credential_type,
        cli_config_path=credential.cli_config_path,
        token_expires_at=_ensure_utc_datetime(credential.token_expires_at),
    )


def _credential_provider_status(
    *,
    status: str,
    credential_type: str,
    cli_config_path: str | None,
    token_expires_at: datetime | None,
) -> CredentialProviderStatus:
    if status == "revoked":
        return CredentialProviderStatus("revoked", "Credential has been revoked.", False)
    if status == "expired":
        return CredentialProviderStatus("expired", "Credential has expired and must be refreshed.", False)
    if credential_type == "local_cli_session" and not cli_config_path:
        return CredentialProviderStatus(
            "missing_cli_session",
            "Local CLI session metadata is missing for this provider credential.",
            False,
        )
    if credential_type == "oauth_token" and token_expires_at is not None and token_expires_at <= datetime.now(UTC):
        return CredentialProviderStatus("expired", "Credential has expired and must be refreshed.", False)
    return CredentialProviderStatus("ready", "Credential is ready for provider execution.", True)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_credential(
    engine: Engine,
    request: CreateCredentialRequest,
) -> CredentialResponse:
    now = datetime.now(UTC)
    record = AuthCredentialRecord(
        credential_id=_generate_credential_id(),
        provider=request.provider,
        credential_type=request.credential_type,
        access_token_encrypted=_encrypt(request.access_token),
        refresh_token_encrypted=_encrypt(request.refresh_token),
        token_expires_at=_parse_timestamp(request.token_expires_at),
        oauth_scopes_json=json.dumps(request.oauth_scopes) if request.oauth_scopes else None,
        api_key_encrypted=_encrypt(request.api_key),
        cli_config_path=request.cli_config_path,
        subscription_id=request.subscription_id,
        subscription_tier=request.subscription_tier,
        rate_limit_tier=request.rate_limit_tier,
        status="active",
        created_at=now,
        cumulative_cost_usd=0.0,
        cost_since_reset=0.0,
    )
    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.refresh(record)
        return _to_response(record)


def list_credentials(engine: Engine) -> list[CredentialResponse]:
    with Session(engine) as session:
        rows = session.execute(select(AuthCredentialRecord)).scalars().all()
        return [_to_response(row) for row in rows]


def revoke_credential(engine: Engine, credential_id: str) -> bool:
    with Session(engine) as session:
        row = session.get(AuthCredentialRecord, credential_id)
        if row is None:
            return False
        row.status = "revoked"
        session.commit()
        return True


def record_cost(
    engine: Engine,
    credential_id: str,
    request: RecordCostRequest,
) -> bool:
    with Session(engine) as session:
        row = session.get(AuthCredentialRecord, credential_id)
        if row is None:
            return False
        row.cumulative_cost_usd += request.cost_usd
        row.cost_since_reset += request.cost_usd
        row.last_used_at = datetime.now(UTC)
        session.commit()
        return True


# ---------------------------------------------------------------------------
# OAuth lifecycle
# ---------------------------------------------------------------------------


def initiate_oauth(*, provider: str) -> OAuthInitiateResponse:
    client = _get_oauth_client(provider)
    state = secrets.token_urlsafe(24)
    code_verifier = secrets.token_urlsafe(48)
    redirect_url = client.build_authorization_url(
        state=state,
        code_challenge=_pkce_challenge(code_verifier),
    )
    _PENDING_OAUTH_STATES[state] = PendingOAuthState(
        provider=provider,
        code_verifier=code_verifier,
        created_at=datetime.now(UTC),
    )
    return OAuthInitiateResponse(redirect_url=redirect_url, state=state)


def complete_oauth_callback(*, engine: Engine, code: str, state: str) -> CredentialResponse:
    pending = _PENDING_OAUTH_STATES.pop(state, None)
    if pending is None:
        raise ValueError("OAuth state is invalid or has expired")

    client = _get_oauth_client(pending.provider)
    token_bundle = client.exchange_code(code=code, code_verifier=pending.code_verifier)
    request = CreateCredentialRequest.model_validate({
        "provider": pending.provider,
        "credentialType": "oauth_token",
        "accessToken": token_bundle.access_token,
        "refreshToken": token_bundle.refresh_token,
        "tokenExpiresAt": token_bundle.expires_at.isoformat() if token_bundle.expires_at else None,
        "oauthScopes": token_bundle.scopes,
    })
    return create_credential(engine, request)


def refresh_credential(engine: Engine, credential_id: str) -> CredentialResponse | None:
    with Session(engine) as session:
        row = session.get(AuthCredentialRecord, credential_id)
        if row is None:
            return None
        if row.credential_type != "oauth_token":
            raise ValueError("Only oauth_token credentials can be refreshed")

        refresh_token = _decrypt(row.refresh_token_encrypted)
        if not refresh_token:
            raise ValueError("OAuth credential is missing a refresh token")

        try:
            token_bundle = _get_oauth_client(row.provider).refresh_access_token(
                refresh_token=refresh_token,
            )
        except Exception:
            row.status = "expired"
            session.commit()
            raise

        row.access_token_encrypted = _encrypt(token_bundle.access_token)
        if token_bundle.refresh_token is not None:
            row.refresh_token_encrypted = _encrypt(token_bundle.refresh_token)
        row.token_expires_at = token_bundle.expires_at
        row.oauth_scopes_json = json.dumps(token_bundle.scopes) if token_bundle.scopes else None
        row.status = "active"
        row.last_refreshed_at = datetime.now(UTC)
        session.commit()
        session.refresh(row)
        return _to_response(row)
