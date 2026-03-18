"""Endpoint tests for conversation evaluation jobs."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterator

from fastapi.testclient import TestClient

from helaicopter_api.adapters.app_sqlite import SqliteAppStore
from helaicopter_api.server.config import Settings
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app


def _create_evaluation_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE conversations (
              conversation_id TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              session_id TEXT NOT NULL,
              project_path TEXT NOT NULL,
              project_name TEXT NOT NULL,
              thread_type TEXT NOT NULL,
              first_message TEXT NOT NULL,
              started_at TEXT NOT NULL,
              ended_at TEXT NOT NULL,
              message_count INTEGER NOT NULL,
              model TEXT,
              git_branch TEXT,
              reasoning_effort TEXT,
              speed TEXT,
              total_input_tokens INTEGER NOT NULL,
              total_output_tokens INTEGER NOT NULL,
              total_cache_write_tokens INTEGER NOT NULL,
              total_cache_read_tokens INTEGER NOT NULL,
              total_reasoning_tokens INTEGER NOT NULL,
              tool_use_count INTEGER NOT NULL,
              subagent_count INTEGER NOT NULL,
              task_count INTEGER NOT NULL
            );

            CREATE TABLE conversation_messages (
              message_id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              ordinal INTEGER NOT NULL,
              role TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              model TEXT,
              reasoning_tokens INTEGER NOT NULL,
              speed TEXT,
              input_tokens INTEGER NOT NULL,
              output_tokens INTEGER NOT NULL,
              cache_write_tokens INTEGER NOT NULL,
              cache_read_tokens INTEGER NOT NULL,
              text_preview TEXT NOT NULL
            );

            CREATE TABLE message_blocks (
              block_id TEXT PRIMARY KEY,
              message_id TEXT NOT NULL,
              block_index INTEGER NOT NULL,
              block_type TEXT NOT NULL,
              text_content TEXT,
              tool_use_id TEXT,
              tool_name TEXT,
              tool_input_json TEXT,
              tool_result_text TEXT,
              is_error INTEGER NOT NULL
            );

            CREATE TABLE evaluation_prompts (
              prompt_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              description TEXT,
              prompt_text TEXT NOT NULL,
              is_default INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE conversation_evaluations (
              evaluation_id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              prompt_id TEXT,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              status TEXT NOT NULL,
              scope TEXT NOT NULL,
              selection_instruction TEXT,
              prompt_name TEXT NOT NULL,
              prompt_text TEXT NOT NULL,
              report_markdown TEXT,
              raw_output TEXT,
              error_message TEXT,
              command TEXT NOT NULL,
              created_at TEXT NOT NULL,
              finished_at TEXT,
              duration_ms INTEGER
            );
            """
        )
        connection.execute(
            """
            INSERT INTO conversations (
              conversation_id,
              provider,
              session_id,
              project_path,
              project_name,
              thread_type,
              first_message,
              started_at,
              ended_at,
              message_count,
              model,
              git_branch,
              reasoning_effort,
              speed,
              total_input_tokens,
              total_output_tokens,
              total_cache_write_tokens,
              total_cache_read_tokens,
              total_reasoning_tokens,
              tool_use_count,
              subagent_count,
              task_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "claude:session-1",
                "claude",
                "session-1",
                "-Users-tony-Code-helaicopter",
                "Code/helaicopter",
                "main",
                "Review the rollout",
                "2026-03-18T09:00:00+00:00",
                "2026-03-18T09:05:00+00:00",
                2,
                "claude-sonnet-4-5",
                "main",
                None,
                "standard",
                25,
                10,
                0,
                0,
                0,
                1,
                0,
                0,
            ),
        )
        connection.executemany(
            """
            INSERT INTO conversation_messages (
              message_id,
              conversation_id,
              ordinal,
              role,
              timestamp,
              model,
              reasoning_tokens,
              speed,
              input_tokens,
              output_tokens,
              cache_write_tokens,
              cache_read_tokens,
              text_preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "message-1",
                    "claude:session-1",
                    0,
                    "user",
                    "2026-03-18T09:00:00+00:00",
                    None,
                    0,
                    None,
                    0,
                    0,
                    0,
                    0,
                    "Review the rollout",
                ),
                (
                    "message-2",
                    "claude:session-1",
                    1,
                    "assistant",
                    "2026-03-18T09:00:30+00:00",
                    "claude-sonnet-4-5",
                    0,
                    "standard",
                    25,
                    10,
                    0,
                    0,
                    "Running the checks",
                ),
            ],
        )
        connection.executemany(
            """
            INSERT INTO message_blocks (
              block_id,
              message_id,
              block_index,
              block_type,
              text_content,
              tool_use_id,
              tool_name,
              tool_input_json,
              tool_result_text,
              is_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "block-1",
                    "message-1",
                    0,
                    "text",
                    "Review the rollout",
                    None,
                    None,
                    None,
                    None,
                    0,
                ),
                (
                    "block-2",
                    "message-2",
                    0,
                    "tool_call",
                    None,
                    "tool-1",
                    "exec_command",
                    '{"cmd": "pytest -q"}',
                    "Process exited with code 1",
                    1,
                ),
            ],
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
                "Failure Sweep",
                "Focus on failed tool calls.",
                "Summarize what failed and how the operator prompt should change.",
                0,
                "2026-03-17T10:00:00+00:00",
                "2026-03-17T10:00:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO conversation_evaluations (
              evaluation_id,
              conversation_id,
              prompt_id,
              provider,
              model,
              status,
              scope,
              selection_instruction,
              prompt_name,
              prompt_text,
              report_markdown,
              raw_output,
              error_message,
              command,
              created_at,
              finished_at,
              duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "evaluation-existing",
                "claude:session-1",
                "prompt-1",
                "codex",
                "gpt-5",
                "completed",
                "full",
                None,
                "Failure Sweep",
                "Summarize what failed and how the operator prompt should change.",
                "# Existing report",
                "# Existing report",
                None,
                "codex exec --dangerously-bypass-approvals-and-sandbox -m gpt-5 -",
                "2026-03-17T12:00:00+00:00",
                "2026-03-17T12:00:03+00:00",
                3000,
            ),
        )
        connection.commit()
    finally:
        connection.close()


class FakeEvaluationRunner:
    def __init__(self) -> None:
        self.submissions: list[dict[str, Any]] = []

    def describe_command(self, request: Any) -> str:
        return f"{request.provider} exec --model {request.model}"

    def submit(
        self,
        request: Any,
        on_complete: Callable[[Any], None],
    ) -> None:
        self.submissions.append(
            {
                "evaluation_id": request.evaluation_id,
                "provider": request.provider,
                "model": request.model,
                "workspace": str(request.workspace),
                "prompt": request.prompt,
            }
        )
        on_complete(
            SimpleNamespace(
                evaluation_id=request.evaluation_id,
                status="completed",
                report_markdown="# Automated evaluation",
                raw_output="# Automated evaluation",
                error_message=None,
                command=self.describe_command(request),
                finished_at="2026-03-18T09:06:00+00:00",
                duration_ms=750,
            )
        )


@contextmanager
def evaluation_client(db_path: Path) -> Iterator[tuple[TestClient, SqliteAppStore, FakeEvaluationRunner]]:
    store = SqliteAppStore(db_path=db_path)
    runner = FakeEvaluationRunner()
    application = create_app()
    application.dependency_overrides[get_services] = lambda: SimpleNamespace(
        app_sqlite_store=store,
        evaluation_job_runner=runner,
        settings=Settings(project_root=db_path.parents[3]),
    )
    try:
        with TestClient(application) as client:
            yield client, store, runner
    finally:
        application.dependency_overrides.clear()


class TestConversationEvaluationEndpoints:
    def test_get_lists_existing_evaluations_for_one_conversation(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_evaluation_db(db_path)

        with evaluation_client(db_path) as (client, _store, _runner):
            response = client.get("/conversations/-Users-tony-Code-helaicopter/session-1/evaluations")

        assert response.status_code == 200
        assert response.json() == [
            {
                "evaluationId": "evaluation-existing",
                "conversationId": "claude:session-1",
                "promptId": "prompt-1",
                "provider": "codex",
                "model": "gpt-5",
                "status": "completed",
                "scope": "full",
                "selectionInstruction": None,
                "promptName": "Failure Sweep",
                "promptText": "Summarize what failed and how the operator prompt should change.",
                "reportMarkdown": "# Existing report",
                "rawOutput": "# Existing report",
                "errorMessage": None,
                "command": "codex exec --dangerously-bypass-approvals-and-sandbox -m gpt-5 -",
                "createdAt": "2026-03-17T12:00:00+00:00",
                "finishedAt": "2026-03-17T12:00:03+00:00",
                "durationMs": 3000,
            }
        ]

    def test_post_creates_running_job_and_runner_completion_is_persisted(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_evaluation_db(db_path)

        with evaluation_client(db_path) as (client, store, runner):
            create_response = client.post(
                "/conversations/-Users-tony-Code-helaicopter/session-1/evaluations",
                json={
                    "provider": "codex",
                    "model": "gpt-5",
                    "scope": "failed_tool_calls",
                    "promptId": "prompt-1",
                    "selectionInstruction": "Focus on the failing exec_command step only.",
                },
            )
            list_response = client.get("/conversations/-Users-tony-Code-helaicopter/session-1/evaluations")

        assert create_response.status_code == 202
        created = create_response.json()
        assert created["status"] == "running"
        assert created["scope"] == "failed_tool_calls"
        assert created["promptId"] == "prompt-1"
        assert created["promptName"] == "Failure Sweep"
        assert created["selectionInstruction"] == "Focus on the failing exec_command step only."
        assert created["command"] == "codex exec --model gpt-5"

        assert len(runner.submissions) == 1
        assert runner.submissions[0]["evaluation_id"] == created["evaluationId"]
        assert runner.submissions[0]["workspace"] == str(Path.cwd())
        assert "failed tool calls and their nearby context" in runner.submissions[0]["prompt"]
        assert "Focus on the failing exec_command step only." not in runner.submissions[0]["prompt"]

        stored = store.list_conversation_evaluations("claude:session-1")
        completed = next(item for item in stored if item.evaluation_id == created["evaluationId"])
        assert completed.status == "completed"
        assert completed.report_markdown == "# Automated evaluation"
        assert completed.duration_ms == 750

        listed = list_response.json()
        assert listed[0]["evaluationId"] == created["evaluationId"]
        assert listed[0]["status"] == "completed"
        assert listed[0]["reportMarkdown"] == "# Automated evaluation"
        assert listed[1]["evaluationId"] == "evaluation-existing"

    def test_openapi_exposes_conversation_evaluation_models(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_evaluation_db(db_path)

        with evaluation_client(db_path) as (client, _store, _runner):
            response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        route = schema["paths"]["/conversations/{project_path}/{session_id}/evaluations"]

        assert route["get"]["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith(
            "/ConversationEvaluationResponse"
        )
        assert route["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ConversationEvaluationCreateRequest"
        )
        assert route["post"]["responses"]["202"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ConversationEvaluationResponse"
        )
