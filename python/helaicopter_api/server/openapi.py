"""OpenAPI metadata for the Helaicopter API."""

from __future__ import annotations

OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "health", "description": "Liveness and readiness probes."},
    {
        "name": "analytics",
        "description": "Aggregated token, cost, and activity analytics. Legacy snake_case HTTP surface deferred from Wave 7 camelCase alignment.",
    },
    {"name": "conversation-dags", "description": "Conversation DAG summaries and backend-built graph stats."},
    {
        "name": "conversations",
        "description": "Conversation summaries and full detail reads. Legacy snake_case HTTP surface deferred from Wave 7 camelCase alignment.",
    },
    {"name": "databases", "description": "Database refresh state and artifact inspection."},
    {"name": "evaluations", "description": "Evaluation prompt management and conversation review workflows."},
    {"name": "gateway", "description": "Backend-owned API gateway direction across frontend, stores, cache, and database surfaces."},
    {"name": "history", "description": "Merged CLI history from Claude and Codex."},
    {"name": "plans", "description": "Saved plan listings and detail views."},
    {"name": "projects", "description": "Project lists derived from conversation data."},
    {"name": "subscriptions", "description": "Provider subscription settings and monthly cost controls."},
    {"name": "tasks", "description": "Task payloads associated with Claude sessions."},
]

TITLE = "Helaicopter API"
DESCRIPTION = "Local-machine backend for the Helaicopter dashboard."
VERSION = "0.1.0"
