"""Concrete adapter for the app-local OLTP SQLite artifact."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from helaicopter_api.ports.app_sqlite import (
    AppSqliteStore,
    ConversationEvaluationRecord,
    EvaluationPromptRecord,
    HistoricalContextBucket,
    HistoricalContextStep,
    HistoricalConversationMessage,
    HistoricalConversationPlan,
    HistoricalConversationRecord,
    HistoricalConversationSubagent,
    HistoricalConversationSummary,
    HistoricalMessageBlock,
    ProviderSubscriptionSetting,
    SubscriptionSettings,
    SupportedProvider,
)

DEFAULT_EVALUATION_PROMPT_ID = "default-conversation-review"
DEFAULT_EVALUATION_PROMPT_NAME = "Default Conversation Review"
DEFAULT_EVALUATION_PROMPT_DESCRIPTION = (
    "Default review prompt for diagnosing instruction quality and conversation flow."
)
DEFAULT_EVALUATION_PROMPT = """Review this assistant conversation as an operator trying to improve future prompts, instructions, and conversation flow.

Focus on:
- unclear or under-specified user instructions
- avoidable tool failures and recovery quality
- places where the assistant should have clarified sooner
- bloated or distracting turns that increased cost without moving the task forward
- concrete rewrites that would make the next run cleaner

Return markdown with these sections:
## Executive Summary
## Instruction Problems
## Conversation Flow Problems
## Concrete Prompt Improvements
## Concrete Recovery Improvements
## Suggested Better Opening Prompt
## Top 3 Highest-Leverage Changes

