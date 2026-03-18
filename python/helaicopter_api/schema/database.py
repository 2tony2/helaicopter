"""Schemas for database introspection and status."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DatabaseStatusKey = Literal["sqlite", "legacy_duckdb"]
DatabaseRole = Literal["metadata", "legacy_debug"]
DatabaseAvailability = Literal["ready", "missing", "unreachable"]


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class DatabaseCamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )


class DatabaseColumnSchemaResponse(DatabaseCamelModel):
    name: str
    type: str
    nullable: bool = False
    default_value: str | None = None
    is_primary_key: bool = False
    references: str | None = None


class DatabaseTableSchemaResponse(DatabaseCamelModel):
    name: str
    row_count: int = 0
    columns: list[DatabaseColumnSchemaResponse] = Field(default_factory=list)


class DatabaseArtifactStatusResponse(DatabaseCamelModel):
    key: DatabaseStatusKey
    label: str
    engine: str
    role: DatabaseRole
    availability: DatabaseAvailability
    note: str | None = None
    error: str | None = None
    path: str | None = None
    target: str | None = None
    public_path: str | None = None
    docs_url: str | None = None
    table_count: int = 0
    tables: list[DatabaseTableSchemaResponse] = Field(default_factory=list)


class DatabaseRuntimeResponse(DatabaseCamelModel):
    analytics_read_backend: Literal["legacy"]
    conversation_summary_read_backend: Literal["legacy"]


class DatabaseArtifactsResponse(DatabaseCamelModel):
    sqlite: DatabaseArtifactStatusResponse
    legacy_duckdb: DatabaseArtifactStatusResponse = Field(alias="legacyDuckdb")


class DatabaseStatusResponse(DatabaseCamelModel):
    """Overall database status including refresh state."""

    status: Literal["idle", "running", "completed", "failed"]
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


class DatabaseRefreshRequest(DatabaseCamelModel):
    force: bool = False
    trigger: str = "manual"
    stale_after_seconds: int = Field(default=21_600, ge=0)
