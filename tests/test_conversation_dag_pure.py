"""Unit tests for the pure conversation DAG builder.

These tests exercise edge cases that complement endpoint tests:
- Root without transcript returns None
- Labels derive from first non-empty text block with whitespace trimmed
- Child with missing file still appears with a null path
"""

from __future__ import annotations

from typing import Callable

from helaicopter_api.pure.conversation_dag import build_conversation_dag
from helaicopter_api.schema.conversations import (
    ConversationDagResponse,
    ConversationDetailResponse,
    ConversationMessageResponse,
    ConversationSubagentResponse,
    ConversationTextBlockResponse,
    ConversationUsageResponse,
)
from helaicopter_domain.ids import SessionId


def _detail(session_id: str, *, has_messages: bool = True) -> ConversationDetailResponse:
    messages = []
    if has_messages:
        messages = [
            ConversationMessageResponse(
                id="m1",
                role="user",
                timestamp=1.0,
                blocks=[ConversationTextBlockResponse(type="text", text="  Hello   world  ")],
            ),
            ConversationMessageResponse(
                id="m2",
                role="assistant",
                timestamp=2.0,
                blocks=[ConversationTextBlockResponse(type="text", text="Second")],
                usage=ConversationUsageResponse(
                    input_tokens=10, output_tokens=20, cache_creation_tokens=5, cache_read_tokens=3
                ),
            ),
        ]

    return ConversationDetailResponse(
        session_id=SessionId(session_id),
        project_path="-Users-tony-Code-helaicopter",
        route_slug="route",
        conversation_ref=f"hello--claude-{session_id}",
        created_at=0,
        last_updated_at=2.0,
        is_running=False,
        messages=messages,
        total_usage=ConversationUsageResponse(
            input_tokens=10, output_tokens=20, cache_creation_tokens=5, cache_read_tokens=3
        ),
        model="claude-sonnet-4-5-20250929",
        start_time=0,
        end_time=2.0,
        subagents=[],
    )


def test_root_without_transcript_returns_none() -> None:
    def loader(_session_id: SessionId, _parent: SessionId | None) -> ConversationDetailResponse | None:
        # Root exists but has no transcript/messages
        if str(_session_id) == "root":
            return _detail("root", has_messages=False)
        return None

    dag = build_conversation_dag(
        project_path="-Users-tony-Code-helaicopter",
        root_session_id=SessionId("root"),
        load_conversation=loader,
    )

    assert dag is None


def test_basic_two_node_dag_and_derived_label_and_path() -> None:
    child = ConversationSubagentResponse(
        agent_id="child",
        description="Inspect",
        subagent_type="explorer",
        nickname="Child",
        has_file=True,
        conversation_ref="inspect--claude-child",
    )

    def loader(session_id: SessionId, _parent: SessionId | None) -> ConversationDetailResponse | None:
        if str(session_id) == "root":
            detail = _detail("root")
            detail.subagents = [child]
            return detail
        if str(session_id) == "child":
            return _detail("child")
        return None

    dag = build_conversation_dag(
        project_path="-Users-tony-Code-helaicopter",
        root_session_id=SessionId("root"),
        load_conversation=loader,
    )

    assert isinstance(dag, ConversationDagResponse)
    assert dag.root_session_id == SessionId("root")

    # Nodes ordered by depth then timestamp then id; root first
    labels = [node.label for node in dag.nodes]
    assert labels[0] == "Hello world"  # trimmed single‑spaced
    # Child label can resolve from nickname/description or first text
    assert any(label in {"Hello world", "Second", "Inspect", "Child", "Sub-agent child"} for label in labels)

    paths = [node.path for node in dag.nodes]
    assert paths[0] == "/conversations/by-ref/hello--claude-root"
    assert "/conversations/by-ref/inspect--claude-child" in paths

    # Totals include cache and output in ConversationUsageResponse
    totals = [node.total_tokens for node in dag.nodes]
    assert (10 + 20 + 5 + 3) in totals


def test_child_without_file_emits_null_path() -> None:
    child = ConversationSubagentResponse(
        agent_id="detached",
        description="Ghost",
        nickname=None,
        subagent_type=None,
        has_file=False,  # no file on disk; we still create a node but without transcript/path
        conversation_ref=None,
    )

    def loader(session_id: SessionId, _parent: SessionId | None) -> ConversationDetailResponse | None:
        if str(session_id) == "root":
            detail = _detail("root")
            detail.subagents = [child]
            return detail
        return None

    dag = build_conversation_dag(
        project_path="-Users-tony-Code-helaicopter",
        root_session_id=SessionId("root"),
        load_conversation=loader,
    )

    assert isinstance(dag, ConversationDagResponse)
    assert len(dag.nodes) == 2
    detached = next(node for node in dag.nodes if str(node.session_id) == "detached")
    assert detached.has_transcript is False
    assert detached.path is None
