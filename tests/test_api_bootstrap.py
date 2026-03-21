"""Tests for bootstrap wiring, middleware, and internal ops endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient

from helaicopter_api.bootstrap.services import BackendServices, LocalCache, build_services
from helaicopter_api.ports.app_sqlite import AppSqliteStore
from helaicopter_api.ports.claude_fs import (
    ConversationReader,
    HistoryReader,
    PlanReader,
    TaskReader,
)
from helaicopter_api.ports.codex_sqlite import CodexStore
from helaicopter_api.ports.evaluations import EvaluationJobRunner
from helaicopter_api.ports.orchestration import OatsRunStore
from helaicopter_api.server.config import Settings
from helaicopter_api.server.main import app, create_app
from helaicopter_api.server.middleware import REQUEST_ID_HEADER
from helaicopter_api.server.openapi_artifacts import generate_openapi_artifacts


@pytest.fixture()
def client():
    """TestClient that enters the lifespan context (populates app.state)."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Bootstrap / services
# ---------------------------------------------------------------------------


class TestBuildServices:
    def test_requires_explicit_settings(self):
        with pytest.raises(TypeError):
            build_services()

    def test_returns_backend_services(self, tmp_path):
        settings = Settings(project_root=tmp_path)
        svc = build_services(settings)
        assert isinstance(svc, BackendServices)
        assert svc.settings is settings

    def test_sqlite_engine_is_created(self, tmp_path):
        settings = Settings(project_root=tmp_path)
        svc = build_services(settings)
        assert str(svc.sqlite_engine.url).startswith("sqlite")
        svc.sqlite_engine.dispose()

    def test_openapi_artifacts_are_configured_under_repo_local_public_dir(self, tmp_path):
        settings = Settings(project_root=tmp_path)

        assert settings.openapi.artifacts_dir == tmp_path / "public" / "openapi"
        assert settings.openapi.json_path == tmp_path / "public" / "openapi" / "helaicopter-api.json"
        assert settings.openapi.yaml_path == tmp_path / "public" / "openapi" / "helaicopter-api.yaml"
        assert settings.openapi.json_url == "/openapi/helaicopter-api.json"
        assert settings.openapi.yaml_url == "/openapi/helaicopter-api.yaml"

    def test_claude_ports_are_wired(self, tmp_path):
        settings = Settings(project_root=tmp_path, claude_dir=tmp_path / ".claude")
        svc = build_services(settings)

        assert isinstance(svc.claude_conversation_reader, ConversationReader)
        assert isinstance(svc.claude_plan_reader, PlanReader)
        assert isinstance(svc.claude_history_reader, HistoryReader)
        assert isinstance(svc.claude_task_reader, TaskReader)
        assert isinstance(svc.app_sqlite_store, AppSqliteStore)
        assert isinstance(svc.codex_store, CodexStore)
        assert isinstance(svc.oats_run_store, OatsRunStore)
        assert isinstance(svc.evaluation_job_runner, EvaluationJobRunner)
        svc.sqlite_engine.dispose()

    def test_cache_operations(self):
        cache = LocalCache()
        cache.set("k", 42)
        assert cache.get("k") == 42
        cache.delete("k")
        assert cache.get("k") is None
        assert cache.get("missing", "default") == "default"

    def test_cache_entries_expire_after_ttl(self):
        cache = LocalCache()

        cache.set("ephemeral", 42, ttl_seconds=0.01)
        assert cache.get("ephemeral") == 42

        time.sleep(0.02)

        assert cache.get("ephemeral") is None


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class TestRequestIDMiddleware:
    def test_generates_request_id_when_absent(self, client):
        resp = client.get("/health")
        rid = resp.headers.get(REQUEST_ID_HEADER)
        assert rid is not None
        assert len(rid) == 32  # uuid4 hex

    def test_echoes_caller_supplied_request_id(self, client):
        custom_id = uuid.uuid4().hex
        resp = client.get("/health", headers={REQUEST_ID_HEADER: custom_id})
        assert resp.headers[REQUEST_ID_HEADER] == custom_id


class TestTimingMiddleware:
    def test_server_timing_header_present(self, client):
        resp = client.get("/health")
        st = resp.headers.get("Server-Timing")
        assert st is not None
        assert st.startswith("total;dur=")


# ---------------------------------------------------------------------------
# Internal ops endpoints
# ---------------------------------------------------------------------------


class TestOpsEndpoints:
    def test_ops_health(self, client):
        resp = client.get("/_ops/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_ops_ready(self, client):
        resp = client.get("/_ops/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert "ready" in body
        assert "checks" in body

    def test_ops_info(self, client):
        resp = client.get("/_ops/info")
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == "0.1.0"
        assert "python" in body
        assert "uptime_seconds" in body


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


class TestCORS:
    def test_cors_headers_on_preflight(self, client):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in resp.headers


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


class TestAppFactory:
    def test_create_app_wires_middleware(self):
        application = create_app()
        # Middleware stack is non-empty (CORS + Gzip + Timing + RequestID)
        assert len(application.user_middleware) >= 4

    def test_generate_openapi_artifacts_writes_json_and_yaml(self, tmp_path: Path) -> None:
        settings = Settings(project_root=tmp_path)
        outputs = generate_openapi_artifacts(settings=settings)

        assert outputs.json_path == tmp_path / "public" / "openapi" / "helaicopter-api.json"
        assert outputs.yaml_path == tmp_path / "public" / "openapi" / "helaicopter-api.yaml"
        assert outputs.json_path.exists()
        assert outputs.yaml_path.exists()

        json_text = outputs.json_path.read_text(encoding="utf-8")
        yaml_text = outputs.yaml_path.read_text(encoding="utf-8")

        assert '"title": "Helaicopter API"' in json_text
        assert '"openapi": "3.1.0"' in json_text
        assert "title: Helaicopter API" in yaml_text
        assert "/orchestration/prefect/flow-runs:" in yaml_text


class TestApiDocsNavigation:
    def test_sidebar_and_schema_page_link_to_generated_openapi_artifacts(self) -> None:
        sidebar_source = Path("src/components/layout/app-sidebar.tsx").read_text(encoding="utf-8")
        schema_page_source = Path("src/app/schema/page.tsx").read_text(encoding="utf-8")

        assert 'label: "API"' in sidebar_source
        assert 'href: "/schema"' in sidebar_source
        assert "/openapi/helaicopter-api.json" in schema_page_source
        assert "/openapi/helaicopter-api.yaml" in schema_page_source


class TestGatewayDirection:
    def test_gateway_direction_exposes_fastapi_first_platform_contract(self, client) -> None:
        response = client.get("/gateway/direction")

        assert response.status_code == 200
        body = response.json()
        assert body["gatewayDirection"] == "fastapi-first"
        assert body["frontendCallsVia"] == "fastapi"

        surfaces = {surface["key"]: surface for surface in body["surfaces"]}
        assert surfaces["fastapi"]["isPrimary"] is True
        assert "/orchestration/prefect" in surfaces["prefect"]["pathPrefixes"]
        assert surfaces["prefect"]["isPrimary"] is True
        assert surfaces["oats"]["isPrimary"] is False
        assert surfaces["cache"]["servingClass"] == "internal-only"
