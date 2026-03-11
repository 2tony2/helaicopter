from __future__ import annotations

from typing import Any, TypedDict


class ExportCostBreakdown(TypedDict):
    inputCost: float
    outputCost: float
    cacheWriteCost: float
    cacheReadCost: float
    totalCost: float


class ExportConversationEnvelope(TypedDict):
    type: str
    summary: dict[str, Any]
    detail: dict[str, Any] | None
    tasks: list[Any]
    cost: ExportCostBreakdown
