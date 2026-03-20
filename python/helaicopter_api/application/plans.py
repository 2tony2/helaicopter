"""Application-layer plan loading and shaping."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypedDict, cast

from pydantic import ConfigDict, InstanceOf, TypeAdapter, ValidationError, validate_call
from helaicopter_domain.ids import PlanId, SessionId
from helaicopter_domain.paths import EncodedProjectKey
from helaicopter_domain.vocab import ProviderName

from helaicopter_api.application.codex_payloads import (
    CodexSessionLine,
    parse_codex_session_lines,
    parse_codex_update_plan_arguments,
    payload_for_line,
)
from helaicopter_api.application.conversation_refs import (
    ConversationRouteTarget,
    build_conversation_route_target,
    derive_route_slug,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.contracts.plans import (
    PlanDetailResponse,
    PlanStepResponse,
    PlanSummaryResponse,
)
from helaicopter_api.domain import plans as plan_domain
from helaicopter_api.ports.claude_fs import RawConversationEvent
from helaicopter_api.ports.app_sqlite import HistoricalPlanSummary
from helaicopter_api.ports.codex_sqlite import CodexThreadRecord


class FilePlanSource(TypedDict):
    kind: Literal["file"]
    slug: str


class ClaudeSessionPlanSource(TypedDict):
    kind: Literal["claude-session"]
    projectPath: EncodedProjectKey
    sessionId: SessionId
    eventId: str


class CodexSessionPlanSource(TypedDict):
    kind: Literal["codex-session"]
    sessionId: SessionId
    callId: str


PlanSource = FilePlanSource | ClaudeSessionPlanSource | CodexSessionPlanSource
_PLAN_SOURCE_ADAPTER = TypeAdapter(PlanSource)
_CACHE_MISS = object()


@dataclass(frozen=True, slots=True)
class _ExtractedPlan:
    id: PlanId
    slug: str
    title: str
    preview: str
    content: str
    provider: ProviderName
    timestamp: float
    model: str | None = None
    source_path: str | None = None
    session_id: SessionId | None = None
    project_path: EncodedProjectKey | None = None
    route_slug: str | None = None
    conversation_ref: str | None = None
    explanation: str | None = None
    steps: list[plan_domain.PlanStepData] | None = None


def _historical_conversation_route_targets(
    services: BackendServices,
) -> dict[tuple[str, SessionId], ConversationRouteTarget]:
    return {
        (summary.provider, summary.session_id): build_conversation_route_target(
            summary.route_slug,
            summary.provider,
            summary.session_id,
        )
        for summary in services.app_sqlite_store.list_historical_conversations()
    }


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def list_plans(services: InstanceOf[BackendServices]) -> list[PlanSummaryResponse]:
    """Return file-backed Claude plans plus session-backed Claude/Codex plans.

    Prefers SQLite-persisted historical plan summaries when available. Falls
    back to scanning live Claude filesystem sessions and Codex SQLite artifacts.
    Results are sorted newest-first and cached on ``services.cache``.

    Args:
        services: Initialised backend services providing the plan reader,
            conversation reader, Codex store, and SQLite store.

    Returns:
        List of ``PlanSummaryResponse`` objects sorted by descending timestamp,
        then alphabetically by title.
    """
    cached = services.cache.get("plans", _CACHE_MISS)
    if isinstance(cached, list):
        return cached

    file_plans = _list_claude_file_plans(services)
    historical_plan_summaries = services.app_sqlite_store.list_historical_plan_summaries()

    if historical_plan_summaries:
        plans = sorted(
            [
                *_historical_plan_summary_responses(historical_plan_summaries),
                *file_plans,
            ],
            key=lambda plan: (-plan.timestamp, plan.title.lower()),
        )
    else:
        route_targets = _historical_conversation_route_targets(services)
        claude_session_plans = _list_claude_session_plans(services, route_targets=route_targets)
        codex_session_plans = _list_codex_session_plans(services, route_targets=route_targets)
        plans = sorted(
            [*claude_session_plans, *codex_session_plans, *file_plans],
            key=lambda plan: (-plan.timestamp, plan.title.lower()),
        )
    services.cache.set("plans", plans)
    return plans


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def get_plan(services: InstanceOf[BackendServices], plan_id: str) -> PlanDetailResponse | None:
    """Return one plan by encoded id or legacy Claude file slug.

    Decodes the ``plan_id`` to determine its source kind (file, Claude session,
    or Codex session), loads the matching artifact, and returns a full detail
    response. Results are cached on ``services.cache``.

    Args:
        services: Initialised backend services providing the plan reader,
            conversation reader, and Codex store.
        plan_id: Base64url-encoded plan source descriptor, or a legacy Claude
            plan file slug.

    Returns:
        A ``PlanDetailResponse`` when the plan is found, otherwise ``None``.
    """
    cache_key = f"plan:{plan_id}"
    cached = services.cache.get(cache_key, _CACHE_MISS)
    if cached is None or isinstance(cached, PlanDetailResponse):
        return cached

    source = _decode_plan_id(plan_id)
    if source is None:
        return None
    route_targets = _historical_conversation_route_targets(services)

    kind = source["kind"]
    if kind == "file":
        file_source = cast(FilePlanSource, source)
        plan = _get_claude_file_plan(services, file_source["slug"], plan_id)
    elif kind == "claude-session":
        claude_source = cast(ClaudeSessionPlanSource, source)
        plan = _get_claude_session_plan(
            services,
            project_path=claude_source["projectPath"],
            session_id=claude_source["sessionId"],
            event_id=claude_source["eventId"],
            route_targets=route_targets,
        )
    else:
        codex_source = cast(CodexSessionPlanSource, source)
        plan = _get_codex_session_plan(
            services,
            session_id=codex_source["sessionId"],
            call_id=codex_source["callId"],
            route_targets=route_targets,
        )

    services.cache.set(cache_key, plan)
    return plan


def _session_route_target(
    route_targets: dict[tuple[str, SessionId], ConversationRouteTarget],
    *,
    provider: str,
    session_id: SessionId,
    first_message: str,
) -> ConversationRouteTarget | None:
    existing = route_targets.get((provider, session_id))
    if existing is not None:
        return existing
    if not session_id:
        return None
    return build_conversation_route_target(derive_route_slug(first_message), provider, session_id)


def _first_claude_user_message(events: list[RawConversationEvent]) -> str:
    for event in events:
        if event.type != "user" or event.message is None:
            continue
        message = event.message.root
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                    return block["text"][:200]
        if isinstance(content, str) and content:
            return content[:200]
    return ""


def _first_codex_user_message(lines: list[CodexSessionLine], thread: CodexThreadRecord | None) -> str:
    if thread is not None and isinstance(thread.first_user_message, str) and thread.first_user_message.strip():
        return thread.first_user_message[:200]
    for line in lines:
        if line.get("type") != "response_item":
            continue
        payload = payload_for_line(line)
        if payload.get("type") != "message" or payload.get("role") != "user":
            continue
        content = payload.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "input_text":
                continue
            text = block.get("text")
            if isinstance(text, str) and text and not text.startswith("<"):
                return text[:200]
    return ""


def _list_claude_file_plans(services: BackendServices) -> list[PlanSummaryResponse]:
    plans: list[PlanSummaryResponse] = []
    for plan_file in services.claude_plan_reader.list_plans():
        metadata = plan_domain.summarize_plan_content(plan_file.content, plan_file.slug)
        plans.append(
            PlanSummaryResponse(
                id=PlanId(_encode_plan_id({"kind": "file", "slug": plan_file.slug})),
                slug=metadata.slug,
                title=metadata.title,
                preview=metadata.preview,
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
    metadata = plan_domain.summarize_plan_content(plan_file.content, slug)
    return PlanDetailResponse(
        id=PlanId(plan_id),
        slug=metadata.slug,
        title=metadata.title,
        content=plan_file.content,
        provider="claude",
        timestamp=plan_file.modified_at * 1000,
        source_path=plan_file.path,
    )


def _list_claude_session_plans(
    services: BackendServices,
    *,
    route_targets: dict[tuple[str, SessionId], ConversationRouteTarget],
) -> list[PlanSummaryResponse]:
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
                    route_targets=route_targets,
                )
            )
    return plans


def _get_claude_session_plan(
    services: BackendServices,
    *,
    project_path: EncodedProjectKey,
    session_id: SessionId,
    event_id: str,
    route_targets: dict[tuple[str, SessionId], ConversationRouteTarget],
) -> PlanDetailResponse | None:
    events = services.claude_conversation_reader.read_session_events(project_path, session_id)
    if not events:
        return None
    source_path = _session_source_path(services, project_path, session_id)
    for event in _extract_claude_session_plan_data(
        events,
        session_id=session_id,
        project_path=project_path,
        source_path=source_path,
        route_targets=route_targets,
    ):
        if event.id == _encode_plan_id(
            {
                "kind": "claude-session",
                "projectPath": project_path,
                "sessionId": session_id,
                "eventId": event_id,
            }
        ):
            return _plan_detail_response(event)
    return None


def _extract_claude_session_plans(
    events: list[RawConversationEvent],
    *,
    session_id: SessionId,
    project_path: EncodedProjectKey,
    source_path: str | None,
    route_targets: dict[tuple[str, SessionId], ConversationRouteTarget],
) -> list[PlanSummaryResponse]:
    return [
        _plan_summary_response(plan)
        for plan in _extract_claude_session_plan_data(
            events,
            session_id=session_id,
            project_path=project_path,
            source_path=source_path,
            route_targets=route_targets,
        )
    ]


def _extract_claude_session_details(
    events: list[RawConversationEvent],
    *,
    session_id: SessionId,
    project_path: EncodedProjectKey,
    source_path: str | None,
    route_targets: dict[tuple[str, SessionId], ConversationRouteTarget],
) -> list[PlanDetailResponse]:
    return [
        _plan_detail_response(plan)
        for plan in _extract_claude_session_plan_data(
            events,
            session_id=session_id,
            project_path=project_path,
            source_path=source_path,
            route_targets=route_targets,
        )
    ]


def _extract_claude_session_plan_data(
    events: list[RawConversationEvent],
    *,
    session_id: SessionId,
    project_path: EncodedProjectKey,
    source_path: str | None,
    route_targets: dict[tuple[str, SessionId], ConversationRouteTarget],
) -> list[_ExtractedPlan]:
    plans: list[_ExtractedPlan] = []
    latest_model: str | None = None
    route_target = _session_route_target(
        route_targets,
        provider="claude",
        session_id=session_id,
        first_message=_first_claude_user_message(events),
    )

    for event in events:
        latest_model = _claude_event_model(event) or latest_model
        content = event.plan_content
        if not isinstance(content, str) or not content.strip():
            continue
        event_id = event.uuid.strip()
        if not event_id:
            continue
        metadata = plan_domain.summarize_plan_content(content, event.slug or session_id)
        plans.append(
            _ExtractedPlan(
                id=_encode_plan_id(
                    {
                        "kind": "claude-session",
                        "projectPath": project_path,
                        "sessionId": session_id,
                        "eventId": event_id,
                    }
                ),
                slug=metadata.slug,
                title=metadata.title,
                content=content,
                provider="claude",
                timestamp=_to_epoch_ms(event.timestamp),
                model=latest_model,
                source_path=source_path,
                session_id=session_id,
                project_path=project_path,
                route_slug=route_target.route_slug if route_target is not None else None,
                conversation_ref=route_target.conversation_ref if route_target is not None else None,
                preview=metadata.preview,
            )
        )

    return sorted(plans, key=lambda plan: -plan.timestamp)


def _list_codex_session_plans(
    services: BackendServices,
    *,
    route_targets: dict[tuple[str, SessionId], ConversationRouteTarget],
) -> list[PlanSummaryResponse]:
    thread_by_id = {thread.id: thread for thread in services.codex_store.list_threads()}
    plans: list[PlanSummaryResponse] = []
    for artifact in services.codex_store.list_session_artifacts():
        lines = _parse_codex_lines(artifact.content)
        project_path = _codex_project_path(lines, thread_by_id.get(artifact.session_id))
        session_id = SessionId(artifact.session_id)
        route_target = _session_route_target(
            route_targets,
            provider="codex",
            session_id=session_id,
            first_message=_first_codex_user_message(lines, thread_by_id.get(artifact.session_id)),
        )
        plans.extend(
            _extract_codex_session_plans(
                lines,
                session_id=session_id,
                project_path=project_path,
                source_path=artifact.path,
                route_target=route_target,
            )
        )
    return plans


def _get_codex_session_plan(
    services: BackendServices,
    *,
    session_id: SessionId,
    call_id: str,
    route_targets: dict[tuple[str, SessionId], ConversationRouteTarget],
) -> PlanDetailResponse | None:
    artifact = services.codex_store.read_session_artifact(session_id)
    if artifact is None:
        return None
    thread = services.codex_store.get_thread(session_id)
    lines = _parse_codex_lines(artifact.content)
    project_path = _codex_project_path(lines, thread)
    route_target = _session_route_target(
        route_targets,
        provider="codex",
        session_id=session_id,
        first_message=_first_codex_user_message(lines, thread),
    )
    for plan in _extract_codex_session_plan_data(
        lines,
        session_id=session_id,
        project_path=project_path,
        source_path=artifact.path,
        route_target=route_target,
    ):
        if plan.id == _encode_plan_id(
            {
                "kind": "codex-session",
                "sessionId": session_id,
                "callId": call_id,
            }
        ):
            return _plan_detail_response(plan)
    return None


def _extract_codex_session_plans(
    lines: list[CodexSessionLine],
    *,
    session_id: SessionId,
    project_path: EncodedProjectKey,
    source_path: str,
    route_target: ConversationRouteTarget | None,
) -> list[PlanSummaryResponse]:
    return [
        _plan_summary_response(plan)
        for plan in _extract_codex_session_plan_data(
            lines,
            session_id=session_id,
            project_path=project_path,
            source_path=source_path,
            route_target=route_target,
        )
    ]


def _extract_codex_session_details(
    lines: list[CodexSessionLine],
    *,
    session_id: SessionId,
    project_path: EncodedProjectKey,
    source_path: str,
    route_target: ConversationRouteTarget | None,
) -> list[PlanDetailResponse]:
    return [
        _plan_detail_response(plan)
        for plan in _extract_codex_session_plan_data(
            lines,
            session_id=session_id,
            project_path=project_path,
            source_path=source_path,
            route_target=route_target,
        )
    ]


def _extract_codex_session_plan_data(
    lines: list[CodexSessionLine],
    *,
    session_id: SessionId,
    project_path: EncodedProjectKey,
    source_path: str,
    route_target: ConversationRouteTarget | None,
) -> list[_ExtractedPlan]:
    plans: list[_ExtractedPlan] = []
    latest_model: str | None = None

    for line in lines:
        if line.get("type") == "turn_context":
            payload = payload_for_line(line)
            model = payload.get("model")
            if isinstance(model, str) and model.strip():
                latest_model = model.strip()
            continue

        if line.get("type") != "response_item":
            continue

        payload = payload_for_line(line)
        if payload.get("type") != "function_call" or payload.get("name") != "update_plan":
            continue

        call_id = payload.get("call_id")
        if not isinstance(call_id, str) or not call_id.strip():
            continue

        args = parse_codex_update_plan_arguments(payload.get("arguments"))
        if args is None:
            continue
        explanation = plan_domain.parse_codex_explanation(args)
        steps = plan_domain.parse_codex_plan_steps(args.get("plan"))
        if explanation is None and not steps:
            continue

        summary = plan_domain.summarize_codex_plan(call_id, explanation, steps)
        plans.append(
            _ExtractedPlan(
                id=_encode_plan_id(
                    {
                        "kind": "codex-session",
                        "sessionId": session_id,
                        "callId": call_id,
                    }
                ),
                slug=summary.slug,
                title=summary.title,
                content=summary.content,
                provider="codex",
                timestamp=_to_epoch_ms(line.get("timestamp")),
                model=latest_model,
                source_path=source_path,
                session_id=session_id,
                project_path=project_path,
                route_slug=route_target.route_slug if route_target is not None else None,
                conversation_ref=route_target.conversation_ref if route_target is not None else None,
                preview=summary.preview,
                explanation=explanation,
                steps=steps,
            )
        )

    return sorted(plans, key=lambda plan: -plan.timestamp)


def _session_source_path(
    services: BackendServices,
    project_path: EncodedProjectKey,
    session_id: SessionId,
) -> str | None:
    sessions = services.claude_conversation_reader.list_sessions(project_path)
    for session in sessions:
        if session.session_id == session_id:
            return session.path
    return None


def _claude_event_model(event: RawConversationEvent) -> str | None:
    if event.type != "assistant":
        return None
    if event.message is None:
        return None
    message = event.message.root
    model = message.get("model")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return None


def _plan_summary_response(plan: _ExtractedPlan) -> PlanSummaryResponse:
    return PlanSummaryResponse(
        id=plan.id,
        slug=plan.slug,
        title=plan.title,
        preview=plan.preview,
        provider=plan.provider,
        timestamp=plan.timestamp,
        model=plan.model,
        source_path=plan.source_path,
        session_id=plan.session_id,
        project_path=plan.project_path,
        route_slug=plan.route_slug,
        conversation_ref=plan.conversation_ref,
    )


def _historical_plan_summary_responses(
    plans: list[HistoricalPlanSummary],
) -> list[PlanSummaryResponse]:
    return [
        PlanSummaryResponse(
            id=plan.plan_id,
            slug=plan.slug,
            title=plan.title,
            preview=plan.preview,
            provider=plan.provider,
            timestamp=_to_epoch_ms(plan.timestamp),
            model=plan.model,
            session_id=plan.session_id,
            project_path=plan.project_path,
            route_slug=plan.route_slug,
            conversation_ref=(
                build_conversation_route_target(
                    plan.route_slug,
                    plan.provider,
                    plan.session_id,
                ).conversation_ref
                if plan.route_slug and plan.session_id
                else None
            ),
        )
        for plan in plans
    ]


def _plan_detail_response(plan: _ExtractedPlan) -> PlanDetailResponse:
    return PlanDetailResponse(
        id=plan.id,
        slug=plan.slug,
        title=plan.title,
        content=plan.content,
        provider=plan.provider,
        timestamp=plan.timestamp,
        model=plan.model,
        source_path=plan.source_path,
        session_id=plan.session_id,
        project_path=plan.project_path,
        route_slug=plan.route_slug,
        conversation_ref=plan.conversation_ref,
        explanation=plan.explanation,
        steps=[
            PlanStepResponse(step=step.step, status=step.status)
            for step in (plan.steps or [])
        ],
    )


def _codex_project_path(
    lines: list[CodexSessionLine],
    thread: CodexThreadRecord | None,
) -> EncodedProjectKey:
    for line in lines:
        if line.get("type") != "session_meta":
            continue
        payload = payload_for_line(line)
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd.strip():
            return f"codex:{_cwd_to_project_path(cwd.strip())}"
    if thread is not None and isinstance(thread.cwd, str) and thread.cwd.strip():
        return f"codex:{_cwd_to_project_path(thread.cwd.strip())}"
    return "codex:unknown"


def _parse_codex_lines(content: str) -> list[CodexSessionLine]:
    return parse_codex_session_lines(content)


def _encode_plan_id(source: PlanSource) -> PlanId:
    payload = json.dumps(source, separators=(",", ":")).encode("utf-8")
    return PlanId(base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("="))


def _decode_plan_id(plan_id: str) -> PlanSource | None:
    try:
        padding = "=" * (-len(plan_id) % 4)
        decoded = base64.urlsafe_b64decode(f"{plan_id}{padding}".encode("utf-8")).decode("utf-8")
        parsed = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        parsed = None

    if parsed is not None:
        try:
            return _PLAN_SOURCE_ADAPTER.validate_python(parsed)
        except ValidationError:
            pass

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
