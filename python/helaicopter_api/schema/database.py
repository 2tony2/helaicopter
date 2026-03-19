"""Schemas for database introspection and status."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field
from helaicopter_domain.vocab import (
    DatabaseAvailability,
    DatabaseRefreshStatus,
    DatabaseRole,
    DatabaseStatusKey,
    RuntimeReadBackend,
)
from helaicopter_api.schema.common import CamelCaseHttpResponseModel, camel_case_request_config


class DatabaseColumnSchemaResponse(CamelCaseHttpResponseModel):
    name: str
    type: str
    nullable: bool = False
    default_value: str | None = None
    is_primary_key: bool = False
    references: str | None = None


class DatabaseTableSchemaResponse(CamelCaseHttpResponseModel):
    name: str
    row_count: int = 0
    size_bytes: int | None = None
    size_display: str | None = None
    columns: list[DatabaseColumnSchemaResponse] = []
    serving_class: str = "not-served"
    integration_type: str = "unclassified"
    fastapi_routes: list[str] = []
    sqlalchemy_model: str | None = None
    note: str | None = None


class DatabaseLoadMetricResponse(CamelCaseHttpResponseModel):
    label: str
    value: float | int | None = None
    display_value: str | None = None


class DatabaseArtifactStatusResponse(CamelCaseHttpResponseModel):
    key: DatabaseStatusKey
    label: str
    engine: str
    role: DatabaseRole
    availability: DatabaseAvailability
    health: str | None = None
    operational_status: str | None = None
    note: str | None = None
    error: str | None = None
    path: str | None = None
    target: str | None = None
    public_path: str | None = None
    docs_url: str | None = None
    table_count: int = 0
    size_bytes: int | None = None
    size_display: str | None = None
    inventory_summary: str | None = None
    load: list[DatabaseLoadMetricResponse] = []
    tables: list[DatabaseTableSchemaResponse] = []


class DatabaseRuntimeResponse(CamelCaseHttpResponseModel):
    analytics_read_backend: RuntimeReadBackend
    conversation_summary_read_backend: RuntimeReadBackend


class DatabaseArtifactsResponse(CamelCaseHttpResponseModel):
    frontend_cache: DatabaseArtifactStatusResponse = Field(
        validation_alias=AliasChoices("frontend_cache", "frontendCache"),
    )
    sqlite: DatabaseArtifactStatusResponse
    duckdb: DatabaseArtifactStatusResponse = Field(
        validation_alias=AliasChoices("duckdb", "legacy_duckdb", "legacyDuckdb"),
    )
    prefect_postgres: DatabaseArtifactStatusResponse = Field(
        validation_alias=AliasChoices("prefect_postgres", "prefectPostgres"),
    )


class DatabaseStatusResponse(CamelCaseHttpResponseModel):
    """Overall database status including refresh state."""

    status: DatabaseRefreshStatus
    trigger: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: float | None = None
    error: str | None = None
    last_successful_refresh_at: str | None = None
    idempotency_key: str | None = None
    scope_label: str | None = None
    window_days: int | None = None
    window_start: str | None = None
    window_end: str | None = None
    source_conversation_count: int | None = None
    refresh_interval_minutes: int = 360
    runtime: DatabaseRuntimeResponse
    databases: DatabaseArtifactsResponse


class DatabaseRefreshRequest(BaseModel):
    model_config = camel_case_request_config(extra="forbid")

    force: bool = False
    trigger: str = "manual"
    stale_after_seconds: int = Field(default=21_600, ge=0)
