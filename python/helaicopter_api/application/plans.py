"""Application-layer plan loading and shaping."""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from typing import Any, Literal, TypedDict, cast

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.claude_fs import RawConversationEvent, SessionInfo
from helaicopter_api.ports.codex_sqlite import CodexThreadRecord
from helaicopter_api.schema.plans import (
    PlanDetailResponse,
    PlanStepResponse,
    PlanSummaryResponse,
)


class FilePlanSource(TypedDict):
    kind: Literal["file"]
    slug: str


class ClaudeSessionPlanSource(TypedDict):
    kind: Literal["claude-session"]
    projectPath: str
    sessionId: str
    eventId: str


class CodexSessionPlanSource(TypedDict):
    kind: Literal["codex-session"]
    sessionId: str
    callId: str


PlanSource = FilePlanSource | ClaudeSessionPlanSource | CodexSessionPlanSource


def list_plans(services: BackendServices) -> list[PlanSummaryResponse]:
    """Return file-backed Claude plans plus session-backed Claude/Codex plans."""
    claude_session_plans = _list_claude_session_plans(services)
    codex_session_plans = _list_codex_session_plans(services)
    file_plans = _list_claude_file_plans(services)
    return sorted(
        [*claude_session_plans, *codex_session_plans, *file_plans],
        key=lambda plan: (-plan.timestamp, plan.title.lower()),
    )


def get_plan(services: BackendServices, plan_id: str) -> PlanDetailResponse | None:
    """Return one plan by encoded id or legacy Claude file slug."""
    source = _decode_plan_id(plan_id)
    if source is None:
        return None

    kind = source["kind"]
    if kind == "file":
        return _get_claude_file_plan(services, source["slug"], plan_id)
    if kind == "claude-session":
        return _get_claude_session_plan(
            services,
            project_path=source["projectPath"],
            session_id=source["sessionId"],
            event_id=source["eventId"],
        )
    return _get_codex_session_plan(
        services,
        session_id=source["sessionId"],
        call_id=source["callId"],
    )


def _list_claude_file_plans(services: BackendServices) -> list[PlanSummaryResponse]:
    plans: list[PlanSummaryResponse] = []
    for plan_file in services.claude_plan_reader.list_plans():
        metadata = _summarize_plan_content(plan_file.content, plan_file.slug)
        plans.append(
            PlanSummaryResponse(
                id=_encode_plan_id({"kind": "file", "slug": plan_file.slug}),
                slug=metadata["slug"],
                title=metadata["title"],
                preview=metadata["preview"],
                provider="claude",
                timestamp=plan_file.modified_at * 1000,
                source_path=plan_file.path,
            )
        )
    return plans


def _get_claude_file_plan(
    services: BackendServices,
    slug: str,
    plan_id: str,
) -> PlanDetailResponse | None:
    plan_file = services.claude_plan_reader.read_plan(slug)
    if plan_file is None:
        return None
    metadata = _summarize_plan_content(plan_file.content, slug)
    return PlanDetailResponse(
        id=plan_id,
        slug=metadata["slug"],
        title=metadata["title"],
        content=plan_file.content,
        provider="claude",
        timestamp=plan_file.modified_at * 1000,
        source_path=plan_file.path,
    )


def _list_claude_session_plans(services: BackendServices) -> list[PlanSummaryResponse]:
    plans: list[PlanSummaryResponse] = []
    for project in services.claude_conversation_reader.list_projects():
        for session in services.claude_conversation_reader.list_sessions(project.dir_name):
            events = services.claude_conversation_reader.read_session_events(
                project.dir_name,
                session.session_id,
            )
            plans.extend(
                _extract_claude_session_plans(
                    events,
                    session_id=session.session_id,
                    project_path=project.dir_name,
                    source_path=session.path,
                )
            )
    return plans