Every recommendation should be concrete, actionable, and tied to specific message ids or tool calls when possible."""
DEFAULT_MONTHLY_COST = 200.0
_PROVIDERS: tuple[SupportedProvider, SupportedProvider] = ("claude", "codex")


class SqliteAppStore(AppSqliteStore):
    """Read historical app-local data and persist mutable app settings."""

    def __init__(self, *, db_path: Path) -> None:
        self._db_path = db_path

    def list_historical_conversations(
        self,
        *,
        project_path: str | None = None,
        days: int | None = None,
    ) -> list[HistoricalConversationSummary]:
        connection = self._connect_readonly()
        if connection is None or not _table_exists(connection, "conversations"):
            if connection is not None:
                connection.close()
            return []

        try:
            clauses: list[str] = []
            params: list[object] = []
            if project_path:
                clauses.append("project_path = ?")
                params.append(project_path)
            if days is not None:
                since = datetime.now(UTC) - timedelta(days=days)
                clauses.append("datetime(ended_at) >= datetime(?)")
                params.append(since.isoformat())
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = connection.execute(
                f"""
                SELECT
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
                FROM conversations
                {where}
                ORDER BY datetime(ended_at) DESC, conversation_id ASC
                """,
                tuple(params),
            ).fetchall()
            conversation_ids = [row["conversation_id"] for row in rows]
            tool_breakdowns = self._load_tool_breakdowns(connection, conversation_ids)
            failed_tool_call_counts = self._load_failed_tool_call_counts(connection, conversation_ids)
            subagent_breakdowns = self._load_subagent_breakdowns(connection, conversation_ids)
            return [
                _map_historical_summary(
                    row,
                    failed_tool_call_count=failed_tool_call_counts.get(row["conversation_id"], 0),
                    tool_breakdown=tool_breakdowns.get(row["conversation_id"], {}),
                    subagent_type_breakdown=subagent_breakdowns.get(row["conversation_id"], {}),
                )
                for row in rows
            ]
        finally:
            connection.close()

    def get_historical_conversation(
        self,
        *,
        project_path: str,
        session_id: str,
    ) -> HistoricalConversationRecord | None:
        connection = self._connect_readonly()
        if connection is None or not _table_exists(connection, "conversations"):
            if connection is not None:
                connection.close()
            return None

        try:
            row = connection.execute(
                """
                SELECT
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
                FROM conversations
                WHERE project_path = ? AND session_id = ?
                """,
                (project_path, session_id),
            ).fetchone()
            if row is None:
                return None

            conversation_id = row["conversation_id"]
            messages = self._load_messages(connection, conversation_id)
            return HistoricalConversationRecord(
                **_map_historical_summary(row).model_dump(),
                messages=messages,
                plans=self._load_plans(connection, conversation_id),
                subagents=self._load_subagents(connection, conversation_id),
                tasks=self._load_tasks(connection, conversation_id),
                context_buckets=self._load_context_buckets(connection, conversation_id),
                context_steps=self._load_context_steps(connection, conversation_id),
            )
        finally:
            connection.close()

    def get_historical_tasks_for_session(self, session_id: str) -> list[dict] | None:
        connection = self._connect_readonly()
        if connection is None or not _table_exists(connection, "conversations"):
            if connection is not None:
                connection.close()
            return None

        try:
            row = connection.execute(
                "SELECT conversation_id FROM conversations WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return self._load_tasks(connection, row["conversation_id"])
        finally:
            connection.close()

    def ensure_default_evaluation_prompt(self) -> EvaluationPromptRecord:
        if not self._db_path.exists():
            return _default_prompt()

        connection = self._connect_writable()
        try:
            if not _table_exists(connection, "evaluation_prompts"):
                return _default_prompt()

            default_prompt = _default_prompt()
            connection.execute(
                """
                INSERT OR IGNORE INTO evaluation_prompts (
                  prompt_id,
                  name,
                  description,
                  prompt_text,
                  is_default,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    default_prompt.prompt_id,
                    default_prompt.name,
                    default_prompt.description,
                    default_prompt.prompt_text,
                    default_prompt.created_at,
                    default_prompt.updated_at,
                ),
            )
            connection.commit()
            row = connection.execute(
                """
                SELECT
                  prompt_id,
                  name,
                  description,
                  prompt_text,
                  is_default,
                  created_at,
                  updated_at
                FROM evaluation_prompts
                WHERE prompt_id = ?
                """,
                (DEFAULT_EVALUATION_PROMPT_ID,),
            ).fetchone()
            if row is None:
                return default_prompt
            return _map_prompt_row(row)
        finally:
            connection.close()

    def list_evaluation_prompts(self) -> list[EvaluationPromptRecord]:
        connection = self._connect_readonly()
        if connection is None or not _table_exists(connection, "evaluation_prompts"):
            if connection is not None:
                connection.close()
            return [_default_prompt()]

        try:
            rows = connection.execute(
                """
                SELECT
                  prompt_id,
                  name,
                  description,
                  prompt_text,
                  is_default,
                  created_at,
                  updated_at
                FROM evaluation_prompts
                ORDER BY is_default DESC, datetime(updated_at) DESC, name ASC
                """
            ).fetchall()
            prompts = [_map_prompt_row(row) for row in rows]
            if not any(prompt.prompt_id == DEFAULT_EVALUATION_PROMPT_ID for prompt in prompts):
                prompts.insert(0, _default_prompt())
            return prompts
        finally:
            connection.close()

    def get_evaluation_prompt(self, prompt_id: str) -> EvaluationPromptRecord | None:
        if prompt_id == DEFAULT_EVALUATION_PROMPT_ID:
            return self.ensure_default_evaluation_prompt()

        connection = self._connect_readonly()
        if connection is None or not _table_exists(connection, "evaluation_prompts"):
            if connection is not None:
                connection.close()
            return None

        try:
            row = connection.execute(
                """
                SELECT
                  prompt_id,
                  name,
                  description,
                  prompt_text,
                  is_default,
                  created_at,
                  updated_at
                FROM evaluation_prompts
                WHERE prompt_id = ?
                """,
                (prompt_id,),
            ).fetchone()
            if row is None:
                return None
            return _map_prompt_row(row)
        finally:
            connection.close()

    def create_evaluation_prompt(
        self,
        *,
        name: str,
        prompt_text: str,
        description: str | None = None,
    ) -> EvaluationPromptRecord:
        connection = self._connect_writable()
        try:
            _require_table(connection, "evaluation_prompts")
            prompt_id = str(uuid4())
            now = _now_iso()
            try:
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
                    ) VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (prompt_id, name, description, prompt_text, now, now),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Prompt name already exists.") from error
            connection.commit()
            row = connection.execute(
                """
                SELECT
                  prompt_id,
                  name,
                  description,
                  prompt_text,
                  is_default,
                  created_at,
                  updated_at
                FROM evaluation_prompts
                WHERE prompt_id = ?
                """,
                (prompt_id,),
            ).fetchone()
            return _map_prompt_row(row)
        finally:
            connection.close()

    def update_evaluation_prompt(
        self,
        prompt_id: str,
        *,
        name: str,
        prompt_text: str,
        description: str | None = None,
    ) -> EvaluationPromptRecord:
        if prompt_id == DEFAULT_EVALUATION_PROMPT_ID:
            raise ValueError("The default prompt cannot be edited through the store.")

        connection = self._connect_writable()
        try:
            _require_table(connection, "evaluation_prompts")
            now = _now_iso()
            try:
                cursor = connection.execute(
                    """
                    UPDATE evaluation_prompts
                    SET name = ?, description = ?, prompt_text = ?, updated_at = ?
                    WHERE prompt_id = ?
                    """,
                    (name, description, prompt_text, now, prompt_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Prompt name already exists.") from error
            if cursor.rowcount == 0:
                raise ValueError("Prompt not found.")
            connection.commit()
            row = connection.execute(
                """
                SELECT
                  prompt_id,
                  name,
                  description,
                  prompt_text,
                  is_default,
                  created_at,
                  updated_at
                FROM evaluation_prompts
                WHERE prompt_id = ?
                """,
                (prompt_id,),
            ).fetchone()
            return _map_prompt_row(row)
        finally:
            connection.close()

    def delete_evaluation_prompt(self, prompt_id: str) -> None:
        if prompt_id == DEFAULT_EVALUATION_PROMPT_ID:
            raise ValueError("The default prompt cannot be deleted.")

        connection = self._connect_writable()
        try:
            _require_table(connection, "evaluation_prompts")
            cursor = connection.execute(
                "DELETE FROM evaluation_prompts WHERE prompt_id = ?",
                (prompt_id,),
            )
            if cursor.rowcount == 0:
                raise ValueError("Prompt not found.")
            connection.commit()
        finally:
            connection.close()

    def list_conversation_evaluations(self, conversation_id: str) -> list[ConversationEvaluationRecord]:
        connection = self._connect_readonly()
        if connection is None or not _table_exists(connection, "conversation_evaluations"):
            if connection is not None:
                connection.close()
            return []

        try:
            rows = connection.execute(
                """
                SELECT
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
                FROM conversation_evaluations
                WHERE conversation_id = ?
                ORDER BY datetime(created_at) DESC, evaluation_id DESC
                """,
                (conversation_id,),
            ).fetchall()
            return [_map_evaluation_row(row) for row in rows]
        finally:
            connection.close()

    def create_conversation_evaluation(
        self,
        *,
        conversation_id: str,
        provider: SupportedProvider,
        model: str,
        status: str,
        scope: str,
        prompt_name: str,
        prompt_text: str,
        command: str,
        prompt_id: str | None = None,
        selection_instruction: str | None = None,
        report_markdown: str | None = None,
        raw_output: str | None = None,
        error_message: str | None = None,
        finished_at: str | None = None,
        duration_ms: int | None = None,
    ) -> ConversationEvaluationRecord:
        connection = self._connect_writable()
        try:
            _require_table(connection, "conversation_evaluations")
            evaluation_id = str(uuid4())
            created_at = _now_iso()
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
                    duration_ms,
                ),
            )
            connection.commit()
            row = connection.execute(
                """
                SELECT
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
                FROM conversation_evaluations
                WHERE evaluation_id = ?
                """,
                (evaluation_id,),
            ).fetchone()
            return _map_evaluation_row(row)
        finally:
            connection.close()

    def update_conversation_evaluation(
        self,
        evaluation_id: str,
        *,
        status: str,
        command: str,
        report_markdown: str | None = None,
        raw_output: str | None = None,
        error_message: str | None = None,
        finished_at: str | None = None,
        duration_ms: int | None = None,
    ) -> ConversationEvaluationRecord:
        connection = self._connect_writable()
        try:
            _require_table(connection, "conversation_evaluations")
            cursor = connection.execute(
                """
                UPDATE conversation_evaluations
                SET
                  status = ?,
                  report_markdown = ?,
                  raw_output = ?,
                  error_message = ?,
                  command = ?,
                  finished_at = ?,
                  duration_ms = ?
                WHERE evaluation_id = ?
                """,
                (
                    status,
                    report_markdown,
                    raw_output,
                    error_message,
                    command,
                    finished_at,
                    duration_ms,
                    evaluation_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError("Evaluation not found.")
            connection.commit()
            row = connection.execute(
                """
                SELECT
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
                FROM conversation_evaluations
                WHERE evaluation_id = ?
                """,
                (evaluation_id,),
            ).fetchone()
            return _map_evaluation_row(row)
        finally:
            connection.close()

    def get_subscription_settings(self) -> SubscriptionSettings:
        defaults = _default_subscription_settings()
        connection = self._connect_readonly()
        if connection is None or not _table_exists(connection, "subscription_settings"):
            if connection is not None:
                connection.close()
            return defaults

        try:
            rows = connection.execute(
                """
                SELECT provider, has_subscription, monthly_cost, updated_at
                FROM subscription_settings
                """
            ).fetchall()
            data = defaults.model_copy(deep=True)
            for row in rows:
                setting = ProviderSubscriptionSetting(
                    provider=row["provider"],
                    has_subscription=bool(row["has_subscription"]),
                    monthly_cost=float(row["monthly_cost"]),
                    updated_at=row["updated_at"],
                )
                setattr(data, row["provider"], setting)
            return data
        finally:
            connection.close()

    def update_subscription_settings(
        self,
        updates: dict[SupportedProvider, dict[str, object]],
    ) -> SubscriptionSettings:
        connection = self._connect_writable()
        try:
            _ensure_subscription_settings_table(connection)
            _seed_default_subscription_settings_rows(connection, _now_iso())
            connection.commit()
            current = self.get_subscription_settings()
            now = _now_iso()
            for provider in _PROVIDERS:
                update = updates.get(provider)
                if update is None:
                    continue
                existing = getattr(current, provider)
                has_subscription = bool(update.get("has_subscription", existing.has_subscription))
                monthly_cost = float(update.get("monthly_cost", existing.monthly_cost))
                connection.execute(
                    """
                    INSERT INTO subscription_settings (
                      provider,
                      has_subscription,
                      monthly_cost,
                      updated_at
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(provider) DO UPDATE SET
                      has_subscription = excluded.has_subscription,
                      monthly_cost = excluded.monthly_cost,
                      updated_at = excluded.updated_at
                    """,
                    (provider, int(has_subscription), monthly_cost, now),
                )
            connection.commit()
        finally:
            connection.close()
        return self.get_subscription_settings()

    def _load_messages(
        self,
        connection: sqlite3.Connection,
        conversation_id: str,
    ) -> list[HistoricalConversationMessage]:
        if not _table_exists(connection, "conversation_messages"):
            return []
        rows = connection.execute(
            """
            SELECT
              message_id,
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
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY ordinal ASC, timestamp ASC
            """,
            (conversation_id,),
        ).fetchall()
        blocks_by_message = self._load_blocks(connection, [row["message_id"] for row in rows])
        return [
            HistoricalConversationMessage(
                message_id=row["message_id"],
                ordinal=row["ordinal"],
                role=row["role"],
                timestamp=row["timestamp"],
                model=row["model"],
                reasoning_tokens=row["reasoning_tokens"] or 0,
                speed=row["speed"],
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
                cache_write_tokens=row["cache_write_tokens"] or 0,
                cache_read_tokens=row["cache_read_tokens"] or 0,
                text_preview=row["text_preview"] or "",
                blocks=blocks_by_message.get(row["message_id"], []),
            )
            for row in rows
        ]

    def _load_blocks(
        self,
        connection: sqlite3.Connection,
        message_ids: list[str],
    ) -> dict[str, list[HistoricalMessageBlock]]:
        if not message_ids or not _table_exists(connection, "message_blocks"):
            return {}
        placeholders = ", ".join("?" for _ in message_ids)
        rows = connection.execute(
            f"""
            SELECT
              message_id,
              block_index,
              block_type,
              text_content,
              tool_use_id,
              tool_name,
              tool_input_json,
              tool_result_text,
              is_error
            FROM message_blocks
            WHERE message_id IN ({placeholders})
            ORDER BY block_index ASC
            """,
            tuple(message_ids),
        ).fetchall()
        results: dict[str, list[HistoricalMessageBlock]] = {}
        for row in rows:
            results.setdefault(row["message_id"], []).append(
                HistoricalMessageBlock(
                    block_index=row["block_index"],
                    block_type=row["block_type"],
                    text_content=row["text_content"],
                    tool_use_id=row["tool_use_id"],
                    tool_name=row["tool_name"],
                    tool_input_json=row["tool_input_json"],
                    tool_result_text=row["tool_result_text"],
                    is_error=bool(row["is_error"]),
                )
            )
        return results

    def _load_plans(
        self,
        connection: sqlite3.Connection,
        conversation_id: str,
    ) -> list[HistoricalConversationPlan]:
        if not _table_exists(connection, "conversation_plans"):
            return []
        rows = connection.execute(
            """
            SELECT
              plan_row_id,
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
            FROM conversation_plans
            WHERE conversation_id = ?
            ORDER BY datetime(timestamp) DESC, plan_row_id ASC
            """,
            (conversation_id,),
        ).fetchall()
        return [
            HistoricalConversationPlan(
                plan_row_id=row["plan_row_id"],
                plan_id=row["plan_id"],
                slug=row["slug"],
                title=row["title"],
                preview=row["preview"],
                content=row["content"],
                provider=row["provider"],
                timestamp=row["timestamp"],
                model=row["model"],
                explanation=row["explanation"],
                steps=_parse_json_list(row["steps_json"]),
            )
            for row in rows
        ]

    def _load_subagents(
        self,
        connection: sqlite3.Connection,
        conversation_id: str,
    ) -> list[HistoricalConversationSubagent]:
        if not _table_exists(connection, "conversation_subagents"):
            return []
        rows = connection.execute(
            """
            SELECT
              subagent_row_id,
              agent_id,
              description,
              subagent_type,
              nickname,
              has_file
            FROM conversation_subagents
            WHERE conversation_id = ?
            ORDER BY subagent_row_id ASC
            """,
            (conversation_id,),
        ).fetchall()
        return [
            HistoricalConversationSubagent(
                subagent_row_id=row["subagent_row_id"],
                agent_id=row["agent_id"],
                description=row["description"],
                subagent_type=row["subagent_type"],
                nickname=row["nickname"],
                has_file=bool(row["has_file"]),
            )
            for row in rows
        ]

    def _load_tasks(
        self,
        connection: sqlite3.Connection,
        conversation_id: str,
    ) -> list[dict]:
        if not _table_exists(connection, "conversation_tasks"):
            return []
        rows = connection.execute(
            """
            SELECT task_json
            FROM conversation_tasks
            WHERE conversation_id = ?
            ORDER BY ordinal ASC, task_row_id ASC
            """,
            (conversation_id,),
        ).fetchall()
        return [
            parsed
            for row in rows
            if isinstance((parsed := _parse_json_value(row["task_json"])), dict)
        ]

    def _load_context_buckets(
        self,
        connection: sqlite3.Connection,
        conversation_id: str,
    ) -> list[HistoricalContextBucket]:
        if not _table_exists(connection, "context_buckets"):
            return []
        rows = connection.execute(
            """
            SELECT
              bucket_row_id,
              label,
              category,
              input_tokens,
              output_tokens,
              cache_write_tokens,
              cache_read_tokens,
              total_tokens,
              calls
            FROM context_buckets
            WHERE conversation_id = ?
            ORDER BY bucket_row_id ASC
            """,
            (conversation_id,),
        ).fetchall()
        return [
            HistoricalContextBucket(
                bucket_row_id=row["bucket_row_id"],
                label=row["label"],
                category=row["category"],
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
                cache_write_tokens=row["cache_write_tokens"] or 0,
                cache_read_tokens=row["cache_read_tokens"] or 0,
                total_tokens=row["total_tokens"] or 0,
                calls=row["calls"] or 0,
            )
            for row in rows
        ]

    def _load_context_steps(
        self,
        connection: sqlite3.Connection,
        conversation_id: str,
    ) -> list[HistoricalContextStep]:
        if not _table_exists(connection, "context_steps"):
            return []
        rows = connection.execute(
            """
            SELECT
              step_row_id,
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
            FROM context_steps
            WHERE conversation_id = ?
            ORDER BY ordinal ASC, step_row_id ASC
            """,
            (conversation_id,),
        ).fetchall()
        return [
            HistoricalContextStep(
                step_row_id=row["step_row_id"],
                message_id=row["message_id"],
                ordinal=row["ordinal"],
                role=row["role"],
                label=row["label"],
                category=row["category"],
                timestamp=row["timestamp"],
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
                cache_write_tokens=row["cache_write_tokens"] or 0,
                cache_read_tokens=row["cache_read_tokens"] or 0,
                total_tokens=row["total_tokens"] or 0,
            )
            for row in rows
        ]

    def _load_tool_breakdowns(
        self,
        connection: sqlite3.Connection,
        conversation_ids: list[str],
    ) -> dict[str, dict[str, int]]:
        if not conversation_ids or not _table_exists(connection, "conversation_messages") or not _table_exists(
            connection, "message_blocks"
        ):
            return {}

        rows = connection.execute(
            f"""
            SELECT cm.conversation_id, mb.tool_name, COUNT(*) AS count
            FROM conversation_messages cm
            JOIN message_blocks mb ON mb.message_id = cm.message_id
            WHERE cm.conversation_id IN ({_placeholders(len(conversation_ids))})
              AND mb.block_type = 'tool_call'
              AND mb.tool_name IS NOT NULL
            GROUP BY cm.conversation_id, mb.tool_name
            """,
            tuple(conversation_ids),
        ).fetchall()
        breakdowns: dict[str, dict[str, int]] = {}
        for row in rows:
            breakdown = breakdowns.setdefault(row["conversation_id"], {})
            breakdown[row["tool_name"]] = row["count"] or 0
        return breakdowns

    def _load_failed_tool_call_counts(
        self,
        connection: sqlite3.Connection,
        conversation_ids: list[str],
    ) -> dict[str, int]:
        if not conversation_ids or not _table_exists(connection, "conversation_messages") or not _table_exists(
            connection, "message_blocks"
        ):
            return {}

        rows = connection.execute(
            f"""
            SELECT cm.conversation_id, COUNT(*) AS count
            FROM conversation_messages cm
            JOIN message_blocks mb ON mb.message_id = cm.message_id
            WHERE cm.conversation_id IN ({_placeholders(len(conversation_ids))})
              AND mb.block_type = 'tool_call'
              AND mb.is_error = 1
            GROUP BY cm.conversation_id
            """,
            tuple(conversation_ids),
        ).fetchall()
        return {row["conversation_id"]: row["count"] or 0 for row in rows}

    def _load_subagent_breakdowns(
        self,
        connection: sqlite3.Connection,
        conversation_ids: list[str],
    ) -> dict[str, dict[str, int]]:
        if not conversation_ids or not _table_exists(connection, "conversation_subagents"):
            return {}

        rows = connection.execute(
            f"""
            SELECT conversation_id, COALESCE(subagent_type, 'unknown') AS subagent_type, COUNT(*) AS count
            FROM conversation_subagents
            WHERE conversation_id IN ({_placeholders(len(conversation_ids))})
            GROUP BY conversation_id, COALESCE(subagent_type, 'unknown')
            """,
            tuple(conversation_ids),
        ).fetchall()
        breakdowns: dict[str, dict[str, int]] = {}
        for row in rows:
            breakdown = breakdowns.setdefault(row["conversation_id"], {})
            breakdown[row["subagent_type"]] = row["count"] or 0
        return breakdowns

    def _connect_readonly(self) -> sqlite3.Connection | None:
        if not self._db_path.exists():
            return None
        uri = f"file:{quote(str(self._db_path))}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def _connect_writable(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _require_table(connection: sqlite3.Connection, table_name: str) -> None:
    if not _table_exists(connection, table_name):
        raise RuntimeError(f"{table_name} table is unavailable in {connection.execute('PRAGMA database_list').fetchone()[2]}")


def _ensure_subscription_settings_table(connection: sqlite3.Connection) -> None:
    if _table_exists(connection, "subscription_settings"):
        return
    connection.execute(
        """
        CREATE TABLE subscription_settings (
          provider TEXT PRIMARY KEY,
          has_subscription INTEGER NOT NULL DEFAULT 1,
          monthly_cost REAL NOT NULL DEFAULT 200,
          updated_at TEXT NOT NULL
        )
        """
    )


def _seed_default_subscription_settings_rows(connection: sqlite3.Connection, updated_at: str) -> None:
    connection.executemany(
        """
        INSERT OR IGNORE INTO subscription_settings (
          provider,
          has_subscription,
          monthly_cost,
          updated_at
        ) VALUES (?, 1, ?, ?)
        """,
        [(provider, DEFAULT_MONTHLY_COST, updated_at) for provider in _PROVIDERS],
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _default_prompt() -> EvaluationPromptRecord:
    now = _now_iso()
    return EvaluationPromptRecord(
        prompt_id=DEFAULT_EVALUATION_PROMPT_ID,
        name=DEFAULT_EVALUATION_PROMPT_NAME,
        description=DEFAULT_EVALUATION_PROMPT_DESCRIPTION,
        prompt_text=DEFAULT_EVALUATION_PROMPT,
        is_default=True,
        created_at=now,
        updated_at=now,
    )


def _default_subscription_settings() -> SubscriptionSettings:
    now = _now_iso()
    return SubscriptionSettings(
        claude=ProviderSubscriptionSetting(
            provider="claude",
            has_subscription=True,
            monthly_cost=DEFAULT_MONTHLY_COST,
            updated_at=now,
        ),
        codex=ProviderSubscriptionSetting(
            provider="codex",
            has_subscription=True,
            monthly_cost=DEFAULT_MONTHLY_COST,
            updated_at=now,
        ),
    )


def _map_historical_summary(
    row: sqlite3.Row,
    *,
    failed_tool_call_count: int = 0,
    tool_breakdown: dict[str, int] | None = None,
    subagent_type_breakdown: dict[str, int] | None = None,
) -> HistoricalConversationSummary:
    return HistoricalConversationSummary(
        conversation_id=row["conversation_id"],
        provider=row["provider"],
        session_id=row["session_id"],
        project_path=row["project_path"],
        project_name=row["project_name"],
        thread_type=row["thread_type"] or "main",
        first_message=row["first_message"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        message_count=row["message_count"] or 0,
        model=row["model"],
        git_branch=row["git_branch"],
        reasoning_effort=row["reasoning_effort"],
        speed=row["speed"],
        total_input_tokens=row["total_input_tokens"] or 0,
        total_output_tokens=row["total_output_tokens"] or 0,
        total_cache_write_tokens=row["total_cache_write_tokens"] or 0,
        total_cache_read_tokens=row["total_cache_read_tokens"] or 0,
        total_reasoning_tokens=row["total_reasoning_tokens"] or 0,
        tool_use_count=row["tool_use_count"] or 0,
        failed_tool_call_count=failed_tool_call_count,
        tool_breakdown=tool_breakdown or {},
        subagent_count=row["subagent_count"] or 0,
        subagent_type_breakdown=subagent_type_breakdown or {},
        task_count=row["task_count"] or 0,
    )


def _map_prompt_row(row: sqlite3.Row) -> EvaluationPromptRecord:
    return EvaluationPromptRecord(
        prompt_id=row["prompt_id"],
        name=row["name"],
        description=row["description"],
        prompt_text=row["prompt_text"],
        is_default=bool(row["is_default"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _map_evaluation_row(row: sqlite3.Row) -> ConversationEvaluationRecord:
    return ConversationEvaluationRecord(
        evaluation_id=row["evaluation_id"],
        conversation_id=row["conversation_id"],
        prompt_id=row["prompt_id"],
        provider=row["provider"],
        model=row["model"],
        status=row["status"],
        scope=row["scope"],
        selection_instruction=row["selection_instruction"],
        prompt_name=row["prompt_name"],
        prompt_text=row["prompt_text"],
        report_markdown=row["report_markdown"],
        raw_output=row["raw_output"],
        error_message=row["error_message"],
        command=row["command"],
        created_at=row["created_at"],
        finished_at=row["finished_at"],
        duration_ms=row["duration_ms"],
    )


def _parse_json_value(raw: str | None) -> object | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _placeholders(count: int) -> str:
    return ",".join("?" for _ in range(count))


def _parse_json_list(raw: str | None) -> list[dict]:
    parsed = _parse_json_value(raw)
    if not isinstance(parsed, list):
        return []
    return [entry for entry in parsed if isinstance(entry, dict)]
