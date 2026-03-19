"""Pure conversation DAG construction for backend APIs."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import quote

from helaicopter_api.schema.conversations import (
    ConversationDagEdgeResponse,
    ConversationDagNodeResponse,
    ConversationDagResponse,
    ConversationDagStatsResponse,
    ConversationDetailResponse,
    ConversationSubagentResponse,
)


def build_conversation_dag(
    *,
    project_path: str,
    root_session_id: str,
    load_conversation: Callable[[str, str | None], ConversationDetailResponse | None],
) -> ConversationDagResponse | None:
    """Build a deterministic conversation/sub-agent DAG from shaped details."""
    nodes: dict[str, ConversationDagNodeResponse] = {}
    edges: dict[str, ConversationDagEdgeResponse] = {}
    expanded: set[str] = set()
    active_path: set[str] = set()

    def visit(
        session_id: str,
        depth: int,
        *,
        parent_session_id: str | None = None,
        subagent: ConversationSubagentResponse | None = None,
    ) -> None:
        if parent_session_id is not None:
            edge_id = f"{parent_session_id}->{session_id}"
            edges[edge_id] = ConversationDagEdgeResponse(
                id=edge_id,
                source=parent_session_id,
                target=session_id,
            )

        existing = nodes.get(session_id)
        if existing is not None and existing.depth <= depth and session_id in expanded:
            return

        should_load = subagent is None or subagent.has_file
        conversation = load_conversation(session_id, parent_session_id) if should_load else None
        next_node = _to_node(
            project_path=project_path,
            session_id=session_id,
            depth=min(existing.depth, depth) if existing is not None else depth,
            parent_session_id=parent_session_id,
            conversation=conversation,
            subagent=subagent,
            is_root=parent_session_id is None,
        )
        nodes[session_id] = next_node if existing is None else existing.model_copy(update=next_node.model_dump())

        if conversation is None or session_id in expanded or session_id in active_path:
            return

        active_path.add(session_id)
        expanded.add(session_id)
        for child in conversation.subagents:
            if child.agent_id == session_id:
                continue
            visit(
                child.agent_id,
                next_node.depth + 1,
                parent_session_id=session_id,
                subagent=child,
            )
        active_path.remove(session_id)

    visit(root_session_id, 0)
    root_node = nodes.get(root_session_id)
    if root_node is None or not root_node.has_transcript:
        return None

    ordered_nodes = sorted(
        nodes.values(),
        key=lambda node: (node.depth, node.timestamp, node.id),
    )
    ordered_edges = sorted(edges.values(), key=lambda edge: edge.id)
    return ConversationDagResponse(
        project_path=project_path,
        root_session_id=root_session_id,
        nodes=ordered_nodes,
        edges=ordered_edges,
        stats=_compute_stats(root_session_id=root_session_id, nodes=ordered_nodes, edges=ordered_edges),
    )


def _to_node(
    *,
    project_path: str,
    session_id: str,
    depth: int,
    parent_session_id: str | None,
    conversation: ConversationDetailResponse | None,
    subagent: ConversationSubagentResponse | None,
    is_root: bool,
) -> ConversationDagNodeResponse:
    fallback_label = (
        (subagent.nickname if subagent is not None else None)
        or (subagent.description if subagent is not None else None)
        or f"{'Conversation' if is_root else 'Sub-agent'} {session_id[:8]}"
    )
    return ConversationDagNodeResponse(
        id=session_id,
        session_id=session_id,
        parent_session_id=parent_session_id,
        project_path=project_path,
        label=_summarize_label(conversation, fallback_label),
        description=subagent.description if subagent is not None else None,
        nickname=subagent.nickname if subagent is not None else None,
        subagent_type=subagent.subagent_type if subagent is not None else None,
        thread_type="main" if is_root else "subagent",
        has_transcript=conversation is not None,
        model=conversation.model if conversation is not None else None,
        message_count=len(conversation.messages) if conversation is not None else 0,
        total_tokens=_conversation_total_tokens(conversation),
        timestamp=conversation.last_updated_at if conversation is not None else 0,
        depth=depth,
        path=_conversation_node_path(
            project_path=project_path,
            parent_session_id=parent_session_id,
            session_id=session_id,
            is_root=is_root,
        ),
        is_root=is_root,
    )


def _conversation_node_path(
    *,
    project_path: str,
    parent_session_id: str | None,
    session_id: str,
    is_root: bool,
) -> str:
    encoded_project_path = quote(project_path, safe="")
    if is_root:
        return f"/conversations/{encoded_project_path}/{session_id}"
    assert parent_session_id is not None
    return f"/conversations/{encoded_project_path}/{parent_session_id}/subagents/{session_id}"


def _summarize_label(conversation: ConversationDetailResponse | None, fallback: str) -> str:
    if conversation is None:
        return fallback
    for message in conversation.messages:
        for block in message.blocks:
            if block.type == "text" and block.text and block.text.strip():
                return " ".join(block.text.split())[:120]
    return fallback


def _conversation_total_tokens(conversation: ConversationDetailResponse | None) -> int:
    if conversation is None:
        return 0
    usage = conversation.total_usage
    return (
        usage.input_tokens
        + usage.output_tokens
        + usage.cache_creation_tokens
        + usage.cache_read_tokens
    )


def _compute_stats(
    *,
    root_session_id: str,
    nodes: list[ConversationDagNodeResponse],
    edges: list[ConversationDagEdgeResponse],
) -> ConversationDagStatsResponse:
    breadth_by_depth: dict[int, int] = {}
    out_degree: dict[str, int] = {}

    for node in nodes:
        breadth_by_depth[node.depth] = breadth_by_depth.get(node.depth, 0) + 1
        out_degree[node.id] = 0
    for edge in edges:
        out_degree[edge.source] = out_degree.get(edge.source, 0) + 1

    return ConversationDagStatsResponse(
        total_nodes=len(nodes),
        total_edges=len(edges),
        total_subagent_nodes=sum(1 for node in nodes if not node.is_root),
        max_depth=max((node.depth for node in nodes), default=0),
        max_breadth=max(breadth_by_depth.values(), default=0),
        leaf_count=sum(1 for node in nodes if out_degree.get(node.id, 0) == 0),
        root_subagent_count=out_degree.get(root_session_id, 0),
        total_messages=sum(node.message_count for node in nodes),
        total_tokens=sum(node.total_tokens for node in nodes),
    )
