"""Endpoint tests for the subscription settings API."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

from fastapi.testclient import TestClient

from helaicopter_api.adapters.app_sqlite import SqliteAppStore
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app


@contextmanager
def subscription_client(db_path: Path) -> Iterator[tuple[TestClient, SqliteAppStore]]:
    store = SqliteAppStore(db_path=db_path)
    application = create_app()
    application.dependency_overrides[get_services] = lambda: SimpleNamespace(app_sqlite_store=store)
    try:
        with TestClient(application) as client:
            yield client, store
    finally:
        application.dependency_overrides.clear()


class TestSubscriptionSettingsEndpoint:
    def test_get_returns_default_settings_when_db_is_missing(self, tmp_path: Path) -> None:
        with subscription_client(tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite") as (
            client,
            _store,
        ):
            response = client.get("/subscription-settings")

        assert response.status_code == 200
        payload = response.json()
        assert payload["claude"]["hasSubscription"] is True
        assert payload["claude"]["monthlyCost"] == 200.0
        assert payload["codex"]["hasSubscription"] is True
        assert payload["codex"]["monthlyCost"] == 200.0

    def test_patch_persists_updates_and_returns_merged_settings(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"

        with subscription_client(db_path) as (client, _store):
            patch_response = client.patch(
                "/subscription-settings",
                json={
                    "claude": {
                        "provider": "claude",
                        "hasSubscription": False,
                        "monthlyCost": 123.45,
                        "updatedAt": "2026-03-17T10:00:00Z",
                    }
                },
            )
            get_response = client.get("/subscription-settings")

        assert patch_response.status_code == 200
        patch_payload = patch_response.json()
        assert patch_payload["claude"]["provider"] == "claude"
        assert patch_payload["claude"]["hasSubscription"] is False
        assert patch_payload["claude"]["monthlyCost"] == 123.45
        assert patch_payload["codex"]["provider"] == "codex"
        assert patch_payload["codex"]["hasSubscription"] is True
        assert patch_payload["codex"]["monthlyCost"] == 200.0

        assert get_response.status_code == 200
        assert get_response.json() == patch_payload

    def test_patch_validates_monthly_cost_and_rejects_unknown_fields(self, tmp_path: Path) -> None:
        with subscription_client(tmp_path / "subscription-settings.sqlite") as (client, _store):
            negative_cost = client.patch(
                "/subscription-settings",
                json={"claude": {"hasSubscription": True, "monthlyCost": -1}},
            )
            unknown_field = client.patch(
                "/subscription-settings",
                json={"claude": {"hasSubscription": True, "monthlyCost": 10, "seatCount": 2}},
            )

        assert negative_cost.status_code == 422
        assert unknown_field.status_code == 422

    def test_openapi_exposes_explicit_subscription_request_and_response_models(self, tmp_path: Path) -> None:
        with subscription_client(tmp_path / "subscription-settings.sqlite") as (client, _store):
            response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        subscription_get = schema["paths"]["/subscription-settings"]["get"]
        subscription_patch = schema["paths"]["/subscription-settings"]["patch"]

        assert subscription_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/SubscriptionSettingsResponse"
        )
        assert subscription_patch["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/SubscriptionSettingsUpdateRequest"
        )
        assert subscription_patch["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/SubscriptionSettingsResponse"
        )
