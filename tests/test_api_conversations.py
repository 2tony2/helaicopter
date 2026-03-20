"""Endpoint tests for conversations, projects, history, and tasks APIs."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from helaicopter_api.application import conversations as conversations_application
from helaicopter_api.application.conversations import _compact_dict, _shape_conversation_task
from helaicopter_api.bootstrap.services import build_services
from helaicopter_api.ports.app_sqlite import HistoricalConversationTask
from helaicopter_api.server.config import Settings
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db.utils import (
    conversation_context_bucket_id,
    conversation_context_step_id,
    conversation_id,
    conversation_message_block_id,
    conversation_message_id,
    conversation_plan_row_id,
    conversation_subagent_row_id,
    conversation_task_row_id,
)


def _codex_thread_row(
    *,
    session_id: str,
    title: str,
    first_user_message: str,
    source: str = "cli",
    agent_role: str | None = None,
    agent_nickname: str | None = None,
    created_at: int = 1_763_200_000,
    updated_at: int = 1_763_200_123,
) -> tuple[object, ...]:
    return (
        session_id,
        title,
        "/Users/tony/Code/helaicopter",
        source,
        "openai",
        0,
        None,
        "main",
        None,
        "0.1.0",
        first_user_message,
        created_at,
        updated_at,
        None,
        agent_role,
        agent_nickname,
    )


def _write_codex_thread_db(path: Path, rows: list[tuple[object, ...]]) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE threads (
              id TEXT PRIMARY KEY,
              title TEXT,
              cwd TEXT,
              source TEXT,
              model_provider TEXT,
              tokens_used INTEGER,
              git_sha TEXT,
              git_branch TEXT,
              git_origin_url TEXT,
              cli_version TEXT,
              first_user_message TEXT,
              created_at INTEGER,
              updated_at INTEGER,
              rollout_path TEXT,
              agent_role TEXT,
              agent_nickname TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO threads (
              id,
              title,
              cwd,
              source,
              model_provider,
              tokens_used,
              git_sha,
              git_branch,
              git_origin_url,
              cli_version,
              first_user_message,
              created_at,
              updated_at,
              rollout_path,
              agent_role,
              agent_nickname
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
    finally:
        connection.close()


def _write_app_db(path: Path) -> None:
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
              thread_type TEXT,
              first_message TEXT NOT NULL,
              route_slug TEXT NOT NULL,
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

            CREATE TABLE conversation_tasks (
              task_row_id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              ordinal INTEGER NOT NULL,
              task_json TEXT NOT NULL
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
              route_slug,
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "claude:historic-session",
                "claude",
                "historic-session",
                "-Users-tony-Code-helaicopter",
                "Code/helaicopter",
                "main",
                "Historic task run",
                "historic-canonical-ref",
                "2026-03-15T10:00:00Z",
                "2026-03-15T10:30:00Z",
                2,
                "claude-sonnet-4-5",
                "main",
                None,
                "standard",
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                1,
            ),
        )
        connection.execute(
            """
            INSERT INTO conversation_tasks (
              task_row_id,
              conversation_id,
              ordinal,
              task_json
            ) VALUES (?, ?, ?, ?)
            """,
            (
                "task-row-1",
                "claude:historic-session",
                0,
                json.dumps({"taskId": "T009", "title": "Historic persisted task"}),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _insert_persisted_conversation_summary(
    path: Path,
    *,
    provider: str,
    session_id: str,
    project_path: str,
    project_name: str,
    thread_type: str,
    first_message: str,
    route_slug: str,
    started_at: str,
    ended_at: str,
    message_count: int = 0,
    model: str | None = None,
    git_branch: str | None = None,
    reasoning_effort: str | None = None,
    speed: str | None = None,
    total_input_tokens: int = 0,
    total_output_tokens: int = 0,
    total_cache_write_tokens: int = 0,
    total_cache_read_tokens: int = 0,
    total_reasoning_tokens: int = 0,
    tool_use_count: int = 0,
    subagent_count: int = 0,
    task_count: int = 0,
) -> None:
    connection = sqlite3.connect(path)
    try:
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
              route_slug,
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{provider}:{session_id}",
                provider,
                session_id,
                project_path,
                project_name,
                thread_type,
                first_message,
                route_slug,
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
                task_count,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _seed_sources(tmp_path: Path) -> Settings:
    claude_dir = tmp_path / ".claude"
    codex_dir = tmp_path / ".codex"
    project_path = "-Users-tony-Code-helaicopter"
    claude_project_dir = claude_dir / "projects" / project_path
    claude_project_dir.mkdir(parents=True)
    claude_dir.joinpath("tasks", "claude-session-1").mkdir(parents=True)
    claude_dir.joinpath("tasks", "claude-session-1", "claude-agent-1").mkdir(parents=True)
    codex_dir.joinpath("sessions", "2026", "03", "18").mkdir(parents=True)
    claude_subagents_dir = claude_project_dir / "claude-session-1" / "subagents"
    claude_subagents_dir.mkdir(parents=True)

    claude_session = claude_project_dir / "claude-session-1.jsonl"
    claude_session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "uuid": "claude-user-1",
                        "timestamp": "2026-03-18T09:00:00Z",
                        "sessionId": "claude-session-1",
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Review the backend rollout"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "claude-assistant-1",
                        "timestamp": "2026-03-18T09:00:10Z",
                        "sessionId": "claude-session-1",
                        "gitBranch": "main",
                        "slug": "conversation-api-rollout",
                        "planContent": "# Conversation API rollout\n\nShip summaries.\nVerify details.\n",
                        "message": {
                            "role": "assistant",
                            "model": "claude-sonnet-4-5",
                            "usage": {
                                "input_tokens": 120,
                                "output_tokens": 45,
                                "cache_creation_input_tokens": 12,
                                "cache_read_input_tokens": 6,
                                "speed": "standard",
                            },
                            "content": [
                                {"type": "thinking", "thinking": "Need to inspect the backend."},
                                {"type": "text", "text": "I will wire the read endpoints."},
                                {
                                    "type": "tool_use",
                                    "id": "tool-1",
                                    "name": "Bash",
                                    "input": {"cmd": "rg -n API python"},
                                },
                                {
                                    "type": "tool_use",
                                    "id": "tool-task-1",
                                    "name": "Task",
                                    "input": {
                                        "description": "Inspect the DAG graph",
                                        "subagent_type": "explorer",
                                    },
                                },
                            ],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "user",
                        "uuid": "claude-user-2",
                        "timestamp": "2026-03-18T09:00:15Z",
                        "sessionId": "claude-session-1",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "tool-1",
                                    "content": "python/helaicopter_api/router/router.py",
                                }
                            ],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "user",
                        "uuid": "claude-user-3",
                        "timestamp": "2026-03-18T09:00:20Z",
                        "sessionId": "claude-session-1",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "tool-task-1",
                                    "content": json.dumps(
                                        {
                                            "agentId": "claude-agent-1",
                                            "nickname": "Scout",
                                        }
                                    ),
                                }
                            ],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    os.utime(claude_session, (1_763_287_215, 1_763_287_215))
    claude_subagents_dir.joinpath("agent-claude-agent-1.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "uuid": "claude-sub-user-1",
                        "timestamp": "2026-03-18T09:00:16Z",
                        "sessionId": "claude-agent-1",
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Inspect the DAG graph"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "claude-sub-assistant-1",
                        "timestamp": "2026-03-18T09:00:18Z",
                        "sessionId": "claude-agent-1",
                        "message": {
                            "role": "assistant",
                            "model": "claude-sonnet-4-5",
                            "usage": {
                                "input_tokens": 40,
                                "output_tokens": 20,
                                "cache_creation_input_tokens": 0,
                                "cache_read_input_tokens": 0,
                                "speed": "standard",
                            },
                            "content": [{"type": "text", "text": "I found the child conversation."}],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    claude_dir.joinpath("tasks", "claude-session-1", "task-1.json").write_text(
        json.dumps({"taskId": "T007", "title": "Conversation API"}),
        encoding="utf-8",
    )
    claude_dir.joinpath("tasks", "claude-session-1", "claude-agent-1", "task-1.json").write_text(
        json.dumps({"taskId": "T008", "title": "Inspect DAG child thread"}),
        encoding="utf-8",
    )
    claude_dir.joinpath("history.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"display": "claude history", "timestamp": 1_763_287_000_000}),
            ]
        ),
        encoding="utf-8",
    )

    codex_session_id = "019cdbff-dbb7-71d0-baaf-c669c55af628"
    codex_subagent_session_id = "019cdbff-dbb7-71d0-baaf-c669c55af629"
    codex_session = (
        codex_dir
        / "sessions"
        / "2026"
        / "03"
        / "18"
        / f"rollout-2026-03-18T10-00-00-{codex_session_id}.jsonl"
    )
    codex_session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:00Z",
                        "type": "session_meta",
                        "payload": {
                            "id": codex_session_id,
                            "cwd": "/Users/tony/Code/helaicopter",
                            "source": "cli",
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:01Z",
                        "type": "turn_context",
                        "payload": {"model": "gpt-5", "reasoning_effort": "medium"},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:02Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "Implement the conversation API"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:03Z",
                        "type": "response_item",
                        "payload": {
                            "type": "reasoning",
                            "summary": [{"type": "summary_text", "text": "Need router and app wiring."}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:04Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "I will wire the FastAPI read surface."}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:05Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "exec_command",
                            "call_id": "call-shell-1",
                            "arguments": json.dumps({"cmd": "rg -n APIRouter python/helaicopter_api"}),
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:06Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "call_id": "call-shell-1",
                            "output": "Process exited with code 0\npython/helaicopter_api/router/router.py:1",
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:07Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "update_plan",
                            "call_id": "call-plan-1",
                            "arguments": json.dumps(
                                {
                                    "explanation": "Codex rollout plan",
                                    "plan": [
                                        {"step": "Wire routers", "status": "in_progress"},
                                        {"step": "Add tests", "status": "pending"},
                                    ],
                                }
                            ),
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:08Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "spawn_agent",
                            "call_id": "call-agent-1",
                            "arguments": json.dumps(
                                {
                                    "message": "Inspect the DAG graph",
                                    "agent_type": "explorer",
                                }
                            ),
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:08Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "call_id": "call-agent-1",
                            "output": json.dumps(
                                {
                                    "agent_id": codex_subagent_session_id,
                                    "nickname": "Scout",
                                }
                            ),
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:09Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 240,
                                    "cached_input_tokens": 16,
                                    "output_tokens": 80,
                                    "reasoning_output_tokens": 22,
                                }
                            },
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    os.utime(codex_session, (1_763_290_808, 1_763_290_808))
    codex_subagent_session = (
        codex_dir
        / "sessions"
        / "2026"
        / "03"
        / "18"
        / f"rollout-2026-03-18T09-59-59-{codex_subagent_session_id}.jsonl"
    )
    codex_subagent_session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-18T09:59:59Z",
                        "type": "session_meta",
                        "payload": {
                            "id": codex_subagent_session_id,
                            "cwd": "/Users/tony/Code/helaicopter",
                            "source": json.dumps(
                                {
                                    "subagent": {
                                        "thread_spawn": {
                                            "parent_thread_id": codex_session_id,
                                        }
                                    }
                                }
                            ),
                            "agent_role": "explorer",
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:00Z",
                        "type": "turn_context",
                        "payload": {"model": "gpt-5", "reasoning_effort": "low"},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:01Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "Inspect the DAG graph"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:02Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "I found the child conversation."}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-18T10:00:03Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 50,
                                    "cached_input_tokens": 0,
                                    "output_tokens": 20,
                                    "reasoning_output_tokens": 0,
                                }
                            },
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    os.utime(codex_subagent_session, (1_763_290_803, 1_763_290_803))

    codex_dir.joinpath("history.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"session_id": codex_session_id, "ts": 1_763_290_900, "text": "codex history"}),
            ]
        ),
        encoding="utf-8",
    )
    _write_codex_thread_db(
        codex_dir / "state_5.sqlite",
        [
            _codex_thread_row(
                session_id=codex_session_id,
                title="Codex rollout",
                first_user_message="Implement the conversation API",
            ),
            _codex_thread_row(
                session_id=codex_subagent_session_id,
                title="Codex rollout subagent",
                first_user_message="Inspect the DAG graph",
                source=json.dumps(
                    {
                        "subagent": {
                            "thread_spawn": {
                                "parent_thread_id": codex_session_id,
                            }
                        }
                    }
                ),
                agent_role="explorer",
                agent_nickname="Scout",
                created_at=1_763_199_999,
                updated_at=1_763_200_003,
            ),
        ],
    )
    _write_app_db(tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite")

    return Settings(project_root=tmp_path, claude_dir=claude_dir, codex_dir=codex_dir)


@pytest.fixture()
def conversations_client(tmp_path: Path):
    settings = _seed_sources(tmp_path)
    services = build_services(settings)
    application = create_app()
    application.dependency_overrides[get_services] = lambda: services

    with TestClient(application) as client:
        yield client

    application.dependency_overrides.clear()
    services.sqlite_engine.dispose()


def test_compact_dict_keeps_non_empty_lists_without_raising() -> None:
    assert _compact_dict(
        {
            "type": "search",
            "query": None,
            "queries": ["alpha", "beta"],
            "empty_queries": [],
            "blank": "",
        }
    ) == {
        "type": "search",
        "queries": ["alpha", "beta"],
    }


class TestConversationEndpoints:
    def test_shape_conversation_task_uses_trusted_fast_path_for_validated_store_tasks(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        task = HistoricalConversationTask.model_validate(
            {
                "taskId": "T200",
                "title": "Hot path",
                "status": "running",
            }
        )

        monkeypatch.setattr(
            HistoricalConversationTask,
            "model_dump",
            lambda self, *args, **kwargs: pytest.fail("validated tasks should not be dumped before shaping"),
        )

        response = _shape_conversation_task(task)

        assert response.model_dump(by_alias=True) == {
            "taskId": "T200",
            "title": "Hot path",
            "status": "running",
        }

    def test_list_and_detail_cover_claude_and_codex(self, conversations_client: TestClient) -> None:
        response = conversations_client.get("/conversations")

        assert response.status_code == 200
        payload = response.json()
        by_session = {item["session_id"]: item for item in payload}

        codex_summary = by_session["019cdbff-dbb7-71d0-baaf-c669c55af628"]
        assert codex_summary["model"] == "gpt-5"
        assert codex_summary["reasoning_effort"] == "medium"
        assert codex_summary["total_reasoning_tokens"] == 22
        assert codex_summary["subagent_count"] == 1
        assert codex_summary["route_slug"] == "implement-the-conversation-api"
        assert (
            codex_summary["conversation_ref"]
            == "implement-the-conversation-api--codex-019cdbff-dbb7-71d0-baaf-c669c55af628"
        )

        claude_live_summary = by_session["claude-session-1"]
        assert claude_live_summary["tool_breakdown"] == {"Bash": 1, "Task": 1}
        assert claude_live_summary["task_count"] == 1
        assert claude_live_summary["subagent_count"] == 1
        assert claude_live_summary["route_slug"] == "review-the-backend-rollout"
        assert (
            claude_live_summary["conversation_ref"]
            == "review-the-backend-rollout--claude-claude-session-1"
        )

        codex_subagent_summary = by_session["019cdbff-dbb7-71d0-baaf-c669c55af629"]
        assert codex_subagent_summary["thread_type"] == "subagent"
        assert codex_subagent_summary["route_slug"] == "inspect-the-dag-graph"
        assert (
            codex_subagent_summary["conversation_ref"]
            == "inspect-the-dag-graph--codex-019cdbff-dbb7-71d0-baaf-c669c55af629"
        )

        persisted_summary = by_session["historic-session"]
        assert persisted_summary["route_slug"] == "historic-canonical-ref"
        assert persisted_summary["conversation_ref"] == "historic-canonical-ref--claude-historic-session"

        claude_detail = conversations_client.get("/conversations/-Users-tony-Code-helaicopter/claude-session-1")
        assert claude_detail.status_code == 200
        claude_payload = claude_detail.json()
        assert claude_payload["route_slug"] == "review-the-backend-rollout"
        assert claude_payload["conversation_ref"] == "review-the-backend-rollout--claude-claude-session-1"
        assert claude_payload["plans"][0]["provider"] == "claude"
        assert claude_payload["plans"][0]["route_slug"] == "review-the-backend-rollout"
        assert (
            claude_payload["plans"][0]["conversation_ref"]
            == "review-the-backend-rollout--claude-claude-session-1"
        )
        assert claude_payload["messages"][1]["blocks"][2]["tool_name"] == "Bash"
        assert claude_payload["messages"][1]["blocks"][2]["result"] == "python/helaicopter_api/router/router.py"
        assert claude_payload["subagents"] == [
            {
                "agent_id": "claude-agent-1",
                "description": "Inspect the DAG graph",
                "subagent_type": "explorer",
                "nickname": "Scout",
                "has_file": True,
                "project_path": "-Users-tony-Code-helaicopter",
                "session_id": "claude-session-1",
                "route_slug": "inspect-the-dag-graph",
                "conversation_ref": "inspect-the-dag-graph--claude-claude-agent-1",
            }
        ]
        assert claude_payload["total_usage"] == {
            "input_tokens": 120,
            "output_tokens": 45,
            "cache_creation_tokens": 12,
            "cache_read_tokens": 6,
        }

        codex_detail = conversations_client.get(
            "/conversations/codex:-Users-tony-Code-helaicopter/019cdbff-dbb7-71d0-baaf-c669c55af628"
        )
        assert codex_detail.status_code == 200
        codex_payload = codex_detail.json()
        assert codex_payload["route_slug"] == "implement-the-conversation-api"
        assert (
            codex_payload["conversation_ref"]
            == "implement-the-conversation-api--codex-019cdbff-dbb7-71d0-baaf-c669c55af628"
        )
        assert codex_payload["reasoning_effort"] == "medium"
        assert codex_payload["total_reasoning_tokens"] == 22
        assert codex_payload["plans"][0]["provider"] == "codex"
        assert codex_payload["plans"][0]["route_slug"] == "implement-the-conversation-api"
        assert (
            codex_payload["plans"][0]["conversation_ref"]
            == "implement-the-conversation-api--codex-019cdbff-dbb7-71d0-baaf-c669c55af628"
        )
        assert codex_payload["plans"][0]["steps"] == [
            {"step": "Wire routers", "status": "in_progress"},
            {"step": "Add tests", "status": "pending"},
        ]
        assert codex_payload["messages"][1]["blocks"][2]["tool_name"] == "Shell"
        assert codex_payload["messages"][1]["blocks"][2]["result"].startswith("Process exited with code 0")
        assert codex_payload["subagents"] == [
            {
                "agent_id": "019cdbff-dbb7-71d0-baaf-c669c55af629",
                "description": "Inspect the DAG graph",
                "subagent_type": "explorer",
                "nickname": "Scout",
                "has_file": True,
                "project_path": "codex:-Users-tony-Code-helaicopter",
                "session_id": "019cdbff-dbb7-71d0-baaf-c669c55af628",
                "route_slug": "inspect-the-dag-graph",
                "conversation_ref": "inspect-the-dag-graph--codex-019cdbff-dbb7-71d0-baaf-c669c55af629",
            }
        ]

        persisted_detail = conversations_client.get("/conversations/-Users-tony-Code-helaicopter/historic-session")
        assert persisted_detail.status_code == 200
        assert persisted_detail.json()["route_slug"] == "historic-canonical-ref"
        assert persisted_detail.json()["conversation_ref"] == "historic-canonical-ref--claude-historic-session"

        filtered = conversations_client.get(
            "/conversations",
            params={"project": "codex:-Users-tony-Code-helaicopter"},
        )
        assert filtered.status_code == 200
        assert {item["session_id"] for item in filtered.json()} == {
            "019cdbff-dbb7-71d0-baaf-c669c55af628",
            "019cdbff-dbb7-71d0-baaf-c669c55af629",
        }

    def test_subagent_detail_route_covers_claude_and_codex(self, conversations_client: TestClient) -> None:
        claude_subagent = conversations_client.get(
            "/subagents/-Users-tony-Code-helaicopter/claude-session-1/claude-agent-1"
        )
        claude_nested = conversations_client.get(
            "/conversations/-Users-tony-Code-helaicopter/claude-session-1/subagents/claude-agent-1"
        )

        assert claude_subagent.status_code == 200
        assert claude_nested.status_code == 200
        claude_payload = claude_subagent.json()
        assert claude_payload["session_id"] == "claude-agent-1"
        assert claude_payload["thread_type"] == "subagent"
        assert claude_nested.json()["session_id"] == "claude-agent-1"

        codex_subagent = conversations_client.get(
            "/subagents/codex:-Users-tony-Code-helaicopter/019cdbff-dbb7-71d0-baaf-c669c55af628/019cdbff-dbb7-71d0-baaf-c669c55af629"
        )
        codex_nested = conversations_client.get(
            "/conversations/codex:-Users-tony-Code-helaicopter/019cdbff-dbb7-71d0-baaf-c669c55af628/subagents/019cdbff-dbb7-71d0-baaf-c669c55af629"
        )

        assert codex_subagent.status_code == 200
        assert codex_nested.status_code == 200
        codex_payload = codex_subagent.json()
        assert codex_payload["session_id"] == "019cdbff-dbb7-71d0-baaf-c669c55af629"
        assert codex_payload["thread_type"] == "subagent"
        assert codex_nested.json()["session_id"] == "019cdbff-dbb7-71d0-baaf-c669c55af629"

    def test_canonical_live_claude_child_detail_requires_parent_session_id(
        self,
        conversations_client: TestClient,
    ) -> None:
        missing = conversations_client.get("/conversations/-Users-tony-Code-helaicopter/claude-agent-1")
        response = conversations_client.get(
            "/conversations/-Users-tony-Code-helaicopter/claude-agent-1",
            params={"parent_session_id": "claude-session-1"},
        )

        assert missing.status_code == 404
        assert response.status_code == 200
        assert response.json()["session_id"] == "claude-agent-1"
        assert response.json()["thread_type"] == "subagent"
        assert response.json()["route_slug"] == "inspect-the-dag-graph"

    def test_missing_conversation_returns_404(self, conversations_client: TestClient) -> None:
        response = conversations_client.get("/conversations/-Users-tony-Code-helaicopter/missing-session")

        assert response.status_code == 404
        assert response.json() == {"detail": "Conversation not found"}

    def test_list_preserves_persisted_canonical_identity_when_live_summary_is_fresher(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        _insert_persisted_conversation_summary(
            tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite",
            provider="claude",
            session_id="claude-session-1",
            project_path="-Users-tony-Code-helaicopter",
            project_name="Code/helaicopter",
            thread_type="main",
            first_message="Persisted canonical title",
            route_slug="persisted-canonical-claude-session-1",
            started_at="2026-03-16T09:00:00Z",
            ended_at="2026-03-16T09:30:00Z",
            message_count=1,
            model="claude-sonnet-4-5",
            git_branch="main",
            speed="standard",
        )
        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                response = client.get("/conversations")
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert response.status_code == 200
        payload = {item["session_id"]: item for item in response.json()}
        summary = payload["claude-session-1"]
        assert summary["route_slug"] == "persisted-canonical-claude-session-1"
        assert (
            summary["conversation_ref"]
            == "persisted-canonical-claude-session-1--claude-claude-session-1"
        )
        assert summary["tool_breakdown"] == {"Bash": 1, "Task": 1}

    def test_conversation_by_ref_resolves_persisted_and_live_routes(self, conversations_client: TestClient) -> None:
        persisted = conversations_client.get("/conversations/by-ref/stale-slug--claude-historic-session")
        assert persisted.status_code == 200
        assert persisted.json() == {
            "conversation_ref": "historic-canonical-ref--claude-historic-session",
            "route_slug": "historic-canonical-ref",
            "project_path": "-Users-tony-Code-helaicopter",
            "session_id": "historic-session",
            "thread_type": "main",
            "parent_session_id": None,
        }

        codex_live = conversations_client.get(
            "/conversations/by-ref/old-title--codex-019cdbff-dbb7-71d0-baaf-c669c55af628"
        )
        assert codex_live.status_code == 200
        assert codex_live.json() == {
            "conversation_ref": "implement-the-conversation-api--codex-019cdbff-dbb7-71d0-baaf-c669c55af628",
            "route_slug": "implement-the-conversation-api",
            "project_path": "codex:-Users-tony-Code-helaicopter",
            "session_id": "019cdbff-dbb7-71d0-baaf-c669c55af628",
            "thread_type": "main",
            "parent_session_id": None,
        }

        claude_subagent = conversations_client.get("/conversations/by-ref/outdated--claude-claude-agent-1")
        assert claude_subagent.status_code == 200
        assert claude_subagent.json() == {
            "conversation_ref": "inspect-the-dag-graph--claude-claude-agent-1",
            "route_slug": "inspect-the-dag-graph",
            "project_path": "-Users-tony-Code-helaicopter",
            "session_id": "claude-agent-1",
            "thread_type": "subagent",
            "parent_session_id": "claude-session-1",
        }

        claude_live_main = conversations_client.get("/conversations/by-ref/outdated--claude-claude-session-1")
        assert claude_live_main.status_code == 200
        assert claude_live_main.json() == {
            "conversation_ref": "review-the-backend-rollout--claude-claude-session-1",
            "route_slug": "review-the-backend-rollout",
            "project_path": "-Users-tony-Code-helaicopter",
            "session_id": "claude-session-1",
            "thread_type": "main",
            "parent_session_id": None,
        }

    def test_list_refreshes_live_conversations_after_cache_ttl_expires(self, tmp_path: Path) -> None:
        settings = _seed_sources(tmp_path)
        services = build_services(settings)
        original_ttl = conversations_application._LIVE_CONVERSATION_CACHE_TTL_SECONDS
        conversations_application._LIVE_CONVERSATION_CACHE_TTL_SECONDS = 0.01

        try:
            initial = conversations_application.list_conversations(services, days=7)
            initial_session_ids = {conversation.session_id for conversation in initial}
            assert "claude-session-2" not in initial_session_ids

            claude_project_dir = settings.claude_dir / "projects" / "-Users-tony-Code-helaicopter"
            claude_session = claude_project_dir / "claude-session-2.jsonl"
            claude_session.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "user",
                                "uuid": "claude-user-new-1",
                                "timestamp": "2026-03-20T12:00:00Z",
                                "sessionId": "claude-session-2",
                                "message": {
                                    "role": "user",
                                    "content": [{"type": "text", "text": "Fresh live session"}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant",
                                "uuid": "claude-assistant-new-1",
                                "timestamp": "2026-03-20T12:00:05Z",
                                "sessionId": "claude-session-2",
                                "message": {
                                    "role": "assistant",
                                    "model": "claude-sonnet-4-5",
                                    "usage": {
                                        "input_tokens": 10,
                                        "output_tokens": 5,
                                        "cache_creation_input_tokens": 0,
                                        "cache_read_input_tokens": 0,
                                        "speed": "standard",
                                    },
                                    "content": [{"type": "text", "text": "Now visible after TTL expiry."}],
                                },
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )
            os.utime(claude_session, None)

            cached = conversations_application.list_conversations(services, days=7)
            assert {conversation.session_id for conversation in cached} == initial_session_ids

            time.sleep(0.02)

            refreshed = conversations_application.list_conversations(services, days=7)
            assert "claude-session-2" in {conversation.session_id for conversation in refreshed}
        finally:
            conversations_application._LIVE_CONVERSATION_CACHE_TTL_SECONDS = original_ttl
            services.sqlite_engine.dispose()

    def test_conversation_by_ref_returns_404_for_unknown_well_formed_ref(
        self,
        conversations_client: TestClient,
    ) -> None:
        response = conversations_client.get("/conversations/by-ref/unknown--codex-019cdbff-dbb7-71d0-baaf-deadbeef0000")

        assert response.status_code == 404
        assert response.json() == {"detail": "Conversation not found"}


class TestConversationDagEndpoints:
    def test_list_filters_and_detail_builds_backend_owned_dag(self, conversations_client: TestClient) -> None:
        response = conversations_client.get("/conversation-dags")

        assert response.status_code == 200
        payload = response.json()
        assert {item["session_id"] for item in payload} == {
            "claude-session-1",
            "019cdbff-dbb7-71d0-baaf-c669c55af628",
        }

        claude_filtered = conversations_client.get("/conversation-dags", params={"provider": "claude"})
        assert claude_filtered.status_code == 200
        assert [item["session_id"] for item in claude_filtered.json()] == ["claude-session-1"]

        codex_filtered = conversations_client.get("/conversation-dags", params={"provider": "codex"})
        assert codex_filtered.status_code == 200
        assert [item["session_id"] for item in codex_filtered.json()] == [
            "019cdbff-dbb7-71d0-baaf-c669c55af628"
        ]

        claude_dag = conversations_client.get("/conversations/-Users-tony-Code-helaicopter/claude-session-1/dag")
        assert claude_dag.status_code == 200
        claude_payload = claude_dag.json()
        assert claude_payload["root_session_id"] == "claude-session-1"
        assert claude_payload["stats"] == {
            "total_nodes": 2,
            "total_edges": 1,
            "total_subagent_nodes": 1,
            "max_depth": 1,
            "max_breadth": 1,
            "leaf_count": 1,
            "root_subagent_count": 1,
            "total_messages": 4,
            "total_tokens": 243,
        }
        assert claude_payload["edges"] == [
            {
                "id": "claude-session-1->claude-agent-1",
                "source": "claude-session-1",
                "target": "claude-agent-1",
            }
        ]
        assert [node["label"] for node in claude_payload["nodes"]] == [
            "Review the backend rollout",
            "Inspect the DAG graph",
        ]
        assert [node["path"] for node in claude_payload["nodes"]] == [
            "/conversations/by-ref/review-the-backend-rollout--claude-claude-session-1",
            "/conversations/by-ref/inspect-the-dag-graph--claude-claude-agent-1",
        ]

        codex_dag = conversations_client.get(
            "/conversations/codex:-Users-tony-Code-helaicopter/019cdbff-dbb7-71d0-baaf-c669c55af628/dag"
        )
        assert codex_dag.status_code == 200
        codex_payload = codex_dag.json()
        assert codex_payload["stats"] == {
            "total_nodes": 2,
            "total_edges": 1,
            "total_subagent_nodes": 1,
            "max_depth": 1,
            "max_breadth": 1,
            "leaf_count": 1,
            "root_subagent_count": 1,
            "total_messages": 4,
            "total_tokens": 406,
        }
        assert codex_payload["nodes"][1]["subagent_type"] == "explorer"
        assert [node["path"] for node in codex_payload["nodes"]] == [
            "/conversations/by-ref/implement-the-conversation-api--codex-019cdbff-dbb7-71d0-baaf-c669c55af628",
            "/conversations/by-ref/inspect-the-dag-graph--codex-019cdbff-dbb7-71d0-baaf-c669c55af629",
        ]

        missing = conversations_client.get(
            "/conversations/codex:-Users-tony-Code-helaicopter/missing-session/dag"
        )
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Conversation DAG not found"}

    def test_canonical_live_claude_child_dag_requires_parent_session_id(
        self,
        conversations_client: TestClient,
    ) -> None:
        missing = conversations_client.get("/conversations/-Users-tony-Code-helaicopter/claude-agent-1/dag")
        response = conversations_client.get(
            "/conversations/-Users-tony-Code-helaicopter/claude-agent-1/dag",
            params={"parent_session_id": "claude-session-1"},
        )

        assert missing.status_code == 404
        assert response.status_code == 200
        assert response.json()["root_session_id"] == "claude-agent-1"
        assert response.json()["edges"] == []
        assert response.json()["stats"] == {
            "total_nodes": 1,
            "total_edges": 0,
            "total_subagent_nodes": 0,
            "max_depth": 0,
            "max_breadth": 1,
            "leaf_count": 1,
            "root_subagent_count": 0,
            "total_messages": 2,
            "total_tokens": 60,
        }
        assert (
            response.json()["nodes"][0]["path"]
            == "/conversations/by-ref/inspect-the-dag-graph--claude-claude-agent-1"
        )

    def test_dag_unresolved_child_threads_emit_null_paths(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        claude_session_path = (
            settings.claude_projects_dir / "-Users-tony-Code-helaicopter" / "claude-session-1.jsonl"
        )
        with claude_session_path.open("a", encoding="utf-8") as handle:
            handle.write("\n")
            handle.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "claude-assistant-missing-child",
                        "timestamp": "2026-03-18T09:00:25Z",
                        "sessionId": "claude-session-1",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "tool-task-missing",
                                    "name": "Task",
                                    "input": {
                                        "description": "Inspect missing child thread",
                                        "subagent_type": "explorer",
                                    },
                                }
                            ],
                        },
                    }
                )
            )
            handle.write("\n")
            handle.write(
                json.dumps(
                    {
                        "type": "user",
                        "uuid": "claude-user-missing-child",
                        "timestamp": "2026-03-18T09:00:26Z",
                        "sessionId": "claude-session-1",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "tool-task-missing",
                                    "content": json.dumps(
                                        {
                                            "agentId": "claude-agent-missing",
                                            "nickname": "Ghost",
                                        }
                                    ),
                                }
                            ],
                        },
                    }
                )
            )

        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                response = client.get("/conversations/-Users-tony-Code-helaicopter/claude-session-1/dag")
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert response.status_code == 200
        node_by_session_id = {node["session_id"]: node for node in response.json()["nodes"]}
        assert node_by_session_id["claude-agent-missing"]["has_transcript"] is False
        assert node_by_session_id["claude-agent-missing"]["path"] is None


class TestProjectsHistoryAndTasks:
    def test_projects_history_and_tasks(self, conversations_client: TestClient) -> None:
        projects = conversations_client.get("/projects")
        assert projects.status_code == 200
        payload = projects.json()
        assert [item["encoded_path"] for item in payload] == [
            "codex:-Users-tony-Code-helaicopter",
            "-Users-tony-Code-helaicopter",
        ]
        assert payload[0]["display_name"] == "Codex/Code/helaicopter"
        assert payload[0]["full_path"] == "codex:-Users-tony-Code-helaicopter"
        assert payload[0]["session_count"] == 2
        assert payload[1]["display_name"] == "Code/helaicopter"
        assert payload[1]["full_path"].endswith("/.claude/projects/-Users-tony-Code-helaicopter")
        assert payload[1]["session_count"] == 2
        assert payload[0]["last_activity"] >= payload[1]["last_activity"]

        history = conversations_client.get("/history", params={"limit": 2})
        assert history.status_code == 200
        assert history.json() == [
            {
                "display": "codex history",
                "pasted_contents": None,
                "timestamp": 1763290900000.0,
                "project": "019cdbff-dbb7-71d0-baaf-c669c55af628",
            },
            {
                "display": "claude history",
                "pasted_contents": None,
                "timestamp": 1763287000000.0,
                "project": None,
            },
        ]

        filesystem_tasks = conversations_client.get("/tasks/claude-session-1")
        assert filesystem_tasks.status_code == 200
        assert filesystem_tasks.json() == {
            "session_id": "claude-session-1",
            "tasks": [{"taskId": "T007", "title": "Conversation API"}],
        }

        persisted_tasks = conversations_client.get("/tasks/historic-session")
        assert persisted_tasks.status_code == 200
        assert persisted_tasks.json() == {
            "session_id": "historic-session",
            "tasks": [{"taskId": "T009", "title": "Historic persisted task"}],
        }

        missing_child_tasks = conversations_client.get("/tasks/claude-agent-1")
        assert missing_child_tasks.status_code == 200
        assert missing_child_tasks.json() == {
            "session_id": "claude-agent-1",
            "tasks": [],
        }

        child_tasks = conversations_client.get(
            "/tasks/claude-agent-1",
            params={"parent_session_id": "claude-session-1"},
        )
        assert child_tasks.status_code == 200
        assert child_tasks.json() == {
            "session_id": "claude-agent-1",
            "tasks": [{"taskId": "T008", "title": "Inspect DAG child thread"}],
        }

    def test_openapi_exposes_new_routes_and_schemas(self, conversations_client: TestClient) -> None:
        response = conversations_client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "/conversation-dags" in schema["paths"]
        assert "/conversations" in schema["paths"]
        assert "/conversations/by-ref/{conversation_ref}" in schema["paths"]
        assert "/conversations/{project_path}/{session_id}" in schema["paths"]
        assert "/conversations/{project_path}/{session_id}/dag" in schema["paths"]
        assert "/conversations/{project_path}/{session_id}/subagents/{agent_id}" in schema["paths"]
        assert "/projects" in schema["paths"]
        assert "/history" in schema["paths"]
        assert "/subagents/{project_path}/{session_id}/{agent_id}" in schema["paths"]
        assert "/tasks/{session_id}" in schema["paths"]

        conversations_get = schema["paths"]["/conversations"]["get"]
        parameters = {param["name"]: param for param in conversations_get["parameters"]}
        assert set(parameters) == {"project", "days"}
        assert conversations_get["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith(
            "/ConversationSummaryResponse"
        )

        dag_list_get = schema["paths"]["/conversation-dags"]["get"]
        dag_parameters = {param["name"]: param for param in dag_list_get["parameters"]}
        assert set(dag_parameters) == {"project", "days", "provider"}
        assert dag_list_get["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith(
            "/ConversationDagSummaryResponse"
        )

        detail_get = schema["paths"]["/conversations/{project_path}/{session_id}"]["get"]
        detail_parameters = {param["name"]: param for param in detail_get["parameters"]}
        assert set(detail_parameters) == {"project_path", "session_id", "parent_session_id"}
        assert detail_parameters["parent_session_id"]["in"] == "query"

        dag_detail_get = schema["paths"]["/conversations/{project_path}/{session_id}/dag"]["get"]
        dag_detail_parameters = {param["name"]: param for param in dag_detail_get["parameters"]}
        assert set(dag_detail_parameters) == {"project_path", "session_id", "parent_session_id"}
        assert dag_detail_parameters["parent_session_id"]["in"] == "query"
        assert dag_detail_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ConversationDagResponse"
        )

        by_ref_get = schema["paths"]["/conversations/by-ref/{conversation_ref}"]["get"]
        assert by_ref_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ConversationRefResolutionResponse"
        )

        history_get = schema["paths"]["/history"]["get"]
        assert history_get["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith(
            "/HistoryEntryResponse"
        )

        tasks_get = schema["paths"]["/tasks/{session_id}"]["get"]
        tasks_parameters = {param["name"]: param for param in tasks_get["parameters"]}
        assert set(tasks_parameters) == {"session_id", "parent_session_id"}
        assert tasks_parameters["parent_session_id"]["in"] == "query"
        assert tasks_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/TaskListResponse"
        )

        message_schema = schema["components"]["schemas"]["ConversationMessageResponse"]
        block_items = message_schema["properties"]["blocks"]["items"]
        assert block_items["discriminator"]["propertyName"] == "type"
        assert set(block_items["discriminator"]["mapping"]) == {"text", "thinking", "tool_call"}

        summary_schema = schema["components"]["schemas"]["ConversationSummaryResponse"]
        assert "route_slug" in summary_schema["properties"]
        assert "conversation_ref" in summary_schema["properties"]

        detail_schema = schema["components"]["schemas"]["ConversationDetailResponse"]
        assert "route_slug" in detail_schema["properties"]
        assert "conversation_ref" in detail_schema["properties"]

        plan_schema = schema["components"]["schemas"]["ConversationPlanResponse"]
        assert "route_slug" in plan_schema["properties"]
        assert "conversation_ref" in plan_schema["properties"]

        subagent_schema = schema["components"]["schemas"]["ConversationSubagentResponse"]
        assert "route_slug" in subagent_schema["properties"]
        assert "conversation_ref" in subagent_schema["properties"]

        dag_node_schema = schema["components"]["schemas"]["ConversationDagNodeResponse"]
        path_schema = dag_node_schema["properties"]["path"]
        assert path_schema.get("nullable") is True or {"type": "null"} in path_schema.get("anyOf", [])


def test_conversation_persistence_ids_make_entity_grain_explicit() -> None:
    conversation = conversation_id("claude", "session-123")
    message = conversation_message_id(conversation, 7)

    assert conversation == "claude:session-123"
    assert message == "claude:session-123:message:7"
    assert conversation_message_block_id(message, 3) == "claude:session-123:message:7:block:3"
    assert conversation_plan_row_id(conversation, 1) == "claude:session-123:plan:1"
    assert conversation_subagent_row_id(conversation, 2) == "claude:session-123:subagent:2"
    assert conversation_task_row_id(conversation, 4) == "claude:session-123:task:4"
    assert conversation_context_bucket_id(conversation, 5) == "claude:session-123:bucket:5"
    assert conversation_context_step_id(conversation, 6) == "claude:session-123:step:6"
