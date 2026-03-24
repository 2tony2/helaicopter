"""Root router – aggregates all sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from .analytics import analytics_router
from .conversation_dags import conversation_dags_router
from .conversations import conversations_router
from .database import database_router
from .evaluations import evaluations_router
from .evaluation_prompts import evaluation_prompts_router
from .gateway import gateway_router
from .history import history_router
from .orchestration import orchestration_router
from .ops import ops_router
from .plans import plans_router
from .projects import projects_router
from .subagents import subagents_router
from .subscriptions import subscriptions_router
from .tasks import tasks_router

root_router = APIRouter()


@root_router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Minimal liveness probe."""
    return {"status": "ok"}


root_router.include_router(ops_router)
root_router.include_router(analytics_router)
root_router.include_router(conversation_dags_router)
root_router.include_router(conversations_router)
root_router.include_router(database_router)
root_router.include_router(evaluations_router)
root_router.include_router(evaluation_prompts_router)
root_router.include_router(gateway_router)
root_router.include_router(history_router)
root_router.include_router(orchestration_router)
root_router.include_router(plans_router)
root_router.include_router(projects_router)
root_router.include_router(subagents_router)
root_router.include_router(subscriptions_router)
root_router.include_router(tasks_router)