def _get_claude_session_plan(
    services: BackendServices,
    *,
    project_path: str,
    session_id: str,
    event_id: str,
) -> PlanDetailResponse | None:
    events = services.claude_conversation_reader.read_session_events(project_path, session_id)
    if not events:
        return None
    source_path = _session_source_path(services, project_path, session_id)
    for event in _extract_claude_session_details(
        events,
        session_id=session_id,
        project_path=project_path,
        source_path=source_path,
    ):
        if event.id == _encode_plan_id(
            {
                "kind": "claude-session",
                "projectPath": project_path,
                "sessionId": session_id,
                "eventId": event_id,
            }
        ):
            return event
    return None


def _extract_claude_session_plans(
    events: list[RawConversationEvent],
    *,
    session_id: str,
    project_path: str,
    source_path: str,
) -> list[PlanSummaryResponse]:
    return [
        PlanSummaryResponse(
            id=plan.id,
            slug=plan.slug,
            title=plan.title,
            preview=_summarize_plan_content(plan.content, plan.slug)["preview"],
            provider=plan.provider,
            timestamp=plan.timestamp,
            model=plan.model,
            source_path=plan.source_path,
            session_id=plan.session_id,
            project_path=plan.project_path,
        )
        for plan in _extract_claude_session_details(
            events,
            session_id=session_id,
            project_path=project_path,
            source_path=source_path,
        )
    ]


def _extract_claude_session_details(
    events: list[RawConversationEvent],
    *,
    session_id: str,
    project_path: str,
    source_path: str,
) -> list[PlanDetailResponse]:
    plans: list[PlanDetailResponse] = []
    latest_model: str | None = None

    for event in events:
        latest_model = _claude_event_model(event) or latest_model
        content = event.plan_content
        if not isinstance(content, str) or not content.strip():
            continue
        event_id = event.uuid.strip()
        if not event_id:
            continue
        metadata = _summarize_plan_content(content, event.slug or session_id)
        plans.append(
            PlanDetailResponse(
                id=_encode_plan_id(
                    {
                        "kind": "claude-session",
                        "projectPath": project_path,
                        "sessionId": session_id,
                        "eventId": event_id,
                    }
                ),
                slug=metadata["slug"],
                title=metadata["title"],
                content=content,
                provider="claude",
                timestamp=_to_epoch_ms(event.timestamp),
                model=latest_model,
                source_path=source_path,
                session_id=session_id,
                project_path=project_path,
            )
        )

    return sorted(plans, key=lambda plan: -plan.timestamp)


def _list_codex_session_plans(services: BackendServices) -> list[PlanSummaryResponse]:
    thread_by_id = {thread.id: thread for thread in services.codex_store.list_threads()}
    plans: list[PlanSummaryResponse] = []
    for artifact in services.codex_store.list_session_artifacts():
        lines = _parse_codex_lines(artifact.content)
        project_path = _codex_project_path(lines, thread_by_id.get(artifact.session_id))
        plans.extend(
            _extract_codex_session_plans(
                lines,
                session_id=artifact.session_id,
                project_path=project_path,
                source_path=artifact.path,
            )
        )
    return plans


def _get_codex_session_plan(
    services: BackendServices,
    *,
    session_id: str,
    call_id: str,
) -> PlanDetailResponse | None:
    artifact = services.codex_store.read_session_artifact(session_id)
    if artifact is None:
        return None
    thread = services.codex_store.get_thread(session_id)
    lines = _parse_codex_lines(artifact.content)
    project_path = _codex_project_path(lines, thread)
    for plan in _extract_codex_session_details(
        lines,
        session_id=session_id,
        project_path=project_path,
        source_path=artifact.path,
    ):
        if plan.id == _encode_plan_id(
            {
                "kind": "codex-session",
                "sessionId": session_id,
                "callId": call_id,
            }
        ):
            return plan
    return None


