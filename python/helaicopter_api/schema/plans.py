"""Schemas for conversation plans."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PlanProvider = Literal["claude", "codex"]


class PlanStepResponse(BaseModel):
    step: str
    status: str


class PlanSummaryResponse(BaseModel):
    """Lightweight plan listing item."""

    id: str
    slug: str
    title: str
    preview: str
    provider: PlanProvider
    timestamp: float
    model: str | None = None
    source_path: str | None = None
    session_id: str | None = None
    project_path: str | None = None


class PlanDetailResponse(BaseModel):
    """Full plan content."""

    id: str
    slug: str
    title: str
    content: str
    provider: PlanProvider
    timestamp: float
    model: str | None = None
    source_path: str | None = None
    session_id: str | None = None
    project_path: str | None = None
    explanation: str | None = None
    steps: list[PlanStepResponse] = Field(default_factory=list)
