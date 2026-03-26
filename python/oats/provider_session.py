from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from oats.identity import generate_session_id


@dataclass(slots=True)
class ProviderSession:
    session_id: str
    provider: str
    status: str
    started_at: datetime
    last_used_at: datetime


class ProviderSessionManager:
    """Own one reusable provider session for a Pi worker."""

    def __init__(self, *, provider: str) -> None:
        self.provider = provider
        self.status = "absent"
        self.failure_reason: str | None = None
        self._session: ProviderSession | None = None

    @property
    def session(self) -> ProviderSession | None:
        return self._session

    def ensure_session(self) -> ProviderSession:
        if self._session is not None and self.status == "ready":
            self._session.last_used_at = datetime.now(UTC)
            return self._session

        self.status = "starting"
        try:
            session = self._bootstrap_session()
        except Exception as exc:
            self.status = "failed"
            self.failure_reason = str(exc)
            raise

        self._session = session
        self.status = "ready"
        self.failure_reason = None
        return session

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
