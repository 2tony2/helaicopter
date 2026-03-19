"""Application-layer conversation evaluation job orchestration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ConfigDict, InstanceOf, validate_call

from helaicopter_api.application.conversations import get_conversation
from helaicopter_api.application.evaluation_prompts import resolve_evaluation_prompt
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.evaluations import EvaluationJobRequest, EvaluationJobResult
from helaicopter_api.schema.conversations import ConversationDetailResponse, ConversationMessageBlockResponse
from helaicopter_api.schema.evaluations import (
    ConversationEvaluationCreateRequest,
    ConversationEvaluationResponse,
)


class ConversationEvaluationConversationNotFoundError(LookupError):
    """Raised when the requested conversation cannot be loaded."""


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def list_conversation_evaluations(
    services: InstanceOf[BackendServices],
    *,
    project_path: str,
    session_id: str,
) -> list[ConversationEvaluationResponse]:
    """Return persisted evaluations for one conversation, newest first."""
    conversation_id = _conversation_id_for(project_path, session_id)
    records = services.app_sqlite_store.list_conversation_evaluations(conversation_id)
    return [_to_response(record) for record in records]


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def create_conversation_evaluation(
    services: InstanceOf[BackendServices],
    *,
    project_path: str,
    session_id: str,
    body: ConversationEvaluationCreateRequest,
) -> ConversationEvaluationResponse:
    """Create a persisted evaluation job and submit it to the runner."""
    if services.evaluation_job_runner is None:
        raise RuntimeError("Evaluation job runner is unavailable.")

    conversation = get_conversation(
        services,
        project_path=project_path,
        session_id=session_id,
    )
    if conversation is None:
        raise ConversationEvaluationConversationNotFoundError("Conversation not found.")

    prompt_id, prompt_name, prompt_text = _resolve_prompt_content(services, body)
    workspace = _resolve_workspace(services, project_path)
    job_request = EvaluationJobRequest(
        evaluation_id=f"pending-{session_id}",
        provider=body.provider,
        model=body.model,
        workspace=workspace,
        prompt=_build_evaluation_prompt(
            conversation,
            scope=body.scope,
            prompt_text=prompt_text,
            selection_instruction=body.selection_instruction,
        ),
    )
    command = services.evaluation_job_runner.describe_command(job_request)
    record = services.app_sqlite_store.create_conversation_evaluation(
        conversation_id=_conversation_id_for(project_path, session_id),
        provider=body.provider,
        model=body.model,
        status="running",
        scope=body.scope,
        prompt_id=prompt_id,
        prompt_name=prompt_name,
        prompt_text=prompt_text,
        selection_instruction=body.selection_instruction,
        command=command,
    )
    submitted_request = EvaluationJobRequest(
        evaluation_id=record.evaluation_id,
        provider=job_request.provider,
        model=job_request.model,
        workspace=job_request.workspace,
        prompt=job_request.prompt,
        timeout_seconds=job_request.timeout_seconds,
    )
    try:
        services.evaluation_job_runner.submit(
            submitted_request,
            lambda result: _persist_job_result(services, result),
        )
    except Exception as error:
        services.app_sqlite_store.update_conversation_evaluation(
            record.evaluation_id,
            status="failed",
            command=command,
            report_markdown=None,
            raw_output=None,
            error_message=str(error) or "Failed to submit evaluation job.",
            finished_at=_now_iso(),
            duration_ms=0,
        )
        raise RuntimeError("Failed to start evaluation job.") from error

    return _to_response(record)


def _persist_job_result(services: BackendServices, result: EvaluationJobResult) -> None:
    services.app_sqlite_store.update_conversation_evaluation(
        result.evaluation_id,
        status=result.status,
        command=result.command,
        report_markdown=result.report_markdown,
        raw_output=result.raw_output,
        error_message=result.error_message,
        finished_at=result.finished_at,
        duration_ms=result.duration_ms,
    )


def _resolve_prompt_content(
    services: BackendServices,
    body: ConversationEvaluationCreateRequest,
) -> tuple[str | None, str, str]:
    if body.prompt_id is not None:
        prompt = resolve_evaluation_prompt(services, prompt_id=body.prompt_id)
        return prompt.prompt_id, prompt.name, prompt.prompt_text

    if body.prompt_name and body.prompt_text:
        return None, body.prompt_name, body.prompt_text

    prompt = resolve_evaluation_prompt(services)
    return prompt.prompt_id, prompt.name, prompt.prompt_text


def _build_evaluation_prompt(
    conversation: ConversationDetailResponse,
    *,
    scope: str,
    prompt_text: str,
    selection_instruction: str | None,
) -> str:
    scope_label = {
        "full": "the full conversation",
        "failed_tool_calls": "only failed tool calls and their nearby context",
        "guided_subset": "a guided subset of the conversation",
    }[scope]
    selection_block = ""
    if scope == "guided_subset" and selection_instruction:
        selection_block = (
            "Before writing the report, first isolate only the messages that match this analyst instruction:\n"
            f"{selection_instruction}\n\nThen base the report on that subset."
        )
    return "\n\n".join(
        part
        for part in [
            "You are evaluating a coding-assistant conversation for quality, instruction design, and flow.",
            "Do not edit files or run commands. Analyze only the provided transcript.",
            f"The transcript below contains {scope_label}.",
            prompt_text.strip(),
            selection_block,
            "Conversation metadata:",
            f"- model: {conversation.model or 'unknown'}",
            f"- message count: {len(conversation.messages)}",
            f"- sub-agent count: {len(conversation.subagents)}",
            f"- started at: {_isoformat_epoch_ms(conversation.start_time)}",
            "",
            "Transcript:",
            _render_conversation_transcript(conversation, scope=scope),
        ]
        if part
    )


def _render_conversation_transcript(conversation: ConversationDetailResponse, *, scope: str) -> str:
    if scope == "failed_tool_calls":
        segments: list[str] = []
        for index, message in enumerate(conversation.messages):
            has_failure = any(block.type == "tool_call" and block.is_error for block in message.blocks)
            if not has_failure:
                continue
            for contextual_message in conversation.messages[max(0, index - 1) : index + 1]:
                segments.append(_render_message(contextual_message))
        if not segments:
            return "No failed tool calls were captured for this conversation."
        return "\n\n---\n\n".join(segments)

    return "\n\n---\n\n".join(_render_message(message) for message in conversation.messages)


def _render_message(message: object) -> str:
    blocks = getattr(message, "blocks", [])
    return "\n".join(
        [
            f"message_id: {getattr(message, 'id')}",
            f"role: {getattr(message, 'role')}",
            f"timestamp: {_isoformat_epoch_ms(getattr(message, 'timestamp'))}",
            "\n\n".join(_format_block(block) for block in blocks),
        ]
    )


def _format_block(block: ConversationMessageBlockResponse) -> str:
    if block.type == "text":
        return f"message text:\n{block.text or ''}"
    if block.type == "thinking":
        return f"message thinking:\n{block.thinking or ''}"

    tool_input = block.input.root
    parts = [
        f"message tool call: {block.tool_name or 'unknown'}",
        f"input: {json.dumps(tool_input, indent=2)}",
        f"result:\n{block.result}" if block.result else None,
        "status: failed" if block.is_error else "status: succeeded",
    ]
    return "\n".join(part for part in parts if part)


def _resolve_workspace(services: BackendServices, project_path: str) -> Path:
    """Resolve a filesystem workspace for the given `project_path`.

    Preference order:
    1) If the configured project root exists, prefer it. This keeps evaluation
       jobs scoped to the active backend workspace or test fixture.
    2) Otherwise, if the current working directory is inside the decoded
       project path, use the CWD. This supports running within a git worktree
       while the project path points at the repository root.
    3) Otherwise, if the decoded path exists on disk, use it.
    4) Fallback to the configured `settings.project_root`.
    """
    encoded = project_path
    if encoded.startswith("codex:"):
        encoded = encoded[len("codex:") :]
    if encoded.startswith("-"):
        decoded = Path("/" + encoded.lstrip("-").replace("-", "/"))
    else:
        decoded = Path.home() / encoded

    configured_root = services.settings.project_root.resolve()
    if configured_root.exists():
        return configured_root

    try:
        cwd = Path.cwd().resolve()
        decoded_resolved = decoded.resolve()
        # If running inside a worktree or subdirectory of the decoded path,
        # prefer the active working directory for better locality when there is
        # no explicit project_root override.
        if cwd.is_relative_to(decoded_resolved):
            return cwd
    except Exception:
        # If resolution fails for any reason, fall back to the next options.
        pass

    if decoded.exists():
        return decoded
    return services.settings.project_root


def _conversation_id_for(project_path: str, session_id: str) -> str:
    provider = "codex" if project_path.startswith("codex:") else "claude"
    return f"{provider}:{session_id}"


def _isoformat_epoch_ms(timestamp_ms: float) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).isoformat()


def _to_response(record: object) -> ConversationEvaluationResponse:
    if hasattr(record, "model_dump"):
        return ConversationEvaluationResponse.model_validate(record.model_dump(mode="python"))
    return ConversationEvaluationResponse.model_validate(record)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
