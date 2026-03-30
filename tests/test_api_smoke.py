"""Smoke tests for the Helaicopter API scaffold."""

from fastapi.testclient import TestClient

from helaicopter_api.server.main import app, create_app


def test_create_app_returns_fastapi_instance() -> None:
    application = create_app()
    assert application.title == "Helaicopter API"


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_available() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Helaicopter API"
    assert "/health" in schema["paths"]
    assert "/orchestration/oats" not in schema["paths"]
    assert "/dispatch/queue" not in schema["paths"]
    assert "/workers" not in schema["paths"]
