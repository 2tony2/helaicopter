"""Tests for execution envelope construction."""

from __future__ import annotations

from oats.envelope import build_execution_envelope, ExecutionEnvelope, RetryPolicy
from oats.graph import TaskKind, TaskNode


class TestEnvelopeConstruction:
    def test_envelope_captures_all_required_fields(self) -> None:
        """Execution envelope captures all required fields."""
        task = TaskNode(task_id="auth", kind=TaskKind.IMPLEMENTATION, title="Auth")
        envelope = build_execution_envelope(
            task=task,
            run_id="run_abc",
            agent="codex",
            model="o3-pro",
            worktree_path="/tmp/wt",
            parent_branch="feat/x",
            timeout_seconds=600,
            max_attempts=3,
        )

        assert envelope.session_id.startswith("sess_")
        assert envelope.attempt_id.startswith("att_")
        assert envelope.task_id == "auth"
        assert envelope.run_id == "run_abc"
        assert envelope.agent == "codex"
        assert envelope.model == "o3-pro"
        assert envelope.timeout_seconds == 600
        assert envelope.retry_policy.max_attempts == 3
        assert envelope.worktree_path == "/tmp/wt"
        assert envelope.parent_branch == "feat/x"

    def test_unique_ids_per_attempt(self) -> None:
        """Each attempt for the same task gets a unique session_id and attempt_id."""
        task = TaskNode(task_id="auth", kind=TaskKind.IMPLEMENTATION, title="Auth")
        e1 = build_execution_envelope(
            task=task, run_id="run_abc", agent="claude",
            model="claude-sonnet-4-6", worktree_path="/tmp/wt1",
            parent_branch="feat/x", timeout_seconds=300, max_attempts=2,
        )
        e2 = build_execution_envelope(
            task=task, run_id="run_abc", agent="claude",
            model="claude-sonnet-4-6", worktree_path="/tmp/wt2",
            parent_branch="feat/x", timeout_seconds=300, max_attempts=2,
        )
        assert e1.session_id != e2.session_id
        assert e1.attempt_id != e2.attempt_id

    def test_default_retry_policy(self) -> None:
        """Default retry policy has sensible defaults."""
        task = TaskNode(task_id="t", kind=TaskKind.IMPLEMENTATION, title="T")
        envelope = build_execution_envelope(
            task=task, run_id="run_x", agent="claude",
            model="claude-sonnet-4-6", worktree_path="/tmp/wt",
            parent_branch="main", timeout_seconds=300,
        )
        assert envelope.retry_policy.max_attempts >= 1
        assert len(envelope.retry_policy.backoff_seconds) > 0

    def test_discovery_enabled_flag(self) -> None:
        """Discovery can be enabled/disabled."""
        task = TaskNode(task_id="t", kind=TaskKind.IMPLEMENTATION, title="T")
        e1 = build_execution_envelope(
            task=task, run_id="run_x", agent="claude",
            model="claude-sonnet-4-6", worktree_path="/tmp/wt",
            parent_branch="main", timeout_seconds=300,
            discovery_enabled=True,
        )
        e2 = build_execution_envelope(
            task=task, run_id="run_x", agent="claude",
            model="claude-sonnet-4-6", worktree_path="/tmp/wt",
            parent_branch="main", timeout_seconds=300,
            discovery_enabled=False,
        )
        assert e1.discovery_enabled is True
        assert e2.discovery_enabled is False
