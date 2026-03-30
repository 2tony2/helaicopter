"""FastMCP adapter for the external-agent backend surface."""

from __future__ import annotations

from fastapi import FastAPI
from fastmcp import FastMCP
from fastmcp.server.openapi import MCPType, RouteMap
from fastmcp.server.openapi import OpenAPIResource, OpenAPIResourceTemplate, OpenAPITool
from fastmcp.server.openapi.routing import HTTPRoute

MCP_MOUNT_PATH = "/mcp"

_MCP_EXCLUDED_PREFIXES = (
    "/auth",
    "/workers",
)

_MCP_RESOURCE_PATHS = {
    "/health",
    "/_ops/health",
    "/_ops/ready",
    "/_ops/info",
    "/analytics",
    "/conversation-dags",
    "/conversations",
    "/history",
    "/plans",
    "/projects",
    "/orchestration/oats",
    "/orchestration/oats/facts",
    "/dispatch/queue",
    "/dispatch/history",
    "/evaluation-prompts",
    "/gateway/direction",
    "/subscription-settings",
}

_MCP_RESOURCE_TEMPLATE_PATHS = {
    "/conversations/by-ref/{conversation_ref}",
    "/conversations/{project_path}/{session_id}",
    "/conversations/{project_path}/{session_id}/dag",
    "/conversations/{project_path}/{session_id}/subagents/{agent_id}",
    "/conversations/{project_path}/{session_id}/evaluations",
    "/plans/{slug}",
    "/tasks/{session_id}",
    "/orchestration/oats/{run_id}",
}

_MCP_TOOL_PATHS = {
    ("POST", "/conversations/{project_path}/{session_id}/evaluations"),
}

_MCP_EXCLUDED_MUTATIONS = {
    ("POST", "/databases/refresh"),
    ("POST", "/evaluation-prompts"),
    ("PATCH", "/evaluation-prompts/{prompt_id}"),
    ("DELETE", "/evaluation-prompts/{prompt_id}"),
    ("PATCH", "/subscription-settings"),
}


def classify_mcp_http_route(method: str, path: str) -> MCPType | None:
    """Return the MCP component type for a backend HTTP route.

    ``None`` means the route must remain absent from the external-agent MCP
    surface.
    """

    normalized_method = method.upper()

    if any(path.startswith(prefix) for prefix in _MCP_EXCLUDED_PREFIXES):
        return None

    if normalized_method != "GET" and path.startswith("/orchestration/oats/"):
        return None

    if (normalized_method, path) in _MCP_EXCLUDED_MUTATIONS:
        return None

    if (normalized_method, path) in _MCP_TOOL_PATHS:
        return MCPType.TOOL

    if normalized_method == "GET" and path in _MCP_RESOURCE_PATHS:
        return MCPType.RESOURCE

    if normalized_method == "GET" and path in _MCP_RESOURCE_TEMPLATE_PATHS:
        return MCPType.RESOURCE_TEMPLATE

    return None


def is_mcp_http_route_exposed(method: str, path: str) -> bool:
    """Report whether a backend HTTP route should be published over MCP."""

    return classify_mcp_http_route(method, path) is not None


def _route_map_fn(route: HTTPRoute, current_type: MCPType) -> MCPType | None:
    del current_type
    return classify_mcp_http_route(route.method, route.path)


def _component_fn(
    route: HTTPRoute,
    component: OpenAPITool | OpenAPIResource | OpenAPIResourceTemplate,
) -> None:
    del route
    component.tags.update({"helaicopter", "external-agent"})


def build_mcp_server(app: FastAPI) -> FastMCP:
    """Create the curated external-agent MCP server from the FastAPI app."""

    return FastMCP.from_fastapi(
        app=app,
        name="Helaicopter External Agent Surface",
        route_maps=[RouteMap(mcp_type=MCPType.EXCLUDE)],
        route_map_fn=_route_map_fn,
        mcp_component_fn=_component_fn,
        tags={"helaicopter", "external-agent"},
    )
