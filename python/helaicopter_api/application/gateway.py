"""Backend-owned platform gateway direction metadata."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from helaicopter_db.models.oltp import OltpBase

from helaicopter_api.schema.gateway import GatewayDirectionResponse, GatewaySurfaceResponse


@dataclass(frozen=True, slots=True)
class TableIntegration:
    artifact_key: str
    table_name: str
    serving_class: str
    integration_type: str
    fastapi_routes: tuple[str, ...]
    note: str


_GATEWAY_SURFACES: tuple[GatewaySurfaceResponse, ...] = (
    GatewaySurfaceResponse(
        key="fastapi",
        owner="helaicopter_api",
        serving_class="entrypoint",
        integration_type="application-router",
        is_primary=True,
        path_prefixes=["/"],
        note="Single backend gateway for frontend, orchestration, database, and local artifact reads.",
    ),
    GatewaySurfaceResponse(
        key="frontend",
        owner="nextjs",
        serving_class="ui-only",
        integration_type="http-client",
        is_primary=True,
        path_prefixes=[],
        note="Browser traffic goes through FastAPI rather than calling storage systems or Prefect directly.",
    ),
    GatewaySurfaceResponse(
        key="sqlite",
        owner="helaicopter_db",
        serving_class="fastapi-data",
        integration_type="sqlite-store-and-sqlalchemy",
        is_primary=True,
        path_prefixes=[
            "/analytics",
            "/conversations",
            "/databases",
            "/evaluation-prompts",
            "/evaluations",
            "/plans",
            "/projects",
            "/subscriptions",
            "/tasks",
        ],
        note="Primary app-local metadata store for FastAPI-owned reads and settings.",
    ),
    GatewaySurfaceResponse(
        key="prefect",
        owner="prefect",
        serving_class="fastapi-proxy",
        integration_type="backend-http-adapter",
        is_primary=True,
        path_prefixes=["/orchestration/prefect"],
        note="Primary orchestration control plane exposed through backend-managed HTTP normalization.",
    ),
    GatewaySurfaceResponse(
        key="oats",
        owner="oats",
        serving_class="compatibility-surface",
        integration_type="artifact-store",
        is_primary=False,
        path_prefixes=["/orchestration/oats"],
        note="Repo-local orchestration artifacts remain available for compatibility and inspection, not as the primary control plane.",
    ),
    GatewaySurfaceResponse(
        key="duckdb",
        owner="helaicopter_db",
        serving_class="inspection-only",
        integration_type="duckdb-introspection",
        is_primary=False,
        path_prefixes=["/databases/status"],
        note="DuckDB remains an optional inspection artifact and is not a primary serving backend.",
    ),
    GatewaySurfaceResponse(
        key="cache",
        owner="helaicopter_api",
        serving_class="internal-only",
        integration_type="local-memory-cache",
        is_primary=False,
        path_prefixes=[],
        note="Short-term backend cache is an internal optimization layer and not a public API surface.",
    ),
)

_TABLE_INTEGRATIONS: tuple[TableIntegration, ...] = (
    TableIntegration(
        artifact_key="sqlite",
        table_name="refresh_runs",
        serving_class="fastapi-derived",
        integration_type="sqlalchemy",
        fastapi_routes=("/databases/status", "/databases/refresh"),
        note="Refresh bookkeeping is a backend-owned SQLite concern exposed through derived FastAPI database status endpoints.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="evaluation_prompts",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/evaluation-prompts",),
        note="Evaluation prompt records are served through FastAPI prompt-management endpoints.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="subscription_settings",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/subscriptions",),
        note="Subscription settings are mutable app state served through FastAPI settings endpoints.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="conversation_evaluations",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/evaluations",),
        note="Conversation evaluation jobs and reports are served through FastAPI evaluation endpoints.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="conversations",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/analytics", "/conversations", "/projects"),
        note="Conversation summaries are served through FastAPI list and analytics endpoints.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="conversation_messages",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/conversations",),
        note="Conversation message detail is served through FastAPI conversation record endpoints.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="message_blocks",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/conversations",),
        note="Message blocks are nested under FastAPI conversation detail responses.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="conversation_plans",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/conversations", "/plans"),
        note="Plan records are served through FastAPI plan and conversation detail endpoints.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="conversation_subagents",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/conversations", "/subagents"),
        note="Subagent records remain reachable through FastAPI conversation detail and subagent views.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="conversation_tasks",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/conversations", "/tasks"),
        note="Task payloads are served through FastAPI task and conversation detail endpoints.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="context_buckets",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/analytics", "/conversations"),
        note="Context bucket rollups are served through FastAPI analytics and conversation detail endpoints.",
    ),
    TableIntegration(
        artifact_key="sqlite",
        table_name="context_steps",
        serving_class="fastapi-data",
        integration_type="sqlite-store",
        fastapi_routes=("/analytics", "/conversations"),
        note="Context step detail is served through FastAPI analytics and conversation detail endpoints.",
    ),
)


def describe_gateway_direction() -> GatewayDirectionResponse:
    """Return the backend-owned gateway direction for the platform."""
    return GatewayDirectionResponse(surfaces=list(_GATEWAY_SURFACES))


def annotate_database_artifacts(databases: object) -> object:
    """Add table-level integration metadata to database status payloads."""
    if not isinstance(databases, dict):
        return databases

    annotated = dict(databases)
    for artifact_key, artifact in list(annotated.items()):
        if not isinstance(artifact, dict):
            continue
        artifact_payload = dict(artifact)
        tables = artifact_payload.get("tables")
        if isinstance(tables, list):
            artifact_payload["tables"] = [
                _annotate_table_payload(artifact_key=artifact_key, table=table)
                for table in tables
            ]
        annotated[artifact_key] = artifact_payload
    return annotated


def _annotate_table_payload(*, artifact_key: str, table: object) -> object:
    if not isinstance(table, dict):
        return table

    payload = dict(table)
    table_name = payload.get("name")
    if not isinstance(table_name, str):
        return payload

    integration = _table_integration_map().get((artifact_key, table_name))
    sqlalchemy_model = _sqlalchemy_models_by_table().get(table_name) if artifact_key == "sqlite" else None

    if integration is None:
        if artifact_key == "duckdb":
            payload.setdefault("servingClass", "schema-inspection")
            payload.setdefault("integrationType", "duckdb-inspection")
            payload.setdefault("fastapiRoutes", ["/databases/status"])
            payload.setdefault("sqlalchemyModel", None)
            payload.setdefault(
                "note",
                "DuckDB tables are surfaced for schema inspection through the database status API, not direct record serving.",
            )
            return payload

        payload.setdefault("servingClass", "not-served")
        payload.setdefault("integrationType", "unclassified")
        payload.setdefault("fastapiRoutes", [])
        payload.setdefault("sqlalchemyModel", sqlalchemy_model)
        payload.setdefault(
            "note",
            "No direct FastAPI serving path is declared for this table yet.",
        )
        return payload

    payload.setdefault("servingClass", integration.serving_class)
    payload.setdefault("integrationType", integration.integration_type)
    payload.setdefault("fastapiRoutes", list(integration.fastapi_routes))
    payload.setdefault("sqlalchemyModel", sqlalchemy_model)
    payload.setdefault("note", integration.note)
    return payload


@lru_cache(maxsize=1)
def _table_integration_map() -> dict[tuple[str, str], TableIntegration]:
    return {
        (integration.artifact_key, integration.table_name): integration
        for integration in _TABLE_INTEGRATIONS
    }


@lru_cache(maxsize=1)
def _sqlalchemy_models_by_table() -> dict[str, str]:
    models: dict[str, str] = {}
    for mapper in OltpBase.registry.mappers:
        table_name = getattr(mapper.local_table, "name", None)
        if isinstance(table_name, str):
            models[table_name] = mapper.class_.__name__
    return models
