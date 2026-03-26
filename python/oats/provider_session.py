from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import subprocess

from oats.identity import generate_session_id


@dataclass(slots=True)
class ProviderSession:
    session_id: str
    provider: str
    status: str
    started_at: datetime
    last_used_at: datetime


def _default_auth_validator(provider: str) -> Callable[[], None]:
    if provider == "claude":
        return _validate_claude_cli_auth
    if provider == "codex":
        return _validate_codex_cli_auth
    return lambda: None


def _validate_claude_cli_auth() -> None:
    result = subprocess.run(
        ["claude", "auth", "status"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode != 0:
        raise RuntimeError("Claude CLI session is not authenticated.")
    if not output:
        raise RuntimeError("Claude CLI session is not authenticated.")
    if output.startswith("{") and output.endswith("}"):
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and payload.get("loggedIn") is True:
            return
    if "logged in" not in output.lower() and "authenticated" not in output.lower():
        raise RuntimeError("Claude CLI session is not authenticated.")


def _validate_codex_cli_auth() -> None:
    result = subprocess.run(
        ["codex", "login", "status"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip().lower()
    if result.returncode != 0 or "logged in" not in output:
        raise RuntimeError("Codex CLI session is not authenticated.")


class ProviderSessionManager:
    """Own one reusable provider session for a Pi worker."""

    def __init__(
        self,
        *,
        provider: str,
        auth_validator: Callable[[], None] | None = None,
    ) -> None:
        self.provider = provider
        self.status = "absent"
        self.failure_reason: str | None = None
        self._session: ProviderSession | None = None
        self._auth_validator = auth_validator or _default_auth_validator(provider)

    @property
    def session(self) -> ProviderSession | None:
        return self._session

    def ensure_session(self) -> ProviderSession | None:
        if self._session is not None and self.status == "ready":
            self._session.last_used_at = datetime.now(UTC)
            return self._session

        try:
            self._auth_validator()
        except Exception as exc:
            self.status = "failed"
            self.failure_reason = str(exc)
            raise

        if self.provider == "codex":
            self.status = "absent"
            self.failure_reason = None
            return None

        self.status = "starting"
        session = self._bootstrap_session()
        self._session = session
        self.status = "ready"
        self.failure_reason = None
        return session

    def record_session(self, session_id: str | None) -> None:
        if not session_id:
            return
        now = datetime.now(UTC)
        if self._session is None or self._session.session_id != session_id:
            self._session = ProviderSession(
                session_id=session_id,
                provider=self.provider,
                status="ready",
                started_at=now,
                last_used_at=now,
            )
        else:
            self._session.last_used_at = now
        self.status = "ready"
        self.failure_reason = None

    def reset(self, *, reason: str) -> None:
        del reason
        self._session = None
        self.status = "absent"
        self.failure_reason = None

    def _bootstrap_session(self) -> ProviderSession:
        now = datetime.now(UTC)
        return ProviderSession(
            session_id=generate_session_id(),
            provider=self.provider,
            status="ready",
            started_at=now,
            last_used_at=now,
        )
