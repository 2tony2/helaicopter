"""Tests for the external-agent FastMCP surface."""

from __future__ import annotations

import asyncio

from fastapi.routing import Mount
from fastapi.testclient import TestClient

from helaicopter_api.server.main import create_app
from helaicopter_api.server.mcp import is_mcp_http_route_exposed


def test_create_app_mounts_mcp_subapp() -> None:
    application = create_app()

    mounted_paths = {
        route.path
        for route in application.routes
        if isinstance(route, Mount)
    }

    assert "/mcp" in mounted_paths


def test_mcp_path_is_served_by_the_app() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/mcp")

    assert response.status_code != 404


def test_mcp_route_allowlist_is_curated_for_external_agents() -> None:
    assert is_mcp_http_route_exposed("GET", "/analytics") is True
    assert is_mcp_http_route_exposed("GET", "/conversations") is True
    assert is_mcp_http_route_exposed(
        "POST",
        "/conversations/{project_path}/{session_id}/evaluations",
    ) is True

    assert is_mcp_http_route_exposed("GET", "/auth/credentials") is False
    assert is_mcp_http_route_exposed("POST", "/workers/register") is False
    assert is_mcp_http_route_exposed("POST", "/databases/refresh") is False
    assert is_mcp_http_route_exposed("POST", "/orchestration/oats/{run_id}/pause") is False


def test_generated_mcp_inventory_matches_the_curated_surface() -> None:
    application = create_app()

    async def collect_component_names() -> tuple[set[str], set[str], set[str]]:
        resources = await application.state.mcp_server.get_resources()
        templates = await application.state.mcp_server.get_resource_templates()
        tools = await application.state.mcp_server.get_tools()
        return set(resources), set(templates), set(tools)

    resources, templates, tools = asyncio.run(collect_component_names())
    all_names = resources | templates | tools

    assert any("analytics" in name for name in resources)
    assert any("conversations_detail" in name for name in templates)
    assert any("conversation_evaluations_create" in name for name in tools)

    assert not any("credential" in name for name in all_names)
    assert not any("worker" in name for name in all_names)
