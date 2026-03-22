"""Additional integration coverage for the /analytics endpoint (empty state)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from fastapi.testclient import TestClient

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app


class _EmptyStore:
    def list_historical_conversations(self, **_kwargs: object) -> list[object]:  # pragma: no cover - trivial stub
        return []


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def _client() -> Iterator[TestClient]:
    application = create_app()
    application.dependency_overrides[get_services] = lambda: _services_stub(app_sqlite_store=_EmptyStore())
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()


def test_analytics_empty_state_returns_zeroes() -> None:
    with _client() as client:
        response = client.get("/analytics", params={"days": 7})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_conversations"] == 0
    assert payload["estimated_cost"] == 0
    assert payload["time_series"]["daily"] == []
    assert payload["daily_usage"] == []

