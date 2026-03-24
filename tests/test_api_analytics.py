"""Endpoint tests for the analytics API."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Iterator

from fastapi.testclient import TestClient

from helaicopter_api.application import analytics as analytics_application
from helaicopter_api.application.conversation_refs import derive_route_slug
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.app_sqlite import HistoricalConversationSummary
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app


def _summary(
    conversation_id: str,
    *,
    provider: str = "claude",
    project_path: str = "-Users-tony-Code-helaicopter",
    started_at: str,
    ended_at: str,
    model: str | None,
    total_input_tokens: int = 0,
) -> HistoricalConversationSummary:
    return HistoricalConversationSummary(
        conversation_id=conversation_id,
        provider=provider,
        session_id=f"session-{conversation_id}",
        project_path=project_path,
        project_name="helaicopter",
        first_message="Ship the analytics API",
        route_slug=derive_route_slug("Ship the analytics API"),
        started_at=started_at,
        ended_at=ended_at,
        message_count=3,
        model=model,
        total_input_tokens=total_input_tokens,
        task_count=1,
    )


class StubStore:
    def __init__(self, rows: list[HistoricalConversationSummary]) -> None:
        self._rows = rows
        self.calls: list[dict[str, object]] = []

    def list_historical_conversations(self, **kwargs: object) -> list[HistoricalConversationSummary]:
        self.calls.append(kwargs)
        return list(self._rows)


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def analytics_client(
    rows: list[HistoricalConversationSummary],
    *,
    warehouse_rows: list[HistoricalConversationSummary] | None = None,
) -> Iterator[tuple[TestClient, StubStore]]:
    store = StubStore(rows)
    application = create_app()
    application.dependency_overrides[get_services] = lambda: _services_stub(app_sqlite_store=store)
    original_loader = analytics_application.list_warehouse_historical_conversations
    analytics_application.list_warehouse_historical_conversations = lambda _services: list(warehouse_rows or [])
    try:
        with TestClient(application) as client:
            yield client, store
    finally:
        analytics_application.list_warehouse_historical_conversations = original_loader
        application.dependency_overrides.clear()


class TestAnalyticsEndpoint:
    def test_endpoint_applies_days_and_provider_filters_without_backend_selector(self) -> None:
        now = datetime.now(UTC)
        recent_claude = _summary(
            "claude-recent",
            started_at=(now - timedelta(hours=18)).isoformat().replace("+00:00", "Z"),
            ended_at=(now - timedelta(hours=17)).isoformat().replace("+00:00", "Z"),
            model="claude-sonnet-4-5-20250929",
            total_input_tokens=10_000,
        )
        recent_codex = _summary(
            "codex-recent",
            provider="codex",
            project_path="codex:-Users-tony-Code-helaicopter",
            started_at=(now - timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
            ended_at=(now - timedelta(hours=5)).isoformat().replace("+00:00", "Z"),
            model="gpt-5",
            total_input_tokens=20_000,
        )
        old_codex = _summary(
            "codex-old",
            provider="codex",
            project_path="codex:-Users-tony-Code-helaicopter",
            started_at=(now - timedelta(days=5)).isoformat().replace("+00:00", "Z"),
            ended_at=(now - timedelta(days=5, hours=-1)).isoformat().replace("+00:00", "Z"),
            model="gpt-5",
            total_input_tokens=30_000,
        )

        with analytics_client([recent_claude, recent_codex, old_codex]) as (client, store):
            response = client.get("/analytics", params={"days": 1, "provider": "codex"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["total_conversations"] == 1
        assert payload["total_input_tokens"] == 20_000
        assert payload["cost_breakdown_by_provider"]["codex"]["input_cost"] == 0.025
        assert "claude" not in payload["cost_breakdown_by_provider"]
        assert store.calls == [{}]

    def test_endpoint_supports_all_provider_and_validates_query_params(self) -> None:
        now = datetime.now(UTC)
        rows = [
            _summary(
                "claude-recent",
                started_at=(now - timedelta(hours=18)).isoformat().replace("+00:00", "Z"),
                ended_at=(now - timedelta(hours=17)).isoformat().replace("+00:00", "Z"),
                model="claude-sonnet-4-5-20250929",
                total_input_tokens=10_000,
            ),
            _summary(
                "codex-recent",
                provider="codex",
                project_path="codex:-Users-tony-Code-helaicopter",
                started_at=(now - timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
                ended_at=(now - timedelta(hours=5)).isoformat().replace("+00:00", "Z"),
                model="gpt-5",
                total_input_tokens=20_000,
            ),
            _summary(
                "openclaw-recent",
                provider="openclaw",
                project_path="openclaw:agent:main",
                started_at=(now - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
                ended_at=(now - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
                model="openclaw-v1",
                total_input_tokens=15_000,
            ),
        ]

        with analytics_client(rows) as (client, _store):
            response = client.get("/analytics", params={"provider": "all"})
            openclaw = client.get("/analytics", params={"provider": "openclaw"})
            invalid_provider = client.get("/analytics", params={"provider": "openai"})
            invalid_days = client.get("/analytics", params={"days": 0})

        assert response.status_code == 200
        assert response.json()["total_conversations"] == 3
        assert openclaw.status_code == 200
        assert openclaw.json()["total_conversations"] == 1

        assert invalid_provider.status_code == 422
        assert invalid_days.status_code == 422

    def test_endpoint_supplements_recent_window_from_sqlite_without_double_counting(self) -> None:
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        historical_row = _summary(
            "claude-historical",
            started_at=(now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
            ended_at=(now - timedelta(days=2, hours=-1)).isoformat().replace("+00:00", "Z"),
            model="claude-sonnet-4-5-20250929",
            total_input_tokens=11_000,
        )
        recent_warehouse_row = _summary(
            "codex-recent",
            provider="codex",
            project_path="codex:-Users-tony-Code-helaicopter",
            started_at=(now - timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
            ended_at=(now - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
            model="gpt-5",
            total_input_tokens=20_000,
        )
        recent_sqlite_row = _summary(
            "codex-recent",
            provider="codex",
            project_path="codex:-Users-tony-Code-helaicopter",
            started_at=(now - timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
            ended_at=(now - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
            model="gpt-5",
            total_input_tokens=24_000,
        )
        newest_sqlite_only_row = _summary(
            "claude-newest",
            started_at=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            ended_at=(now - timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            model="claude-sonnet-4-5-20250929",
            total_input_tokens=7_000,
        )

        with analytics_client(
            [recent_sqlite_row, newest_sqlite_only_row],
            warehouse_rows=[historical_row, recent_warehouse_row],
        ) as (client, store):
            response = client.get("/analytics", params={"days": 7})

        assert response.status_code == 200
        payload = response.json()
        assert payload["total_conversations"] == 3
        assert payload["total_input_tokens"] == 42_000
        assert store.calls == [{}]

    def test_openapi_exposes_explicit_analytics_parameters_and_response_schema(self) -> None:
        with analytics_client([]) as (client, _store):
            response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        analytics_get = schema["paths"]["/analytics"]["get"]

        parameters = {param["name"]: param for param in analytics_get["parameters"]}
        assert set(parameters) == {"days", "provider"}
        assert parameters["days"]["schema"]["anyOf"][0]["minimum"] == 1
        assert parameters["provider"]["schema"]["anyOf"][0]["enum"] == [
            "all",
            "claude",
            "codex",
            "openclaw",
        ]
        assert analytics_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/AnalyticsDataResponse"
        )
