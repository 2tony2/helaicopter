"""Auth credential CRUD and managed OAuth lifecycle operations."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import urlencode

import httpx

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
from helaicopter_api.server.config import Settings
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


@dataclass(slots=True)
class ClaudeCliSession:
    cli_config_path: str
    subscription_tier: str | None = None


@dataclass(slots=True)
class CodexCliSession:
    cli_config_path: str


class OAuthProviderClient(Protocol):
    def build_authorization_url(self, *, state: str, code_challenge: str) -> str: ...

    def exchange_code(self, *, code: str, code_verifier: str) -> OAuthTokenBundle: ...

    def refresh_access_token(self, *, refresh_token: str) -> OAuthTokenBundle: ...


@dataclass(slots=True)
class CodexOAuthClient:
    client_id: str
    authorize_url: str
    token_url: str
    redirect_uri: str
    scopes: tuple[str, ...]

    def build_authorization_url(self, *, state: str, code_challenge: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.scopes),
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self.authorize_url}?{query}"

    def exchange_code(self, *, code: str, code_verifier: str) -> OAuthTokenBundle:
        return self._exchange_token(
            {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": code_verifier,
            }
        )

    def refresh_access_token(self, *, refresh_token: str) -> OAuthTokenBundle:
        return self._exchange_token(
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": refresh_token,
            }
        )

    def _exchange_token(self, data: dict[str, str]) -> OAuthTokenBundle:
        try:
            response = httpx.post(self.token_url, data=data, timeout=30.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError("Codex OAuth token exchange failed") from exc
        return _oauth_token_bundle_from_payload(response.json(), fallback_scopes=self.scopes)


@dataclass(slots=True)
class PendingOAuthState:
    provider: str
    code_verifier: str
    created_at: datetime


_OAUTH_CLIENTS: dict[str, OAuthProviderClient] = {}
_PENDING_OAUTH_STATES: dict[str, PendingOAuthState] = {}


def _configured_oauth_clients(*, settings: Settings) -> dict[str, OAuthProviderClient]:
    clients: dict[str, OAuthProviderClient] = {}
    if settings.codex_oauth_client_id:
        clients["codex"] = CodexOAuthClient(
            client_id=settings.codex_oauth_client_id,
            authorize_url=settings.codex_oauth_authorize_url,
            token_url=settings.codex_oauth_token_url,
            redirect_uri=settings.codex_oauth_redirect_uri,
            scopes=settings.codex_oauth_scopes,
        )
    return clients


def _get_oauth_client(provider: str, *, settings: Settings) -> OAuthProviderClient:
    client = _OAUTH_CLIENTS.get(provider)
    if client is None:
        client = _configured_oauth_clients(settings=settings).get(provider)
    if client is None:
        raise ValueError(f"OAuth client is not configured for provider '{provider}'")
    return client


def configure_provider_auth(*, settings: Settings) -> None:
    _OAUTH_CLIENTS.clear()
    _OAUTH_CLIENTS.update(_configured_oauth_clients(settings=settings))


def _oauth_token_bundle_from_payload(
    payload: dict[str, object],
    *,
    fallback_scopes: tuple[str, ...],
) -> OAuthTokenBundle:
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("OAuth token response is missing an access token")

    refresh_token = payload.get("refresh_token")
    if refresh_token is not None and not isinstance(refresh_token, str):
        raise ValueError("OAuth token response has an invalid refresh token")

    expires_at = None
    expires_in = payload.get("expires_in")
    if expires_in is not None:
        expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))

    scopes_value = payload.get("scope") or payload.get("scopes")
    if isinstance(scopes_value, str):
        scopes = [scope for scope in scopes_value.split() if scope]
    elif isinstance(scopes_value, list):
        scopes = [str(scope) for scope in scopes_value if str(scope)]
    else:
        scopes = list(fallback_scopes)

    return OAuthTokenBundle(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        scopes=scopes,
    )


def _pkce_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _parse_claude_subscription_tier(output: str) -> str | None:
    for line in output.splitlines():
        normalized = line.strip().lower()
        if normalized.startswith("subscription tier:"):
            value = line.split(":", 1)[1].strip()
            return value or None
        if normalized.startswith("tier:"):
            value = line.split(":", 1)[1].strip()
            return value or None
    return None


def _claude_status_output_indicates_authenticated_session(output: str) -> bool:
    normalized = output.lower()
    indicators = (
        "logged in",
        "authenticated",
        "subscription tier:",
        "tier:",
        "email:",
        "org id:",
        "org name:",
    )
    return any(indicator in normalized for indicator in indicators)


def _claude_auth_payload_has_meaningful_fields(payload: dict[str, object]) -> bool:
    meaningful_keys = ("authMethod", "apiProvider", "email", "orgId", "orgName", "subscriptionType")
    return any(bool(payload.get(key)) for key in meaningful_keys)


def _parse_claude_status_payload(
    payload: dict[str, object],
    *,
    settings: Settings,
) -> ClaudeCliSession:
    if payload.get("loggedIn") is not True:
        raise ValueError("Claude CLI status does not indicate an authenticated session")
    if not _claude_auth_payload_has_meaningful_fields(payload):
        raise ValueError("Claude CLI status output is missing authenticated session metadata")

    subscription_tier = payload.get("subscriptionType") or payload.get("subscription_tier")
    if subscription_tier is not None and not isinstance(subscription_tier, str):
        raise ValueError("Claude CLI status output has an invalid subscription type")

    return ClaudeCliSession(
        cli_config_path=str(settings.claude_dir),
        subscription_tier=subscription_tier or None,
    )


def _discover_claude_cli_session_from_filesystem(*, settings: Settings) -> ClaudeCliSession:
    credentials_path = settings.claude_dir / "credentials.json"
    if not credentials_path.exists():
        raise ValueError(
            f"Claude CLI authentication could not be discovered: '{credentials_path}' is missing. "
            f"Run '{settings.claude_cli_command} auth login' and try again."
        )

    try:
        payload = json.loads(credentials_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Claude CLI authentication could not be discovered: '{credentials_path}' is unreadable."
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            f"Claude CLI authentication could not be discovered: '{credentials_path}' must contain a JSON object."
        )
    if payload.get("loggedIn") is not True:
        raise ValueError(
            f"Claude CLI authentication could not be discovered: '{credentials_path}' does not describe an active login."
        )
    if not _claude_auth_payload_has_meaningful_fields(payload):
        raise ValueError(
            f"Claude CLI authentication could not be discovered: '{credentials_path}' does not contain authenticated session metadata."
        )

    return ClaudeCliSession(
        cli_config_path=str(settings.claude_dir),
        subscription_tier=(payload.get("subscriptionType") or payload.get("subscription_tier"))
        if isinstance(payload.get("subscriptionType") or payload.get("subscription_tier"), str)
        else None,
    )


def discover_claude_cli_session(*, settings: Settings) -> ClaudeCliSession:
    cli_command = [settings.claude_cli_command, "auth", "status"]
    try:
        result = subprocess.run(
            cli_command,
            cwd=settings.claude_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, OSError) as exc:
        return _discover_claude_cli_session_from_filesystem(settings=settings)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"Claude CLI authentication could not be discovered: '{settings.claude_cli_command} auth status' timed out."
        ) from exc

    if result is not None and result.returncode == 0:
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        stripped_output = output.strip()
        if stripped_output.startswith("{") and stripped_output.endswith("}"):
            try:
                payload = json.loads(stripped_output)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(payload, dict):
                    return _parse_claude_status_payload(payload, settings=settings)
        if not stripped_output or not _claude_status_output_indicates_authenticated_session(stripped_output):
            raise ValueError(
                f"Claude CLI authentication could not be discovered: '{settings.claude_cli_command} auth status' "
                f"returned 0 without authenticated session details. Run '{settings.claude_cli_command} auth login' "
                "and try again."
            )
        return ClaudeCliSession(
            cli_config_path=str(settings.claude_dir),
            subscription_tier=_parse_claude_subscription_tier(output),
        )

    stderr = (result.stderr or "").strip() if result is not None else ""
    stdout = (result.stdout or "").strip() if result is not None else ""
    details = " ".join(part for part in (stderr, stdout) if part)
    raise ValueError(
        f"Claude CLI authentication could not be discovered: '{settings.claude_cli_command} auth status' "
        f"returned {result.returncode if result is not None else 'unknown'}."
        f"{f' Output: {details}' if details else ''} Run '{settings.claude_cli_command} auth login' and try again."
    )


def discover_codex_cli_session(*, settings: Settings) -> CodexCliSession:
    cli_command = ["codex", "login", "status"]
    try:
        result = subprocess.run(
            cli_command,
            cwd=settings.codex_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            "Codex CLI authentication could not be discovered: 'codex login status' timed out."
        ) from exc
    except (FileNotFoundError, OSError) as exc:
        raise ValueError(
            "Codex CLI authentication could not be discovered: 'codex' is unavailable. "
            "Run 'codex login' and try again."
        ) from exc

    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode == 0:
        if not output or "logged in" not in output.lower():
            raise ValueError(
                "Codex CLI authentication could not be discovered: 'codex login status' returned 0 without"
                " authenticated session details. Run 'codex login' and try again."
            )
        return CodexCliSession(cli_config_path=str(settings.codex_dir))

    raise ValueError(
        "Codex CLI authentication could not be discovered: 'codex login status' "
        f"returned {result.returncode}.{' Output: ' + output if output else ''} Run 'codex login' and try again."
    )


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
    with Session(engine) as session:
        record = _create_credential_record(session, request)
        session.commit()
        session.refresh(record)
        return _to_response(record)


def _create_credential_record(session: Session, request: CreateCredentialRequest) -> AuthCredentialRecord:
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
    session.add(record)
    return record


def _active_claude_cli_rows(session: Session) -> list[AuthCredentialRecord]:
    return session.execute(
        select(AuthCredentialRecord)
        .where(
            AuthCredentialRecord.provider == "claude",
            AuthCredentialRecord.credential_type == "local_cli_session",
            AuthCredentialRecord.status == "active",
        )
        .order_by(AuthCredentialRecord.created_at.desc())
    ).scalars().all()


def _active_codex_cli_rows(session: Session) -> list[AuthCredentialRecord]:
    return session.execute(
        select(AuthCredentialRecord)
        .where(
            AuthCredentialRecord.provider == "codex",
            AuthCredentialRecord.credential_type == "local_cli_session",
            AuthCredentialRecord.status == "active",
        )
        .order_by(AuthCredentialRecord.created_at.desc())
    ).scalars().all()


def connect_claude_cli_credential(
    engine: Engine,
    *,
    settings: Settings,
) -> CredentialResponse:
    session = discover_claude_cli_session(settings=settings)
    now = datetime.now(UTC)

    with Session(engine) as db:
        rows = _active_claude_cli_rows(db)
        request = CreateCredentialRequest.model_validate(
            {
                "provider": "claude",
                "credentialType": "local_cli_session",
                "cliConfigPath": session.cli_config_path,
                "subscriptionTier": session.subscription_tier,
            }
        )
        if not rows:
            record = _create_credential_record(db, request)
            db.commit()
            db.refresh(record)
            return _to_response(record)

        row = rows[0]
        row.cli_config_path = session.cli_config_path
        row.subscription_tier = session.subscription_tier
        row.status = "active"
        row.last_refreshed_at = now
        for duplicate in rows[1:]:
            duplicate.status = "revoked"
            duplicate.last_refreshed_at = now
        db.commit()
        db.refresh(row)
        return _to_response(row)


def connect_codex_cli_credential(
    engine: Engine,
    *,
    settings: Settings,
) -> CredentialResponse:
    session = discover_codex_cli_session(settings=settings)
    now = datetime.now(UTC)

    with Session(engine) as db:
        rows = _active_codex_cli_rows(db)
        request = CreateCredentialRequest.model_validate(
            {
                "provider": "codex",
                "credentialType": "local_cli_session",
                "cliConfigPath": session.cli_config_path,
            }
        )
        if not rows:
            record = _create_credential_record(db, request)
            db.commit()
            db.refresh(record)
            return _to_response(record)

        row = rows[0]
        row.cli_config_path = session.cli_config_path
        row.status = "active"
        row.last_refreshed_at = now
        for duplicate in rows[1:]:
            duplicate.status = "revoked"
            duplicate.last_refreshed_at = now
        db.commit()
        db.refresh(row)
        return _to_response(row)


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


def initiate_oauth(*, provider: str, settings: Settings) -> OAuthInitiateResponse:
    client = _get_oauth_client(provider, settings=settings)
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


def complete_oauth_callback(
    *,
    engine: Engine,
    code: str,
    state: str,
    settings: Settings,
) -> CredentialResponse:
    pending = _PENDING_OAUTH_STATES.pop(state, None)
    if pending is None:
        raise ValueError("OAuth state is invalid or has expired")

    client = _get_oauth_client(pending.provider, settings=settings)
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


def refresh_credential(
    engine: Engine,
    credential_id: str,
    *,
    settings: Settings,
) -> CredentialResponse | None:
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
            token_bundle = _get_oauth_client(row.provider, settings=settings).refresh_access_token(
                refresh_token=refresh_token,
            )
        except Exception:
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