def _extract_codex_session_plans(
    lines: list[dict[str, Any]],
    *,
    session_id: str,
    project_path: str,
    source_path: str,
) -> list[PlanSummaryResponse]:
    return [
        PlanSummaryResponse(
            id=plan.id,
            slug=plan.slug,
            title=plan.title,
            preview=_summarize_plan_content(plan.content, plan.slug)["preview"],
            provider=plan.provider,
            timestamp=plan.timestamp,
            model=plan.model,
            source_path=plan.source_path,
            session_id=plan.session_id,
            project_path=plan.project_path,
        )
        for plan in _extract_codex_session_details(
            lines,
            session_id=session_id,
            project_path=project_path,
            source_path=source_path,
        )
    ]


def _extract_codex_session_details(
    lines: list[dict[str, Any]],
    *,
    session_id: str,
    project_path: str,
    source_path: str,
) -> list[PlanDetailResponse]:
    plans: list[PlanDetailResponse] = []
    latest_model: str | None = None

    for line in lines:
        if line.get("type") == "turn_context":
            payload = cast(dict[str, Any], line.get("payload") or {})
            model = payload.get("model")
            if isinstance(model, str) and model.strip():
                latest_model = model.strip()
            continue

        if line.get("type") != "response_item":
            continue

        payload = cast(dict[str, Any], line.get("payload") or {})
        if payload.get("type") != "function_call" or payload.get("name") != "update_plan":
            continue

        call_id = payload.get("call_id")
        if not isinstance(call_id, str) or not call_id.strip():
            continue

        args = _parse_json_mapping(payload.get("arguments"))
        explanation = _parse_codex_explanation(args)
        steps = _parse_codex_plan_steps(args.get("plan"))
        if explanation is None and not steps:
            continue

        slug, title, content = _summarize_codex_plan(call_id, explanation, steps)
        plans.append(
            PlanDetailResponse(
                id=_encode_plan_id(
                    {
                        "kind": "codex-session",
                        "sessionId": session_id,
                        "callId": call_id,
                    }
                ),
                slug=slug,
                title=title,
                content=content,
                provider="codex",
                timestamp=_to_epoch_ms(line.get("timestamp")),
                model=latest_model,
                source_path=source_path,
                session_id=session_id,
                project_path=project_path,
                explanation=explanation,
                steps=steps,
            )
        )

    return sorted(plans, key=lambda plan: -plan.timestamp)


def _session_source_path(
    services: BackendServices,
    project_path: str,
    session_id: str,
) -> str | None:
    sessions = services.claude_conversation_reader.list_sessions(project_path)
    for session in sessions:
        if session.session_id == session_id:
            return session.path
    return None


def _claude_event_model(event: RawConversationEvent) -> str | None:
    if event.type != "assistant":
        return None
    message = event.message
    if not isinstance(message, dict):
        return None
    model = message.get("model")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return None


def _summarize_codex_plan(
    call_id: str,
    explanation: str | None,
    steps: list[PlanStepResponse],
) -> tuple[str, str, str]:
    title_source = _first_non_empty_line(explanation) or (
        steps[0].step if steps else f"Plan update {call_id[-8:]}"
    )
    title = _truncate(title_source.strip(), max_length=80)
    slug = f"codex-{_slugify(title)}-{call_id[-8:]}"

    content_lines = [f"# {title}"]
    if explanation:
        content_lines.extend(["", explanation])
    if steps:
        content_lines.extend(["", "## Steps", ""])
        for step in steps:
            content_lines.append(f"{_checkbox_for_status(step.status)} {step.step}")
    return slug, title, "\n".join(content_lines)


def _parse_codex_explanation(payload: dict[str, Any]) -> str | None:
    explanation = payload.get("explanation")
    if isinstance(explanation, str) and explanation.strip():
        return explanation.strip()
    return None


