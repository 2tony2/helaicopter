"""Common response envelopes, error models, and pagination helpers."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")
ExtraPolicy = Literal["allow", "forbid", "ignore"]


def to_camel(value: str) -> str:
    """Convert snake_case field names to camelCase aliases."""
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


def camel_case_request_config(*, extra: ExtraPolicy) -> ConfigDict:
    """Build config for HTTP request/query models that accept camelCase only."""
    return ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=False,
        serialize_by_alias=True,
        loc_by_alias=True,
        extra=extra,
    )


class CamelCaseHttpResponseModel(BaseModel):
    """HTTP response model that accepts snake_case internally and emits camelCase."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
        loc_by_alias=True,
    )


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class ErrorDetail(CamelCaseHttpResponseModel):
    """Structured error detail returned inside an envelope."""

    code: str = Field(..., description="Machine-readable error code.")
    message: str = Field(..., description="Human-readable description.")
    detail: str | None = Field(None, description="Optional extended context.")


# ---------------------------------------------------------------------------
# Envelopes
# ---------------------------------------------------------------------------


class Envelope(CamelCaseHttpResponseModel, Generic[T]):
    """Standard single-item response wrapper."""

    ok: bool = True
    data: T
    error: ErrorDetail | None = None


class ListEnvelope(CamelCaseHttpResponseModel, Generic[T]):
    """Standard list response wrapper with optional paging metadata."""

    ok: bool = True
    data: list[T] = []
    total: int | None = Field(None, description="Total count when pagination is used.")
    offset: int | None = None
    limit: int | None = None
    error: ErrorDetail | None = None


# ---------------------------------------------------------------------------
# Pagination / filtering query helpers
# ---------------------------------------------------------------------------


class PaginationParams(BaseModel):
    """Reusable offset/limit pagination parameters."""

    offset: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=500)


class SortParam(BaseModel):
    """Generic sort descriptor."""

    field: str
    direction: str = Field("desc", pattern=r"^(asc|desc)$")
