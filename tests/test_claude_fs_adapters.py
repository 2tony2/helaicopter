"""Tests for Claude filesystem adapters."""

from __future__ import annotations

from pathlib import Path

from helaicopter_api.adapters.claude_fs import (
    ClaudeArtifactStore,
    FileConversationReader,
    FileHistoryReader,
    FilePlanReader,
    FileTaskReader,
)
from helaicopter_api.ports.claude_fs import ClaudeTaskPayload


def build_store(tmp_path: Path) -> ClaudeArtifactStore:
    return ClaudeArtifactStore(
        projects_dir=tmp_path / "projects",
        plans_dir=tmp_path / "plans",
        history_file=tmp_path / "history.jsonl",
        tasks_dir=tmp_path / "tasks",
    )


class TestFileConversationReader:
    def test_missing_projects_dir_returns_empty_results(self, tmp_path):
        reader = FileConversationReader(build_store(tmp_path))

        assert reader.list_projects() == []
        assert reader.list_sessions("missing-project") == []
        assert reader.read_session_events("missing-project", "missing-session") == []

    def test_skips_malformed_json_and_normalizes_keys(self, tmp_path):
        session_dir = tmp_path / "projects" / "repo"
        session_dir.mkdir(parents=True)
        session_dir.joinpath("session-1.jsonl").write_text(
            "\n".join(
                [
                    '{"type":"assistant","uuid":"evt-1","sessionId":"session-1","gitBranch":"main","planContent":"# Plan","message":{"role":"assistant","model":"claude-sonnet"}}',
                    "{not json",
                    '{"uuid":"evt-2"}',
                    '"scalar"',
                ]
            ),
            encoding="utf-8",
        )

        reader = FileConversationReader(build_store(tmp_path))
        events = reader.read_session_events("repo", "session-1")

        assert len(events) == 1
        assert events[0].session_id == "session-1"
        assert events[0].git_branch == "main"
        assert events[0].plan_content == "# Plan"
        assert reader.list_projects()[0].session_ids == ["session-1"]
        assert reader.list_sessions("repo")[0].session_id == "session-1"


class TestFileHistoryReader:
    def test_missing_history_file_returns_empty_list(self, tmp_path):
        reader = FileHistoryReader(build_store(tmp_path))

        assert reader.read_history() == []

    def test_skips_malformed_entries_and_applies_limit(self, tmp_path):
        history_file = tmp_path / "history.jsonl"
        history_file.write_text(
            "\n".join(
                [
                    '{"display":"first","timestamp":1,"pastedContents":{"a":1}}',
                    "{not json",
                    '{"timestamp":2}',
                    '{"display":"second","timestamp":2}',
                ]
            ),
            encoding="utf-8",
        )

        reader = FileHistoryReader(build_store(tmp_path))
        entries = reader.read_history(limit=1)

        assert len(entries) == 1
        assert entries[0].display == "second"
        assert entries[0].timestamp == 2
        assert entries[0].pasted_contents is None


class TestFilePlanReader:
    def test_missing_plans_dir_and_missing_plan_return_empty_values(self, tmp_path):
        reader = FilePlanReader(build_store(tmp_path))

        assert reader.list_plans() == []
        assert reader.read_plan("missing") is None

    def test_reads_markdown_plan_files(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir(parents=True)
        plans_dir.joinpath("alpha.md").write_text("# Alpha\n\nBody", encoding="utf-8")
        plans_dir.joinpath("notes.txt").write_text("ignore", encoding="utf-8")

        reader = FilePlanReader(build_store(tmp_path))
        plans = reader.list_plans()

        assert [plan.slug for plan in plans] == ["alpha"]
        assert plans[0].content == "# Alpha\n\nBody"
        assert reader.read_plan("alpha") is not None


class TestFileTaskReader:
    def test_missing_task_dir_returns_empty_list(self, tmp_path):
        reader = FileTaskReader(build_store(tmp_path))

        assert reader.read_tasks("missing-session") == []

    def test_reads_only_valid_json_object_tasks(self, tmp_path):
        task_dir = tmp_path / "tasks" / "session-1"
        task_dir.mkdir(parents=True)
        task_dir.joinpath("task-1.json").write_text('{"taskId":"T007","title":"Conversation API"}', encoding="utf-8")
        task_dir.joinpath("task-2.json").write_text("{not json", encoding="utf-8")
        task_dir.joinpath("task-3.json").write_text('["not","an","object"]', encoding="utf-8")

        reader = FileTaskReader(build_store(tmp_path))

        assert reader.read_tasks("session-1") == [
            ClaudeTaskPayload.model_validate({"taskId": "T007", "title": "Conversation API"})
        ]
