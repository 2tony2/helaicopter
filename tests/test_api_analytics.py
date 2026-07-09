"""Endpoint tests for the analytics API."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import sqlite3
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient

from helaicopter_api.application import analytics as analytics_application
from helaicopter_api.application.conversation_refs import derive_route_slug
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.app_sqlite import HistoricalConversationSummary
from helaicopter_api.server.config import Settings
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


def _write_hermes_analytics_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE sessions (
              id TEXT PRIMARY KEY,
              source TEXT NOT NULL,
              model TEXT,
              started_at REAL NOT NULL,
              ended_at REAL,
              message_count INTEGER DEFAULT 0,
              tool_call_count INTEGER DEFAULT 0,
              input_tokens INTEGER DEFAULT 0,
              output_tokens INTEGER DEFAULT 0,
              cache_read_tokens INTEGER DEFAULT 0,
              cache_write_tokens INTEGER DEFAULT 0,
              reasoning_tokens INTEGER DEFAULT 0,
              title TEXT
            );
            CREATE TABLE messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id TEXT NOT NULL,
              role TEXT NOT NULL,
              content TEXT,
              tool_call_id TEXT,
              tool_calls TEXT,
              tool_name TEXT,
              timestamp REAL NOT NULL,
              token_count INTEGER,
              reasoning TEXT,
              reasoning_content TEXT
            );
            """
        )
        connection.execute(
            """
            INSERT INTO sessions (
              id, source, model, started_at, ended_at, message_count,
              tool_call_count, input_tokens, output_tokens, cache_read_tokens,
              cache_write_tokens, reasoning_tokens, title
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "hermes-analytics-1",
                "discord",
                "gpt-5.5",
                1_783_000_000.0,
                1_783_000_090.0,
                1,
                0,
                123,
                45,
                6,
                7,
                8,
                "Hermes analytics",
            ),
        )
        connection.commit()
    finally:
        connection.close()


@contextmanager
def analytics_client(
    rows: list[HistoricalConversationSummary],
    *,
    warehouse_rows: list[HistoricalConversationSummary] | None = None,
    settings: Settings | None = None,
) -> Iterator[tuple[TestClient, StubStore]]:
    store = StubStore(rows)
    application = create_app()
    application.dependency_overrides[get_services] = lambda: _services_stub(
        app_sqlite_store=store,
        settings=settings,
    )
    original_loader = analytics_application.list_warehouse_historical_conversations
    analytics_application.list_warehouse_historical_conversations = lambda _services: list(warehouse_rows or [])
    try:
        with TestClient(application) as client:
            yield client, store
    finally:
        analytics_application.list_warehouse_historical_conversations = original_loader
        application.dependency_overrides.clear()


class TestAnalyticsEndpoint:
    def test_endpoint_includes_live_hermes_state_db_rows(self, tmp_path: Path) -> None:
        hermes_dir = tmp_path / ".hermes"
        _write_hermes_analytics_db(hermes_dir / "state.db")
        settings = Settings(project_root=tmp_path, hermes_dir=hermes_dir)

        with analytics_client([], settings=settings) as (client, _store):
            response = client.get("/analytics", params={"provider": "hermes"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["total_conversations"] == 1
        assert payload["total_input_tokens"] == 123
        assert payload["total_output_tokens"] == 45
        assert payload["total_cache_creation_tokens"] == 7
        assert payload["total_cache_read_tokens"] == 6
        assert payload["total_reasoning_tokens"] == 8
        assert payload["model_breakdown_by_provider"]["gpt-5.5"]["hermes"] == 1

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
            "hermes",
        ]
        assert analytics_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/AnalyticsDataResponse"
        )
