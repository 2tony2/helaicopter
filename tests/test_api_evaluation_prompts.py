"""Endpoint tests for evaluation prompt management."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient

from helaicopter_api.adapters.app_sqlite import SqliteAppStore
from helaicopter_api.application.evaluation_prompts import resolve_evaluation_prompt
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app


def _create_prompt_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE evaluation_prompts (
              prompt_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              description TEXT,
              prompt_text TEXT NOT NULL,
              is_default INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO evaluation_prompts (
              prompt_id,
              name,
              description,
              prompt_text,
              is_default,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "prompt-1",
                "Failure-focused review",
                "Inspect failed tool calls.",
                "Review every failed tool call and propose better recovery steps.",
                0,
                "2026-03-17T10:00:00+00:00",
                "2026-03-17T10:00:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def evaluation_prompt_client(db_path: Path) -> Iterator[tuple[TestClient, SqliteAppStore]]:
    store = SqliteAppStore(db_path=db_path)
    application = create_app()
    application.dependency_overrides[get_services] = lambda: _services_stub(app_sqlite_store=store)
    try:
        with TestClient(application) as client:
            yield client, store
    finally:
        application.dependency_overrides.clear()


class TestEvaluationPromptEndpoints:
    def test_get_returns_default_prompt_and_seeds_it_when_db_exists(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_prompt_db(db_path)

        with evaluation_prompt_client(db_path) as (client, store):
            response = client.get("/evaluation-prompts")
            default_prompt = store.get_evaluation_prompt("default-conversation-review")

        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["promptId"] == "default-conversation-review"
        assert payload[0]["isDefault"] is True
        assert payload[1]["promptId"] == "prompt-1"
        assert default_prompt is not None
        assert default_prompt.is_default is True

    def test_get_returns_ephemeral_default_prompt_when_db_is_missing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"

        with evaluation_prompt_client(db_path) as (client, _store):
            response = client.get("/evaluation-prompts")

        assert response.status_code == 200
        assert response.json() == [
            {
                "promptId": "default-conversation-review",
                "name": "Default Conversation Review",
                "description": "Default review prompt for diagnosing instruction quality and conversation flow.",
                "promptText": (
                    "Review this assistant conversation as an operator trying to improve future prompts, "
                    "instructions, and conversation flow.\n\n"
                    "Focus on:\n"
                    "- unclear or under-specified user instructions\n"
                    "- avoidable tool failures and recovery quality\n"
                    "- places where the assistant should have clarified sooner\n"
                    "- bloated or distracting turns that increased cost without moving the task forward\n"
                    "- concrete rewrites that would make the next run cleaner\n\n"
                    "Return markdown with these sections:\n"
                    "## Executive Summary\n"
                    "## Instruction Problems\n"
                    "## Conversation Flow Problems\n"
                    "## Concrete Prompt Improvements\n"
                    "## Concrete Recovery Improvements\n"
                    "## Suggested Better Opening Prompt\n"
                    "## Top 3 Highest-Leverage Changes\n\n"
                    "Every recommendation should be concrete, actionable, and tied to specific message ids or tool calls when possible."
                ),
                "isDefault": True,
                "createdAt": response.json()[0]["createdAt"],
                "updatedAt": response.json()[0]["updatedAt"],
            }
        ]

    def test_post_creates_prompt_and_patch_updates_it(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_prompt_db(db_path)

        with evaluation_prompt_client(db_path) as (client, _store):
            create_response = client.post(
                "/evaluation-prompts",
                json={
                    "name": "  Reviewer Sweep  ",
                    "description": "  Focus on risky turns.  ",
                    "promptText": "  Find the weakest handoffs.  ",
                },
            )
            prompt_id = create_response.json()["promptId"]
            update_response = client.patch(
                f"/evaluation-prompts/{prompt_id}",
                json={
                    "name": "Reviewer Sweep v2",
                    "description": "",
                    "promptText": "Highlight avoidable detours.",
                },
            )

        assert create_response.status_code == 201
        assert create_response.json()["name"] == "Reviewer Sweep"
        assert create_response.json()["description"] == "Focus on risky turns."
        assert create_response.json()["promptText"] == "Find the weakest handoffs."
        assert create_response.json()["isDefault"] is False

        assert update_response.status_code == 200
        assert update_response.json()["promptId"] == prompt_id
        assert update_response.json()["name"] == "Reviewer Sweep v2"
        assert update_response.json()["description"] is None
        assert update_response.json()["promptText"] == "Highlight avoidable detours."

    def test_patch_returns_404_for_unknown_prompt(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_prompt_db(db_path)

        with evaluation_prompt_client(db_path) as (client, _store):
            response = client.patch(
                "/evaluation-prompts/missing-prompt",
                json={
                    "name": "Missing prompt",
                    "description": None,
                    "promptText": "Still valid.",
                },
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Prompt 'missing-prompt' not found."

    def test_prompt_requests_reject_snake_case_payload_keys(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_prompt_db(db_path)

        with evaluation_prompt_client(db_path) as (client, _store):
            response = client.post(
                "/evaluation-prompts",
                json={
                    "name": "Failure-focused review",
                    "description": "Inspect failed tool calls.",
                    "prompt_text": "Review every failed tool call and propose better recovery steps.",
                },
            )

        assert response.status_code == 422
        assert any(error["loc"][-1] == "prompt_text" for error in response.json()["detail"])

    def test_delete_removes_user_prompt_and_rejects_default_prompt(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_prompt_db(db_path)

        with evaluation_prompt_client(db_path) as (client, store):
            delete_response = client.delete("/evaluation-prompts/prompt-1")
            missing_prompt = store.get_evaluation_prompt("prompt-1")
            default_delete_response = client.delete("/evaluation-prompts/default-conversation-review")

        assert delete_response.status_code == 204
        assert missing_prompt is None
        assert default_delete_response.status_code == 400
        assert default_delete_response.json()["detail"] == "The default prompt cannot be deleted."

    def test_openapi_exposes_prompt_request_and_response_models(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"

        with evaluation_prompt_client(db_path) as (client, _store):
            response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        prompt_get = schema["paths"]["/evaluation-prompts"]["get"]
        prompt_post = schema["paths"]["/evaluation-prompts"]["post"]
        prompt_patch = schema["paths"]["/evaluation-prompts/{prompt_id}"]["patch"]

        assert prompt_get["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith(
            "/EvaluationPromptResponse"
        )
        assert prompt_post["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/EvaluationPromptCreateRequest"
        )
        assert prompt_post["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/EvaluationPromptResponse"
        )
        assert prompt_patch["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/EvaluationPromptUpdateRequest"
        )

        create_schema = schema["components"]["schemas"]["EvaluationPromptCreateRequest"]
        response_schema = schema["components"]["schemas"]["EvaluationPromptResponse"]
        assert "promptText" in create_schema["properties"]
        assert "prompt_text" not in create_schema["properties"]
        assert "promptId" in response_schema["properties"]
        assert "prompt_id" not in response_schema["properties"]


class TestEvaluationPromptResolution:
    def test_resolve_defaults_when_prompt_id_is_missing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_prompt_db(db_path)
        store = SqliteAppStore(db_path=db_path)

        resolved = resolve_evaluation_prompt(_services_stub(app_sqlite_store=store))

        assert resolved.prompt_id == "default-conversation-review"
        assert resolved.is_default is True

    def test_resolve_returns_named_prompt_when_prompt_id_is_supplied(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_prompt_db(db_path)
        store = SqliteAppStore(db_path=db_path)

        resolved = resolve_evaluation_prompt(
            _services_stub(app_sqlite_store=store),
            prompt_id="prompt-1",
        )

        assert resolved.prompt_id == "prompt-1"
        assert resolved.name == "Failure-focused review"
