"""Tests for Codex and app-local SQLite adapters."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from helaicopter_api.adapters.app_sqlite import SqliteAppStore
from helaicopter_api.adapters.codex_sqlite import FileCodexStore
from helaicopter_api.ports.app_sqlite import (
    HistoricalConversationPlanStep,
    HistoricalConversationSummary,
    HistoricalConversationTask,
    ProviderSubscriptionSettingUpdate,
    SubscriptionSettingsUpdate,
)


def _create_codex_db(path: Path) -> None:
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
        connection.execute(
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
            (
                "019cdbff-dbb7-71d0-baaf-c669c55af628",
                "Main thread",
                "/Users/tony/Code/helaicopter",
                '{"kind":"main"}',
                "openai",
                42,
                "abc123",
                "main",
                "git@github.com:owner/repo.git",
                "0.1.0",
                "Ship the backend adapters",
                1_742_000_000,
                1_742_000_123,
                "/tmp/rollout.jsonl",
                "planner",
                "delta",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _create_app_db(path: Path) -> None:
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

            CREATE TABLE conversation_plans (
              plan_row_id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              plan_id TEXT NOT NULL,
              slug TEXT NOT NULL,
              title TEXT NOT NULL,
              preview TEXT NOT NULL,
              content TEXT NOT NULL,
              provider TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              model TEXT,
              explanation TEXT,
              steps_json TEXT
            );

            CREATE TABLE conversation_subagents (
              subagent_row_id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              agent_id TEXT NOT NULL,
              description TEXT,
              subagent_type TEXT,
              nickname TEXT,
              has_file INTEGER NOT NULL
            );

            CREATE TABLE conversation_tasks (
              task_row_id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              ordinal INTEGER NOT NULL,
              task_json TEXT NOT NULL
            );

            CREATE TABLE context_buckets (
              bucket_row_id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              label TEXT NOT NULL,
              category TEXT NOT NULL,
              input_tokens INTEGER NOT NULL,
              output_tokens INTEGER NOT NULL,
              cache_write_tokens INTEGER NOT NULL,
              cache_read_tokens INTEGER NOT NULL,
              total_tokens INTEGER NOT NULL,
              calls INTEGER NOT NULL
            );

            CREATE TABLE context_steps (
              step_row_id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              message_id TEXT NOT NULL,
              ordinal INTEGER NOT NULL,
              role TEXT NOT NULL,
              label TEXT NOT NULL,
              category TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              input_tokens INTEGER NOT NULL,
              output_tokens INTEGER NOT NULL,
              cache_write_tokens INTEGER NOT NULL,
              cache_read_tokens INTEGER NOT NULL,
              total_tokens INTEGER NOT NULL
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

            CREATE TABLE subscription_settings (
              provider TEXT PRIMARY KEY,
              has_subscription INTEGER NOT NULL,
              monthly_cost REAL NOT NULL,
              updated_at TEXT NOT NULL
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
                "codex:019cdbff-dbb7-71d0-baaf-c669c55af628",
                "codex",
                "019cdbff-dbb7-71d0-baaf-c669c55af628",
                "codex:-Users-tony-Code-helaicopter",
                "helaicopter",
                "main",
                "Build the adapters",
                "build-the-adapters",
                "2026-03-10T09:00:00+00:00",
                "2026-03-10T09:05:00+00:00",
                1,
                "gpt-5",
                "main",
                "medium",
                "fast",
                10,
                5,
                0,
                0,
                0,
                1,
                1,
                1,
            ),
        )
        connection.execute(
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
            (
                "msg-1",
                "codex:019cdbff-dbb7-71d0-baaf-c669c55af628",
                1,
                "assistant",
                "2026-03-10T09:00:01+00:00",
                "gpt-5",
                0,
                "fast",
                10,
                5,
                0,
                0,
                "Added adapters.",
            ),
        )
        connection.execute(
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
            (
                "block-1",
                "msg-1",
                0,
                "text",
                "Added adapters.",
                None,
                None,
                None,
                None,
                0,
            ),
        )
        connection.execute(
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
            (
                "block-2",
                "msg-1",
                1,
                "tool_call",
                None,
                "tool-1",
                "Read",
                '{"path":"README.md"}',
                "ok",
                1,
            ),
        )
        connection.execute(
            """
            INSERT INTO conversation_plans (
              plan_row_id,
              conversation_id,
              plan_id,
              slug,
              title,
              preview,
              content,
              provider,
              timestamp,
              model,
              explanation,
              steps_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "plan-row-1",
                "codex:019cdbff-dbb7-71d0-baaf-c669c55af628",
                "plan-1",
                "plan-1",
                "Adapter rollout",
                "Build adapters",
                "# Adapter rollout",
                "codex",
                "2026-03-10T09:00:00+00:00",
                "gpt-5",
                "Keep the scope tight.",
                '[{"step":"Build adapters","status":"completed"}]',
            ),
        )
        connection.execute(
            """
            INSERT INTO conversation_subagents (
              subagent_row_id,
              conversation_id,
              agent_id,
              description,
              subagent_type,
              nickname,
              has_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "subagent-row-1",
                "codex:019cdbff-dbb7-71d0-baaf-c669c55af628",
                "agent-1",
                "Review the adapter tests",
                "reviewer",
                "alpha",
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
                "codex:019cdbff-dbb7-71d0-baaf-c669c55af628",
                0,
                '{"taskId":"T006","title":"Codex And App SQLite Adapters"}',
            ),
        )
        connection.execute(
            """
            INSERT INTO context_buckets (
              bucket_row_id,
              conversation_id,
              label,
              category,
              input_tokens,
              output_tokens,
              cache_write_tokens,
              cache_read_tokens,
              total_tokens,
              calls
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "bucket-row-1",
                "codex:019cdbff-dbb7-71d0-baaf-c669c55af628",
                "conversation",
                "conversation",
                10,
                5,
                0,
                0,
                15,
                1,
            ),
        )
        connection.execute(
            """
            INSERT INTO context_steps (
              step_row_id,
              conversation_id,
              message_id,
              ordinal,
              role,
              label,
              category,
              timestamp,
              input_tokens,
              output_tokens,
              cache_write_tokens,
              cache_read_tokens,
              total_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "step-row-1",
                "codex:019cdbff-dbb7-71d0-baaf-c669c55af628",
                "msg-1",
                0,
                "assistant",
                "assistant response",
                "conversation",
                "2026-03-10T09:00:01+00:00",
                10,
                5,
                0,
                0,
                15,
            ),
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
                "First prompt",
                "Stored prompt",
                "Review the conversation",
                0,
                "2026-03-10T09:00:00+00:00",
                "2026-03-10T09:00:00+00:00",
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
                "evaluation-1",
                "codex:019cdbff-dbb7-71d0-baaf-c669c55af628",
                "prompt-1",
                "codex",
                "gpt-5",
                "completed",
                "full",
                None,
                "First prompt",
                "Review the conversation",
                "# Report",
                None,
                None,
                "codex exec -",
                "2026-03-10T09:01:00+00:00",
                "2026-03-10T09:01:03+00:00",
                3000,
            ),
        )
        connection.execute(
            """
            INSERT INTO subscription_settings (
              provider,
              has_subscription,
              monthly_cost,
              updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            ("codex", 0, 50.0, "2026-03-10T09:00:00+00:00"),
        )
        connection.commit()
    finally:
        connection.close()


class TestFileCodexStore:
    def test_missing_sources_return_empty_results(self, tmp_path: Path) -> None:
        store = FileCodexStore(
            sessions_dir=tmp_path / "sessions",
            db_path=tmp_path / "state_5.sqlite",
            history_file=tmp_path / "history.jsonl",
        )

        assert store.list_session_artifacts() == []
        assert store.read_session_artifact("missing") is None
        assert store.list_threads() == []
        assert store.get_thread("missing") is None
        assert store.read_history() == []

    def test_reads_session_artifacts_and_thread_metadata(self, tmp_path: Path) -> None:
        sessions_dir = tmp_path / "sessions" / "2026" / "03" / "10"
        sessions_dir.mkdir(parents=True)
        older = sessions_dir / "rollout-2026-03-10T08-00-00-019cdbff-dbb7-71d0-baaf-c669c55af628.jsonl"
        newer = sessions_dir / "rollout-2026-03-10T08-05-00-019cdbff-dbb7-71d0-baaf-c669c55af629.jsonl"
        ignored = sessions_dir / "notes.jsonl"
        older.write_text('{"type":"session_meta"}\n', encoding="utf-8")
        newer.write_text('{"type":"session_meta","payload":{"id":"child"}}\n', encoding="utf-8")
        ignored.write_text("ignore", encoding="utf-8")
        older.touch()
        newer.touch()

        db_path = tmp_path / "state_5.sqlite"
        _create_codex_db(db_path)
        history_file = tmp_path / "history.jsonl"
        history_file.write_text(
            "\n".join(
                [
                    '{"session_id":"019cdbff-dbb7-71d0-baaf-c669c55af628","ts":10,"text":"older"}',
                    "{not json",
                    '{"session_id":"019cdbff-dbb7-71d0-baaf-c669c55af629","ts":20,"text":"newer"}',
                ]
            ),
            encoding="utf-8",
        )

        store = FileCodexStore(
            sessions_dir=tmp_path / "sessions",
            db_path=db_path,
            history_file=history_file,
        )

        artifacts = store.list_session_artifacts()
        assert [artifact.session_id for artifact in artifacts] == [
            "019cdbff-dbb7-71d0-baaf-c669c55af629",
            "019cdbff-dbb7-71d0-baaf-c669c55af628",
        ]
        assert store.read_session_artifact("019cdbff-dbb7-71d0-baaf-c669c55af628") is not None

        thread = store.get_thread("019cdbff-dbb7-71d0-baaf-c669c55af628")
        assert thread is not None
        assert thread.agent_role == "planner"
        assert thread.cwd == "/Users/tony/Code/helaicopter"
        assert len(store.list_threads()) == 1
        assert [entry.display for entry in store.read_history(limit=1)] == ["newer"]


class TestSqliteAppStore:
    def test_missing_db_returns_defaults(self, tmp_path: Path) -> None:
        store = SqliteAppStore(db_path=tmp_path / "missing.sqlite")

        assert store.list_historical_conversations() == []
        assert (
            store.get_historical_conversation(
                project_path="codex:-Users-tony-Code-helaicopter",
                session_id="missing",
            )
            is None
        )
        assert store.get_historical_tasks_for_session("missing") is None
        assert store.list_conversation_evaluations("missing") == []

        prompts = store.list_evaluation_prompts()
        assert len(prompts) == 1
        assert prompts[0].is_default is True

        settings = store.get_subscription_settings()
        assert settings.claude.has_subscription is True
        assert settings.codex.monthly_cost == 200.0

    def test_historical_detail_uses_validated_fast_paths_for_nested_payloads(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_app_db(db_path)
        store = SqliteAppStore(db_path=db_path)

        monkeypatch.setattr(
            HistoricalConversationSummary,
            "model_dump",
            lambda self, *args, **kwargs: pytest.fail("validated summaries should not be dumped into records"),
        )
        monkeypatch.setattr(
            HistoricalConversationPlanStep,
            "model_validate",
            classmethod(
                lambda cls, *args, **kwargs: pytest.fail("plan steps should use cached adapters instead of per-item model_validate")
            ),
        )
        monkeypatch.setattr(
            HistoricalConversationTask,
            "model_validate",
            classmethod(
                lambda cls, *args, **kwargs: pytest.fail("tasks should use cached adapters instead of per-item model_validate")
            ),
        )

        conversation = store.get_historical_conversation(
            project_path="codex:-Users-tony-Code-helaicopter",
            session_id="019cdbff-dbb7-71d0-baaf-c669c55af628",
        )

        assert conversation is not None
        assert conversation.plans[0].steps[0].step == "Build adapters"
        assert conversation.tasks[0].task_id == "T006"

    def test_reads_historical_records_and_persists_settings(self, tmp_path: Path) -> None:
        db_path = tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
        _create_app_db(db_path)
        store = SqliteAppStore(db_path=db_path)

        summaries = store.list_historical_conversations(project_path="codex:-Users-tony-Code-helaicopter")
        assert len(summaries) == 1
        assert summaries[0].conversation_id == "codex:019cdbff-dbb7-71d0-baaf-c669c55af628"
        assert summaries[0].route_slug == "build-the-adapters"
        assert summaries[0].failed_tool_call_count == 1
        assert summaries[0].tool_breakdown == {"Read": 1}
        assert summaries[0].subagent_type_breakdown == {"reviewer": 1}

        conversation = store.get_historical_conversation(
            project_path="codex:-Users-tony-Code-helaicopter",
            session_id="019cdbff-dbb7-71d0-baaf-c669c55af628",
        )
        assert conversation is not None
        assert conversation.route_slug == "build-the-adapters"
        assert conversation.messages[0].blocks[0].text_content == "Added adapters."
        assert conversation.plans[0].steps[0].step == "Build adapters"
        assert conversation.subagents[0].nickname == "alpha"
        assert conversation.tasks[0].task_id == "T006"
        assert conversation.context_buckets[0].total_tokens == 15
        assert conversation.context_steps[0].message_id == "msg-1"

        prompts = store.list_evaluation_prompts()
        assert [prompt.prompt_id for prompt in prompts[:2]] == [
            "default-conversation-review",
            "prompt-1",
        ]

        created_prompt = store.create_evaluation_prompt(
            name="Second prompt",
            prompt_text="Find rough edges",
            description="Follow-up",
        )
        updated_prompt = store.update_evaluation_prompt(
            created_prompt.prompt_id,
            name="Second prompt updated",
            prompt_text="Find sharper rough edges",
            description="Edited",
        )
        assert updated_prompt.name == "Second prompt updated"

        evaluations = store.list_conversation_evaluations(
            "codex:019cdbff-dbb7-71d0-baaf-c669c55af628"
        )
        assert evaluations[0].evaluation_id == "evaluation-1"

        created_evaluation = store.create_conversation_evaluation(
            conversation_id="codex:019cdbff-dbb7-71d0-baaf-c669c55af628",
            provider="codex",
            model="gpt-5",
            status="running",
            scope="guided_subset",
            prompt_name=updated_prompt.name,
            prompt_text=updated_prompt.prompt_text,
            command="codex exec -",
            prompt_id=updated_prompt.prompt_id,
            selection_instruction="Only inspect the last assistant turn.",
        )
        assert created_evaluation.scope == "guided_subset"
        assert created_evaluation.prompt_id == updated_prompt.prompt_id
        finished_evaluation = store.update_conversation_evaluation(
            created_evaluation.evaluation_id,
            status="completed",
            command="codex exec -m gpt-5 -",
            report_markdown="# Finished",
            raw_output="# Finished",
            error_message=None,
            finished_at="2026-03-18T12:00:00+00:00",
            duration_ms=400,
        )
        assert finished_evaluation.status == "completed"
        assert finished_evaluation.report_markdown == "# Finished"

        settings = store.update_subscription_settings(
            SubscriptionSettingsUpdate(
                claude=ProviderSubscriptionSettingUpdate(
                    has_subscription=False,
                    monthly_cost=123.45,
                )
            )
        )
        assert settings.claude.has_subscription is False
        assert settings.claude.monthly_cost == 123.45
        assert settings.codex.monthly_cost == 50.0

        store.delete_evaluation_prompt(created_prompt.prompt_id)
        prompt_ids = [prompt.prompt_id for prompt in store.list_evaluation_prompts()]
        assert created_prompt.prompt_id not in prompt_ids
