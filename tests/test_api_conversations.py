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
from helaicopter_api.bootstrap.services import build_services, invalidate_backend_read_caches
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
    openclaw_dir = tmp_path / ".openclaw"
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
    openclaw_main_sessions_dir = openclaw_dir / "agents" / "main" / "sessions"
    openclaw_secondary_sessions_dir = openclaw_dir / "agents" / "secondary" / "sessions"
    openclaw_main_sessions_dir.mkdir(parents=True)
    openclaw_secondary_sessions_dir.mkdir(parents=True)

    openclaw_main_session_id = "openclaw-main-session"
    openclaw_secondary_session_id = "openclaw-secondary-session"
    openclaw_alias_artifact_id = "artifact-session-id"
    openclaw_alias_payload_id = "payload-session-id"
    openclaw_main_sessions_dir.joinpath("sessions.json").write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "id": openclaw_main_session_id,
                        "updatedAt": "2026-03-19T12:00:06Z",
                        "title": "Review OpenClaw backend rollout",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    openclaw_secondary_sessions_dir.joinpath("sessions.json").write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "id": openclaw_secondary_session_id,
                        "updatedAt": "2026-03-19T12:05:01Z",
                        "title": "Inspect secondary agent transcript",
                    },
                    {
                        "id": openclaw_alias_artifact_id,
                        "updatedAt": "2026-03-19T12:06:03Z",
                        "title": "Alias session id transcript",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    openclaw_main_session = openclaw_main_sessions_dir / f"{openclaw_main_session_id}.jsonl"
    openclaw_main_session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "session",
                        "timestamp": "2026-03-19T12:00:00Z",
                        "session": {
                            "id": openclaw_main_session_id,
                            "cwd": "/tmp/not-the-grouping-key",
                            "agentId": "main",
                            "title": "Review OpenClaw backend rollout",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "model_change",
                        "timestamp": "2026-03-19T12:00:01Z",
                        "model": "gpt-5",
                        "provider": "openai-codex",
                    }
                ),
                json.dumps(
                    {
                        "type": "thinking_level_change",
                        "timestamp": "2026-03-19T12:00:02Z",
                        "thinkingLevel": "high",
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-19T12:00:03Z",
                        "message": {
                            "id": "openclaw-user-1",
                            "role": "user",
                            "content": [{"type": "text", "text": "Review OpenClaw backend rollout"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-19T12:00:04Z",
                        "message": {
                            "id": "openclaw-assistant-1",
                            "role": "assistant",
                            "model": "gpt-5",
                            "usage": {
                                "inputTokens": 100,
                                "outputTokens": 40,
                                "cacheReadTokens": 5,
                                "cacheCreationTokens": 2,
                                "reasoningTokens": 12,
                            },
                            "content": [
                                {"type": "text", "text": "Starting backend scan."},
                                {"type": "thinking", "thinking": "Need to inspect all agent trees."},
                                {
                                    "type": "toolCall",
                                    "toolCallId": "tool-oc-1",
                                    "toolName": "Shell",
                                    "input": {"cmd": "ls agents"},
                                },
                            ],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-19T12:00:05Z",
                        "message": {
                            "id": "openclaw-tool-result-1",
                            "role": "toolResult",
                            "toolCallId": "tool-oc-1",
                            "toolName": "Shell",
                            "isError": False,
                            "content": [{"type": "text", "text": "agents/main\nagents/secondary"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-19T12:00:05.250000Z",
                        "message": {
                            "id": "openclaw-tool-result-1b",
                            "role": "toolResult",
                            "toolCallId": "tool-oc-1",
                            "toolName": "Shell",
                            "isError": False,
                            "content": [{"type": "text", "text": "agents/main resolved"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "custom",
                        "timestamp": "2026-03-19T12:00:05.500000Z",
                        "data": {"note": "safe to ignore"},
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-19T12:00:06Z",
                        "message": {
                            "id": "openclaw-tool-result-2",
                            "role": "tool",
                            "toolCallId": "tool-oc-unmatched",
                            "toolName": "Shell",
                            "isError": True,
                            "content": [{"type": "text", "text": "unmatched stderr"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "unknown_event",
                        "timestamp": "2026-03-19T12:00:07Z",
                        "payload": {"ignored": True},
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-19T12:00:08Z",
                        "message": {
                            "id": "openclaw-assistant-2",
                            "role": "assistant",
                            "usage": {
                                "inputTokens": 130,
                                "outputTokens": 55,
                                "cacheReadTokens": 8,
                                "cacheCreationTokens": 4,
                                "reasoningTokens": 18,
                            },
                            "content": [{"type": "text", "text": "Completed discovery."}],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    openclaw_secondary_session = openclaw_secondary_sessions_dir / f"{openclaw_secondary_session_id}.jsonl"
    openclaw_secondary_session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "session",
                        "timestamp": "2026-03-19T12:05:00Z",
                        "session": {
                            "id": openclaw_secondary_session_id,
                            "cwd": "/Users/tony/Code/helaicopter",
                            "agentId": "secondary",
                            "title": "Inspect secondary agent transcript",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-19T12:05:01Z",
                        "message": {
                            "id": "openclaw-secondary-user-1",
                            "role": "user",
                            "content": [{"type": "text", "text": "Inspect secondary agent transcript"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-19T12:05:02Z",
                        "message": {
                            "id": "openclaw-secondary-assistant-1",
                            "role": "assistant",
                            "model": "gpt-4.1",
                            "usage": {"inputTokens": 20, "outputTokens": 10},
                            "content": [{"type": "text", "text": "Secondary transcript loaded."}],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    openclaw_alias_session = openclaw_secondary_sessions_dir / f"{openclaw_alias_artifact_id}.jsonl"
    openclaw_alias_session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "session",
                        "timestamp": "2026-03-19T12:06:00Z",
                        "session": {
                            "id": openclaw_alias_payload_id,
                            "cwd": "/tmp/alias-session",
                            "agentId": "secondary",
                            "title": "Alias session id transcript",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-19T12:06:01Z",
                        "message": {
                            "id": "openclaw-alias-user-1",
                            "role": "user",
                            "content": [{"type": "text", "text": "Alias session id transcript"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-19T12:06:02Z",
                        "message": {
                            "id": "openclaw-alias-assistant-1",
                            "role": "assistant",
                            "model": "gpt-4.1",
                            "usage": {"inputTokens": 9, "outputTokens": 4},
                            "content": [{"type": "text", "text": "Payload session id should win."}],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    os.utime(openclaw_main_session, (1_763_585_608, 1_763_585_608))
    os.utime(openclaw_secondary_session, (1_763_585_902, 1_763_585_902))
    os.utime(openclaw_alias_session, (1_763_585_963, 1_763_585_963))
    _write_app_db(tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite")

    return Settings(
        project_root=tmp_path,
        claude_dir=claude_dir,
        codex_dir=codex_dir,
        openclaw_dir=openclaw_dir,
    )


def _seed_openclaw_archive_family(settings: Settings) -> None:
    sessions_dir = settings.openclaw_agents_dir / "main" / "sessions"
    sessions_json_path = sessions_dir / "sessions.json"
    sessions_json = json.loads(sessions_json_path.read_text(encoding="utf-8"))
    sessions = list(sessions_json.get("sessions", []))
    sessions.append(
        {
            "id": "primary",
            "updatedAt": "2026-03-22T03:00:11.497Z",
            "title": "Primary stitched family",
        }
    )
    sessions_json["sessions"] = sessions
    sessions_json["entries"] = {
        "agent:main:main": {
            "sessionId": "primary",
            "title": "Primary stitched family",
            "skills": {
                "prompt": "Follow the OpenClaw rollout checklist",
                "names": ["verification-before-completion", "requesting-code-review"],
            },
            "systemPrompt": {
                "workspaceDir": "/Users/tony/Code/helaicopter",
                "content": "You are working in the helaicopter workspace.",
            },
            "usage": {
                "totalTokens": 275,
            },
        }
    }
    sessions_json_path.write_text(json.dumps(sessions_json), encoding="utf-8")

    primary_live = sessions_dir / "primary.jsonl"
    primary_live.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "session",
                        "timestamp": "2026-03-22T03:00:00Z",
                        "workspaceDir": "/Users/tony/Code/helaicopter",
                        "session": {
                            "id": "primary",
                            "agentId": "main",
                            "title": "Primary live transcript",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "model_change",
                        "timestamp": "2026-03-22T03:00:01Z",
                        "model": "gpt-5",
                        "provider": "openai-codex",
                    }
                ),
                json.dumps(
                    {
                        "type": "thinking_level_change",
                        "timestamp": "2026-03-22T03:00:02Z",
                        "thinkingLevel": "max",
                    }
                ),
                json.dumps(
                    {
                        "type": "custom",
                        "timestamp": "2026-03-22T03:00:03Z",
                        "data": {
                            "kind": "skills",
                            "prompt": "Transcript skill prompt",
                            "names": ["verification-before-completion"],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "custom_message",
                        "timestamp": "2026-03-22T03:00:03.250000Z",
                        "data": {
                            "kind": "system_prompt",
                            "workspaceDir": "/Users/tony/Code/helaicopter",
                            "content": "Prefer repository-local evidence.",
                        },
                        "label": "provider-note",
                    }
                ),
                json.dumps(
                    {
                        "type": "compaction",
                        "timestamp": "2026-03-22T03:00:03.500000Z",
                        "data": {
                            "beforeTokens": 320,
                            "afterTokens": 210,
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "branch_summary",
                        "timestamp": "2026-03-22T03:00:03.750000Z",
                        "data": {
                            "branch": "codex/openclaw-provider-detail",
                            "status": "in_progress",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-22T03:00:04Z",
                        "message": {
                            "id": "primary-user-1",
                            "role": "user",
                            "content": [{"type": "text", "text": "Inspect provider detail stitching"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-22T03:00:05Z",
                        "message": {
                            "id": "primary-assistant-1",
                            "role": "assistant",
                            "model": "gpt-5",
                            "usage": {
                                "inputTokens": 111,
                                "outputTokens": 68,
                                "cacheReadTokens": 12,
                                "cacheCreationTokens": 4,
                                "reasoningTokens": 21,
                            },
                            "content": [
                                {"type": "text", "text": "Provider detail is stitched from the live transcript."}
                            ],
                            "checkpoint": "provider-detail",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "unknown_event",
                        "timestamp": "2026-03-22T03:00:06Z",
                        "payload": {"note": "keep for raw diagnostics"},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    reset_archive = sessions_dir / "primary.jsonl.reset.2026-03-22T03-00-11.497Z"
    reset_archive.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "session",
                        "timestamp": "2026-03-22T03:00:11.497Z",
                        "session": {
                            "id": "primary",
                            "agentId": "main",
                            "title": "Primary archive reset",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": "2026-03-22T03:00:11.600000Z",
                        "message": {
                            "id": "archive-user-1",
                            "role": "user",
                            "content": [{"type": "text", "text": "Archive-only context"}],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    deleted_archive = sessions_dir / "secondary.jsonl.deleted.2026-03-21T08-39-54.467Z"
    deleted_archive.write_text(
        json.dumps(
            {
                "type": "session",
                "timestamp": "2026-03-21T08:39:54.467Z",
                "session": {
                    "id": "secondary",
                    "agentId": "main",
                    "title": "Secondary archive deleted",
                },
            }
        ),
        encoding="utf-8",
    )
    os.utime(primary_live, (1_763_805_600, 1_763_805_600))
    os.utime(reset_archive, (1_763_805_611, 1_763_805_611))
    os.utime(deleted_archive, (1_763_719_194, 1_763_719_194))
    settings.openclaw_memory_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    _seed_openclaw_memory_store(settings.openclaw_memory_sqlite_path)


def _seed_openclaw_memory_store(
    path: Path,
    *,
    workspace_root: str = "/Users/tony/Code/helaicopter",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE files (
              id INTEGER PRIMARY KEY,
              path TEXT NOT NULL,
              source TEXT
            );

            CREATE TABLE chunks (
              id INTEGER PRIMARY KEY,
              file_id INTEGER NOT NULL,
              source TEXT,
              FOREIGN KEY(file_id) REFERENCES files(id)
            );

            CREATE TABLE embedding_cache (
              id INTEGER PRIMARY KEY,
              cache_key TEXT NOT NULL
            );

            CREATE TABLE memory_summary (
              id INTEGER PRIMARY KEY,
              kind TEXT NOT NULL,
              value TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO files (id, path, source) VALUES (?, ?, ?)",
            [
                (1, f"{workspace_root}/src/hooks/use-conversations.ts", "workspace"),
                (2, f"{workspace_root}/python/helaicopter_api/application/conversations.py", "workspace"),
                (3, "/Users/tony/Code/other-project/README.md", "external"),
            ],
        )
        connection.executemany(
            "INSERT INTO chunks (id, file_id, source) VALUES (?, ?, ?)",
            [
                (1, 1, "workspace"),
                (2, 1, "workspace"),
                (3, 2, "workspace"),
                (4, 3, "external"),
            ],
        )
        connection.executemany(
            "INSERT INTO embedding_cache (id, cache_key) VALUES (?, ?)",
            [
                (1, "workspace:1"),
                (2, "workspace:2"),
            ],
        )
        connection.executemany(
            "INSERT INTO memory_summary (id, kind, value) VALUES (?, ?, ?)",
            [
                (1, "index_version", "3"),
                (2, "last_refresh", "2026-03-22T03:00:11.497Z"),
            ],
        )
        connection.commit()
    finally:
        connection.close()


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

    def test_openclaw_list_discovers_all_agents_and_uses_agent_project_paths(
        self,
        conversations_client: TestClient,
    ) -> None:
        response = conversations_client.get("/conversations")

        assert response.status_code == 200
        payload = response.json()
        by_session = {item["session_id"]: item for item in payload}

        main_summary = by_session["openclaw-main-session"]
        assert main_summary["project_path"] == "openclaw:agent:main"
        assert main_summary["project_name"] == "openclaw:agent:main"
        assert main_summary["route_slug"] == "review-openclaw-backend-rollout"
        assert (
            main_summary["conversation_ref"]
            == "review-openclaw-backend-rollout--openclaw-openclaw:agent:main::openclaw-main-session"
        )
        assert main_summary["model"] == "gpt-5"
        assert main_summary["reasoning_effort"] == "high"
        assert main_summary["total_input_tokens"] == 130
        assert main_summary["total_output_tokens"] == 55
        assert main_summary["total_cache_creation_tokens"] == 4
        assert main_summary["total_cache_read_tokens"] == 8
        assert main_summary["total_reasoning_tokens"] == 18
        assert main_summary["tool_breakdown"] == {"Shell": 2}
        assert main_summary["failed_tool_call_count"] == 1
        assert main_summary["message_count"] == 5

        secondary_summary = by_session["openclaw-secondary-session"]
        assert secondary_summary["project_path"] == "openclaw:agent:secondary"
        assert secondary_summary["conversation_ref"] == (
            "inspect-secondary-agent-transcript--openclaw-openclaw:agent:secondary::openclaw-secondary-session"
        )

        filtered = conversations_client.get("/conversations", params={"project": "openclaw:agent:main"})
        assert filtered.status_code == 200
        assert [item["session_id"] for item in filtered.json()] == ["openclaw-main-session"]

    def test_openclaw_archive_discovery_exposes_live_archive_session_and_memory_metadata(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        _seed_openclaw_archive_family(settings)
        services = build_services(settings)

        transcripts = services.openclaw_store.list_transcript_artifacts()
        by_name = {Path(item.path).name: item for item in transcripts}
        live_artifact = by_name["primary.jsonl"]
        reset_archive = by_name["primary.jsonl.reset.2026-03-22T03-00-11.497Z"]
        deleted_archive = by_name["secondary.jsonl.deleted.2026-03-21T08-39-54.467Z"]
        session_store = services.openclaw_store.read_session_store(agent_id="main")
        memory_meta = services.openclaw_store.read_memory_store_metadata()
        snapshot = services.openclaw_store.read_discovery_snapshot()

        assert live_artifact.kind == "live_transcript"
        assert reset_archive.kind == "reset_archive"
        assert deleted_archive.kind == "deleted_archive"
        assert session_store is not None
        assert session_store.entries["agent:main:main"]["sessionId"] == "primary"
        assert memory_meta.exists is True
        assert memory_meta.path.endswith("/.openclaw/memory/main.sqlite")
        assert str(settings.openclaw_agents_dir / "main" / "sessions") in snapshot.sessions_dir_mtimes
        assert str(settings.openclaw_agents_dir / "main" / "sessions" / "sessions.json") in snapshot.session_store_mtimes
        assert snapshot.signature

    def test_openclaw_archive_discovery_skips_unreadable_transcript_and_session_store_files(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        _seed_openclaw_archive_family(settings)
        services = build_services(settings)

        broken_transcript = settings.openclaw_agents_dir / "main" / "sessions" / "broken.jsonl"
        broken_transcript.write_bytes(b"\x80not-utf8")
        broken_store = settings.openclaw_agents_dir / "secondary" / "sessions" / "sessions.json"
        broken_store.write_bytes(b"\x80not-utf8")

        transcripts = services.openclaw_store.list_transcript_artifacts()

        assert "broken.jsonl" not in {Path(item.path).name for item in transcripts}
        assert services.openclaw_store.read_session_store(agent_id="secondary") is None

    def test_openclaw_archive_discovery_skips_permission_denied_sessions_dir(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _seed_sources(tmp_path)
        services = build_services(settings)
        original_iterdir = Path.iterdir
        blocked_dir = settings.openclaw_agents_dir / "secondary" / "sessions"

        def _guarded_iterdir(path: Path):
            if path == blocked_dir:
                raise PermissionError("permission denied")
            return original_iterdir(path)

        monkeypatch.setattr(Path, "iterdir", _guarded_iterdir)

        transcripts = services.openclaw_store.list_transcript_artifacts()

        assert {item.agent_id for item in transcripts} == {"main"}

    def test_invalidate_backend_read_caches_clears_openclaw_cache_entries(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        services = build_services(settings)
        services.cache.set("openclaw_session_artifacts", ["stale"])
        services.cache.set("openclaw_transcript_artifacts", ["stale"])
        services.cache.set("openclaw_discovery_snapshot", "stale")
        services.cache.set("openclaw_memory_store_metadata", "stale")
        services.cache.set("openclaw_session_store:main", {"stale": True})

        invalidate_backend_read_caches(services)

        assert services.cache.get("openclaw_session_artifacts") is None
        assert services.cache.get("openclaw_transcript_artifacts") is None
        assert services.cache.get("openclaw_discovery_snapshot") is None
        assert services.cache.get("openclaw_memory_store_metadata") is None
        assert services.cache.get("openclaw_session_store:main") is None

    def test_openclaw_detail_shapes_tool_results_and_ignores_unknown_events(
        self,
        conversations_client: TestClient,
    ) -> None:
        response = conversations_client.get("/conversations/openclaw:agent:main/openclaw-main-session")

        assert response.status_code == 200
        payload = response.json()

        assert payload["project_path"] == "openclaw:agent:main"
        assert payload["route_slug"] == "review-openclaw-backend-rollout"
        assert payload["conversation_ref"] == (
            "review-openclaw-backend-rollout--openclaw-openclaw:agent:main::openclaw-main-session"
        )
        assert payload["model"] == "gpt-5"
        assert payload["reasoning_effort"] == "high"
        assert payload["total_reasoning_tokens"] == 18
        assert payload["total_usage"] == {
            "input_tokens": 130,
            "output_tokens": 55,
            "cache_creation_tokens": 4,
            "cache_read_tokens": 8,
        }
        assert [message["id"] for message in payload["messages"]] == [
            "openclaw-user-1",
            "openclaw-assistant-1",
            "openclaw-tool-result-1b",
            "openclaw-tool-result-2",
            "openclaw-assistant-2",
        ]

        assistant_blocks = payload["messages"][1]["blocks"]
        assert assistant_blocks[0] == {"type": "text", "text": "Starting backend scan."}
        assert assistant_blocks[1]["type"] == "thinking"
        assert assistant_blocks[1]["thinking"] == "Need to inspect all agent trees."
        assert assistant_blocks[2] == {
            "type": "tool_call",
            "tool_use_id": "tool-oc-1",
            "tool_name": "Shell",
            "input": {"cmd": "ls agents"},
            "result": "agents/main\nagents/secondary",
            "is_error": False,
        }

        repeated_tool_result = payload["messages"][2]
        assert repeated_tool_result["role"] == "tool"
        assert repeated_tool_result["blocks"] == [
            {
                "type": "tool_call",
                "tool_use_id": "tool-oc-1",
                "tool_name": "Shell",
                "input": {},
                "result": "agents/main resolved",
                "is_error": False,
            }
        ]

        unmatched_tool_result = payload["messages"][3]
        assert unmatched_tool_result["role"] == "tool"
        assert unmatched_tool_result["blocks"] == [
            {
                "type": "tool_call",
                "tool_use_id": "tool-oc-unmatched",
                "tool_name": "Shell",
                "input": {},
                "result": "unmatched stderr",
                "is_error": True,
            }
        ]

    def test_openclaw_uses_payload_session_id_for_detail_and_ref_resolution(
        self,
        conversations_client: TestClient,
    ) -> None:
        list_response = conversations_client.get("/conversations")

        assert list_response.status_code == 200
        by_session = {item["session_id"]: item for item in list_response.json()}
        alias_summary = by_session["payload-session-id"]
        assert alias_summary["project_path"] == "openclaw:agent:secondary"
        assert alias_summary["conversation_ref"] == (
            "alias-session-id-transcript--openclaw-openclaw:agent:secondary::payload-session-id"
        )

        detail_response = conversations_client.get(
            "/conversations/openclaw:agent:secondary/payload-session-id"
        )
        assert detail_response.status_code == 200
        assert detail_response.json()["session_id"] == "payload-session-id"
        assert detail_response.json()["conversation_ref"] == (
            "alias-session-id-transcript--openclaw-openclaw:agent:secondary::payload-session-id"
        )

        by_ref_response = conversations_client.get(
            "/conversations/by-ref/outdated--openclaw-payload-session-id"
        )
        assert by_ref_response.status_code == 200
        assert by_ref_response.json() == {
            "conversation_ref": "alias-session-id-transcript--openclaw-openclaw:agent:secondary::payload-session-id",
            "route_slug": "alias-session-id-transcript",
            "project_path": "openclaw:agent:secondary",
            "session_id": "payload-session-id",
            "thread_type": "main",
            "parent_session_id": None,
        }

    def test_openclaw_by_ref_resolution_is_unique_across_agents_with_duplicate_session_ids(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        main_sessions_dir = settings.openclaw_agents_dir / "main" / "sessions"
        secondary_sessions_dir = settings.openclaw_agents_dir / "secondary" / "sessions"
        shared_session_id = "shared-session"

        main_sessions_dir.joinpath(f"{shared_session_id}.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "session",
                            "timestamp": "2026-03-22T08:00:00Z",
                            "session": {
                                "id": shared_session_id,
                                "agentId": "main",
                                "title": "Main shared session",
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "type": "message",
                            "timestamp": "2026-03-22T08:00:01Z",
                            "message": {
                                "id": "main-shared-user-1",
                                "role": "user",
                                "content": [{"type": "text", "text": "Main agent duplicate ref"}],
                            },
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )
        secondary_sessions_dir.joinpath(f"{shared_session_id}.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "session",
                            "timestamp": "2026-03-22T08:05:00Z",
                            "session": {
                                "id": shared_session_id,
                                "agentId": "secondary",
                                "title": "Secondary shared session",
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "type": "message",
                            "timestamp": "2026-03-22T08:05:01Z",
                            "message": {
                                "id": "secondary-shared-user-1",
                                "role": "user",
                                "content": [{"type": "text", "text": "Secondary agent duplicate ref"}],
                            },
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )

        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                list_response = client.get("/conversations")
                main_by_ref = client.get(
                    "/conversations/by-ref/main-agent-duplicate-ref--openclaw-openclaw:agent:main::shared-session"
                )
                secondary_by_ref = client.get(
                    "/conversations/by-ref/secondary-agent-duplicate-ref--openclaw-openclaw:agent:secondary::shared-session"
                )
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert list_response.status_code == 200
        shared_summaries = [
            item
            for item in list_response.json()
            if item["session_id"] == shared_session_id and item["provider"] == "openclaw"
        ]
        by_project = {item["project_path"]: item for item in shared_summaries}
        assert by_project["openclaw:agent:main"]["conversation_ref"] == (
            "main-agent-duplicate-ref--openclaw-openclaw:agent:main::shared-session"
        )
        assert by_project["openclaw:agent:secondary"]["conversation_ref"] == (
            "secondary-agent-duplicate-ref--openclaw-openclaw:agent:secondary::shared-session"
        )

        assert main_by_ref.status_code == 200
        assert main_by_ref.json()["project_path"] == "openclaw:agent:main"
        assert main_by_ref.json()["session_id"] == shared_session_id

        assert secondary_by_ref.status_code == 200
        assert secondary_by_ref.json()["project_path"] == "openclaw:agent:secondary"
        assert secondary_by_ref.json()["session_id"] == shared_session_id

    def test_persisted_openclaw_summary_and_detail_keep_agent_qualified_ref(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        archived_session_id = "archived-main-session"
        _insert_persisted_conversation_summary(
            settings.app_sqlite_path,
            provider="openclaw",
            session_id=archived_session_id,
            project_path="openclaw:agent:main",
            project_name="openclaw:agent:main",
            thread_type="main",
            first_message="Persisted main archived session",
            route_slug="persisted-main-archived-session",
            started_at="2026-03-20T10:00:00Z",
            ended_at="2026-03-20T10:10:00Z",
        )
        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                list_response = client.get("/conversations")
                detail_response = client.get(
                    f"/conversations/openclaw:agent:main/{archived_session_id}"
                )
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert list_response.status_code == 200
        archived_summary = next(
            item
            for item in list_response.json()
            if item["provider"] == "openclaw" and item["session_id"] == archived_session_id
        )
        assert archived_summary["project_path"] == "openclaw:agent:main"
        assert archived_summary["conversation_ref"] == (
            "persisted-main-archived-session--openclaw-openclaw:agent:main::archived-main-session"
        )

        assert detail_response.status_code == 200
        assert detail_response.json()["conversation_ref"] == (
            "persisted-main-archived-session--openclaw-openclaw:agent:main::archived-main-session"
        )

    def test_openclaw_by_ref_resolves_persisted_archived_only_conversations(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        archived_session_id = "archived-only-session"
        _insert_persisted_conversation_summary(
            settings.app_sqlite_path,
            provider="openclaw",
            session_id=archived_session_id,
            project_path="openclaw:agent:main",
            project_name="openclaw:agent:main",
            thread_type="main",
            first_message="Persisted archived only session",
            route_slug="persisted-archived-only-session",
            started_at="2026-03-19T09:00:00Z",
            ended_at="2026-03-19T09:05:00Z",
        )
        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                by_ref_response = client.get(
                    "/conversations/by-ref/old-title--openclaw-openclaw:agent:main::archived-only-session"
                )
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert by_ref_response.status_code == 200
        assert by_ref_response.json() == {
            "conversation_ref": (
                "persisted-archived-only-session--openclaw-openclaw:agent:main::archived-only-session"
            ),
            "route_slug": "persisted-archived-only-session",
            "project_path": "openclaw:agent:main",
            "session_id": "archived-only-session",
            "thread_type": "main",
            "parent_session_id": None,
        }

    def test_openclaw_provider_detail_stitches_family_and_attaches_archives(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        _seed_openclaw_archive_family(settings)
        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                summary_response = client.get("/conversations", params={"project": "openclaw:agent:main"})
                detail_response = client.get("/conversations/openclaw:agent:main/primary")
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert summary_response.status_code == 200
        primary_summary = {item["session_id"]: item for item in summary_response.json()}["primary"]
        assert primary_summary["provider"] == "openclaw"

        assert detail_response.status_code == 200
        payload = detail_response.json()
        assert payload["provider"] == "openclaw"
        assert payload["provider_detail"]["kind"] == "openclaw"
        assert payload["total_usage"] == {
            "input_tokens": 111,
            "output_tokens": 68,
            "cache_creation_tokens": 4,
            "cache_read_tokens": 12,
        }
        assert [message["id"] for message in payload["messages"]] == [
            "primary-user-1",
            "primary-assistant-1",
        ]

        openclaw = payload["provider_detail"]["openclaw"]
        assert openclaw["artifact_inventory"]["live_transcript"]["status"] == "live"
        assert openclaw["artifact_inventory"]["live_transcript"]["canonical_session_id"] == "primary"
        assert [item["kind"] for item in openclaw["artifact_inventory"]["attached_archives"]] == [
            "reset_archive"
        ]
        assert openclaw["session_store"]["skills"]["prompt"] == "Follow the OpenClaw rollout checklist"
        assert openclaw["skills"]["prompt"] == "Transcript skill prompt"
        assert openclaw["system_prompt"]["workspace_dir"] == "/Users/tony/Code/helaicopter"
        assert openclaw["usage_reconciliation"]["transcript_total_tokens"] == 195
        assert openclaw["usage_reconciliation"]["store_total_tokens"] == 275
        assert openclaw["memory_store"]["path"].endswith("/.openclaw/memory/main.sqlite")
        assert openclaw["memory_store"]["tables"] == [
            "chunks",
            "embedding_cache",
            "files",
            "memory_summary",
        ]
        assert openclaw["memory_store"]["counts"] == {
            "files": 3,
            "chunks": 4,
            "embedding_cache": 2,
        }
        assert openclaw["memory_store"]["coverage"]["file_sources"] == {
            "external": 1,
            "workspace": 2,
        }
        assert openclaw["memory_store"]["coverage"]["chunk_sources"] == {
            "external": 1,
            "workspace": 3,
        }
        assert openclaw["memory_store"]["workspace_link"] == {
            "workspace_dir": "/Users/tony/Code/helaicopter",
            "matched_prefix": "/Users/tony/Code/helaicopter",
            "confidence": "exact",
            "counts": {
                "files": 2,
                "chunks": 3,
            },
        }
        assert openclaw["memory_store"]["raw_rows"] == [
            {"kind": "index_version", "value": "3"},
            {"kind": "last_refresh", "value": "2026-03-22T03:00:11.497Z"},
        ]
        assert openclaw["transcript_diagnostics"]["event_types"]["custom_message"] == 1
        assert openclaw["transcript_diagnostics"]["event_types"]["branch_summary"] == 1
        assert openclaw["raw"]["session_store_entry"]["sessionId"] == "primary"
        assert openclaw["raw"]["events"][0]["workspaceDir"] == "/Users/tony/Code/helaicopter"
        assert [item["type"] for item in openclaw["raw"]["unhandled_events"]] == ["unknown_event"]

    def test_openclaw_list_polling_skips_memory_sqlite_and_reuses_cached_discovery(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _seed_sources(tmp_path)
        _seed_openclaw_archive_family(settings)
        services = build_services(settings)
        memory_connects = 0
        discovery_reads = 0
        transcript_reads = 0
        session_store_reads = 0

        original_connect = sqlite3.connect
        original_read_discovery_snapshot = services.openclaw_store.read_discovery_snapshot
        original_list_transcript_artifacts = services.openclaw_store.list_transcript_artifacts
        original_read_session_store = services.openclaw_store.read_session_store

        def _counting_connect(database: object, *args: object, **kwargs: object):
            nonlocal memory_connects
            if str(settings.openclaw_memory_sqlite_path) in str(database):
                memory_connects += 1
            return original_connect(database, *args, **kwargs)

        def _counting_read_discovery_snapshot():
            nonlocal discovery_reads
            discovery_reads += 1
            return original_read_discovery_snapshot()

        def _counting_list_transcript_artifacts():
            nonlocal transcript_reads
            transcript_reads += 1
            return original_list_transcript_artifacts()

        def _counting_read_session_store(*, agent_id: str):
            nonlocal session_store_reads
            session_store_reads += 1
            return original_read_session_store(agent_id=agent_id)

        monkeypatch.setattr(sqlite3, "connect", _counting_connect)
        monkeypatch.setattr(
            services.openclaw_store,
            "read_discovery_snapshot",
            _counting_read_discovery_snapshot,
        )
        monkeypatch.setattr(
            services.openclaw_store,
            "list_transcript_artifacts",
            _counting_list_transcript_artifacts,
        )
        monkeypatch.setattr(
            services.openclaw_store,
            "read_session_store",
            _counting_read_session_store,
        )

        first = conversations_application.list_conversations(services)

        assert any(item.session_id == "primary" for item in first)
        assert memory_connects == 0
        assert discovery_reads >= 1
        assert transcript_reads == 1
        assert session_store_reads == 2

        services.cache.delete(conversations_application._cache_key("conversation_summaries", "*", "all"))

        second = conversations_application.list_conversations(services)

        assert any(item.session_id == "primary" for item in second)
        assert memory_connects == 0
        assert discovery_reads > 1
        assert transcript_reads == 1
        assert session_store_reads == 2

        sessions_json_path = settings.openclaw_agents_dir / "main" / "sessions" / "sessions.json"
        time.sleep(0.01)
        sessions_json_path.touch()
        services.cache.delete(conversations_application._cache_key("conversation_summaries", "*", "all"))

        third = conversations_application.list_conversations(services)

        assert any(item.session_id == "primary" for item in third)
        assert memory_connects == 0
        assert discovery_reads > 2
        assert transcript_reads == 1
        assert session_store_reads == 3

    def test_openclaw_detail_opens_memory_store_only_for_detail_requests(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _seed_sources(tmp_path)
        _seed_openclaw_archive_family(settings)
        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services
        memory_connects = 0
        original_connect = sqlite3.connect

        def _counting_connect(database: object, *args: object, **kwargs: object):
            nonlocal memory_connects
            if str(settings.openclaw_memory_sqlite_path) in str(database):
                memory_connects += 1
            return original_connect(database, *args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", _counting_connect)

        try:
            with TestClient(application) as client:
                list_response = client.get("/conversations", params={"project": "openclaw:agent:main"})
                detail_response = client.get("/conversations/openclaw:agent:main/primary")
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert list_response.status_code == 200
        assert detail_response.status_code == 200
        assert memory_connects == 1

    def test_openclaw_memory_store_without_exact_join_stays_global_only(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        _seed_openclaw_archive_family(settings)
        _seed_openclaw_memory_store(
            settings.openclaw_memory_sqlite_path,
            workspace_root="/Users/tony/Code/unrelated-workspace",
        )
        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                detail_response = client.get("/conversations/openclaw:agent:main/primary")
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert detail_response.status_code == 200
        memory_store = detail_response.json()["provider_detail"]["openclaw"]["memory_store"]
        assert memory_store["counts"] == {
            "files": 3,
            "chunks": 4,
            "embedding_cache": 2,
        }
        assert memory_store.get("workspace_link") is None

    def test_openclaw_provider_detail_system_prompt_falls_back_to_header_workspace_dir(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        _seed_openclaw_archive_family(settings)
        sessions_dir = settings.openclaw_agents_dir / "main" / "sessions"
        sessions_json_path = sessions_dir / "sessions.json"
        sessions_json = json.loads(sessions_json_path.read_text(encoding="utf-8"))
        sessions_json["entries"]["agent:main:main"].pop("systemPrompt", None)
        sessions_json_path.write_text(json.dumps(sessions_json), encoding="utf-8")

        primary_path = sessions_dir / "primary.jsonl"
        lines = [
            json.loads(line)
            for line in primary_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        filtered_lines = [line for line in lines if line.get("type") != "custom_message"]
        primary_path.write_text(
            "\n".join(json.dumps(line) for line in filtered_lines),
            encoding="utf-8",
        )

        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                detail_response = client.get("/conversations/openclaw:agent:main/primary")
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert detail_response.status_code == 200
        assert (
            detail_response.json()["provider_detail"]["openclaw"]["system_prompt"]["workspace_dir"]
            == "/Users/tony/Code/helaicopter"
        )

    def test_openclaw_provider_detail_canonical_identity_prefers_header_then_filename_stem(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        sessions_dir = settings.openclaw_agents_dir / "main" / "sessions"
        sessions_json_path = sessions_dir / "sessions.json"
        sessions_json = json.loads(sessions_json_path.read_text(encoding="utf-8"))
        sessions_json["entries"] = {
            "agent:main:header": {"sessionId": "store-header-id"},
            "agent:main:filename": {"sessionId": "store-filename-id"},
        }
        sessions_json_path.write_text(json.dumps(sessions_json), encoding="utf-8")
        sessions_dir.joinpath("header-filename.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "session",
                            "timestamp": "2026-03-22T05:00:00Z",
                            "session": {"id": "header-wins", "agentId": "main"},
                        }
                    ),
                    json.dumps(
                        {
                            "type": "message",
                            "timestamp": "2026-03-22T05:00:01Z",
                            "message": {
                                "id": "header-user-1",
                                "role": "user",
                                "content": [{"type": "text", "text": "Header identity should win"}],
                            },
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )
        sessions_dir.joinpath("filename-wins.jsonl").write_text(
            json.dumps(
                {
                    "type": "message",
                    "timestamp": "2026-03-22T05:05:00Z",
                    "message": {
                        "id": "filename-user-1",
                        "role": "user",
                        "content": [{"type": "text", "text": "Filename identity should win"}],
                    },
                }
            ),
            encoding="utf-8",
        )
        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                response = client.get("/conversations", params={"project": "openclaw:agent:main"})
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert response.status_code == 200
        by_session = {item["session_id"]: item for item in response.json()}
        assert "header-wins" in by_session
        assert "filename-wins" in by_session
        assert "store-header-id" not in by_session
        assert "store-filename-id" not in by_session

    def test_openclaw_headerless_live_transcript_uses_session_store_fallback_for_summary_detail_and_ref(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        sessions_dir = settings.openclaw_agents_dir / "main" / "sessions"
        sessions_json_path = sessions_dir / "sessions.json"
        sessions_json = json.loads(sessions_json_path.read_text(encoding="utf-8"))
        sessions_json["entries"] = {
            "agent:main:fallback": {
                "sessionId": "store-fallback-id",
                "sessionFile": str(sessions_dir / "fallback-live.jsonl"),
            }
        }
        sessions_json_path.write_text(json.dumps(sessions_json), encoding="utf-8")
        sessions_dir.joinpath("fallback-live.jsonl").write_text(
            json.dumps(
                {
                    "type": "message",
                    "timestamp": "2026-03-22T06:00:00Z",
                    "message": {
                        "id": "fallback-user-1",
                        "role": "user",
                        "content": [{"type": "text", "text": "Store fallback should route this transcript"}],
                    },
                }
            ),
            encoding="utf-8",
        )

        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                list_response = client.get("/conversations", params={"project": "openclaw:agent:main"})
                detail_response = client.get("/conversations/openclaw:agent:main/fallback-live")
                by_ref_response = client.get(
                    "/conversations/by-ref/outdated--openclaw-fallback-live"
                )
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert list_response.status_code == 200
        by_session = {item["session_id"]: item for item in list_response.json()}
        assert "fallback-live" in by_session
        assert "store-fallback-id" not in by_session

        assert detail_response.status_code == 200
        assert detail_response.json()["session_id"] == "fallback-live"
        assert (
            detail_response.json()["provider_detail"]["openclaw"]["raw"]["session_store_entry"]["sessionId"]
            == "store-fallback-id"
        )

        assert by_ref_response.status_code == 200
        assert by_ref_response.json()["session_id"] == "fallback-live"
        assert by_ref_response.json()["project_path"] == "openclaw:agent:main"

    def test_openclaw_session_file_match_beats_weaker_session_store_candidates(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _seed_sources(tmp_path)
        sessions_dir = settings.openclaw_agents_dir / "main" / "sessions"
        sessions_json_path = sessions_dir / "sessions.json"
        sessions_json = json.loads(sessions_json_path.read_text(encoding="utf-8"))
        target_path = sessions_dir / "ambiguous-live.jsonl"
        sessions_json["entries"] = {
            "agent:main:strong": {
                "sessionId": "session-file-wins",
                "sessionFile": str(target_path),
            },
            "agent:main:weaker": {
                "sessionId": "ambiguous-live",
                "title": "Same title but weaker evidence",
            },
        }
        sessions_json_path.write_text(json.dumps(sessions_json), encoding="utf-8")
        target_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "session",
                            "timestamp": "2026-03-22T06:05:00Z",
                            "session": {
                                "agentId": "main",
                                "title": "Same title but weaker evidence",
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "type": "message",
                            "timestamp": "2026-03-22T06:05:01Z",
                            "message": {
                                "id": "ambiguous-user-1",
                                "role": "user",
                                "content": [{"type": "text", "text": "sessionFile should win"}],
                            },
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )

        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                list_response = client.get("/conversations", params={"project": "openclaw:agent:main"})
                detail_response = client.get("/conversations/openclaw:agent:main/ambiguous-live")
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert list_response.status_code == 200
        by_session = {item["session_id"]: item for item in list_response.json()}
        assert "ambiguous-live" in by_session
        assert "session-file-wins" not in by_session

        assert detail_response.status_code == 200
        assert detail_response.json()["session_id"] == "ambiguous-live"
        assert (
            detail_response.json()["provider_detail"]["openclaw"]["raw"]["session_store_entry"]["sessionId"]
            == "session-file-wins"
        )

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
            "openclaw:agent:secondary",
            "openclaw:agent:main",
            "codex:-Users-tony-Code-helaicopter",
            "-Users-tony-Code-helaicopter",
        ]
        assert payload[0]["display_name"] == "openclaw:agent:secondary"
        assert payload[0]["full_path"] == "openclaw:agent:secondary"
        assert payload[0]["session_count"] == 2
        assert payload[1]["display_name"] == "openclaw:agent:main"
        assert payload[1]["full_path"] == "openclaw:agent:main"
        assert payload[1]["session_count"] == 1
        assert payload[2]["display_name"] == "Codex/Code/helaicopter"
        assert payload[2]["full_path"] == "codex:-Users-tony-Code-helaicopter"
        assert payload[2]["session_count"] == 2
        assert payload[3]["display_name"] == "Code/helaicopter"
        assert payload[3]["full_path"].endswith("/.claude/projects/-Users-tony-Code-helaicopter")
        assert payload[3]["session_count"] == 2
        assert (
            payload[0]["last_activity"]
            >= payload[1]["last_activity"]
            >= payload[2]["last_activity"]
            >= payload[3]["last_activity"]
        )

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
