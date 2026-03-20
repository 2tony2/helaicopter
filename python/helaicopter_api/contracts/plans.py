"""Contracts for plan API responses."""

from __future__ import annotations

from pydantic import BaseModel
from helaicopter_domain.ids import PlanId, SessionId
from helaicopter_domain.paths import EncodedProjectKey
from helaicopter_domain.vocab import ProviderName

PlanProvider = ProviderName


class PlanStepResponse(BaseModel):
    step: str
    status: str


class PlanSummaryResponse(BaseModel):
    """Lightweight plan listing item."""

    id: PlanId
    slug: str
    title: str
    preview: str
    provider: ProviderName
    timestamp: float
    model: str | None = None
    source_path: str | None = None
    session_id: SessionId | None = None
    project_path: EncodedProjectKey | None = None
    route_slug: str | None = None
    conversation_ref: str | None = None


class PlanDetailResponse(BaseModel):
    """Full plan content."""

    id: PlanId
    slug: str
    title: str
    content: str
    provider: ProviderName
    timestamp: float
    model: str | None = None
    source_path: str | None = None
    session_id: SessionId | None = None
    project_path: EncodedProjectKey | None = None
    route_slug: str | None = None
    conversation_ref: str | None = None
    explanation: str | None = None
    steps: list[PlanStepResponse] = []
