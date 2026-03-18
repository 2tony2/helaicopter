"""Common response envelopes, error models, and pagination helpers."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    """Structured error detail returned inside an envelope."""

    code: str = Field(..., description="Machine-readable error code.")
    message: str = Field(..., description="Human-readable description.")
    detail: str | None = Field(None, description="Optional extended context.")


# ---------------------------------------------------------------------------
# Envelopes
# ---------------------------------------------------------------------------


class Envelope(BaseModel, Generic[T]):
    """Standard single-item response wrapper."""

    ok: bool = True
    data: T
    error: ErrorDetail | None = None


class ListEnvelope(BaseModel, Generic[T]):
    """Standard list response wrapper with optional paging metadata."""

    ok: bool = True
    data: list[T] = Field(default_factory=list)
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