def _parse_codex_plan_steps(raw_plan: object) -> list[PlanStepResponse]:
    if not isinstance(raw_plan, list):
        return []

    steps: list[PlanStepResponse] = []
    for item in raw_plan:
        if not isinstance(item, dict):
            continue
        step = item.get("step")
        if not isinstance(step, str) or not step.strip():
            continue
        status = item.get("status")
        normalized_status = status.strip() if isinstance(status, str) and status.strip() else "pending"
        steps.append(PlanStepResponse(step=step.strip(), status=normalized_status))
    return steps


def _codex_project_path(
    lines: list[dict[str, Any]],
    thread: CodexThreadRecord | None,
) -> str:
    for line in lines:
        if line.get("type") != "session_meta":
            continue
        payload = cast(dict[str, Any], line.get("payload") or {})
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd.strip():
            return f"codex:{_cwd_to_project_path(cwd.strip())}"
    if thread is not None and isinstance(thread.cwd, str) and thread.cwd.strip():
        return f"codex:{_cwd_to_project_path(thread.cwd.strip())}"
    return "codex:unknown"


def _parse_codex_lines(content: str) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            lines.append(parsed)
    return lines


def _parse_json_mapping(raw_value: object) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if not isinstance(raw_value, str) or not raw_value.strip():
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _summarize_plan_content(content: str, fallback_slug: str) -> dict[str, str]:
    lines = [line for line in content.splitlines() if line.strip()]
    title = next(
        (
            line.replace("# ", "", 1).strip()
            for line in lines
            if line.startswith("# ")
        ),
        fallback_slug,
    )
    preview = " ".join(line for line in lines if not line.startswith("#"))[:200]
    return {"slug": fallback_slug, "title": title, "preview": preview}


def _encode_plan_id(source: PlanSource) -> str:
    payload = json.dumps(source, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def _decode_plan_id(plan_id: str) -> PlanSource | None:
    try:
        padding = "=" * (-len(plan_id) % 4)
        decoded = base64.urlsafe_b64decode(f"{plan_id}{padding}".encode("utf-8")).decode("utf-8")
        parsed = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        parsed = None

    if isinstance(parsed, dict):
        kind = parsed.get("kind")
        if kind == "file" and isinstance(parsed.get("slug"), str):
            return cast(FilePlanSource, {"kind": "file", "slug": parsed["slug"]})
        if (
            kind == "claude-session"
            and isinstance(parsed.get("projectPath"), str)
            and isinstance(parsed.get("sessionId"), str)
            and isinstance(parsed.get("eventId"), str)
        ):
            return cast(
                ClaudeSessionPlanSource,
                {
                    "kind": "claude-session",
                    "projectPath": parsed["projectPath"],
                    "sessionId": parsed["sessionId"],
                    "eventId": parsed["eventId"],
                },
            )
        if (
            kind == "codex-session"
            and isinstance(parsed.get("sessionId"), str)
            and isinstance(parsed.get("callId"), str)
        ):
            return cast(
                CodexSessionPlanSource,
                {
                    "kind": "codex-session",
                    "sessionId": parsed["sessionId"],
                    "callId": parsed["callId"],
                },
            )

    if plan_id:
        return {"kind": "file", "slug": plan_id}
    return None


def _to_epoch_ms(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        try:
            return datetime.fromisoformat(stripped.replace("Z", "+00:00")).timestamp() * 1000
        except ValueError:
            try:
                return float(stripped)
            except ValueError:
                return 0
    return 0


def _cwd_to_project_path(cwd: str) -> str:
    return cwd.replace("/", "-") if cwd else "unknown"


def _first_non_empty_line(value: str | None) -> str | None:
    if value is None:
        return None
    for line in value.splitlines():
        if line.strip():
            return line.strip()
    return None


def _truncate(value: str, *, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3].rstrip()}..."


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "plan"


def _checkbox_for_status(status: str) -> str:
    if status == "completed":
        return "[x]"
    if status == "in_progress":
        return "[-]"
    return "[ ]"
