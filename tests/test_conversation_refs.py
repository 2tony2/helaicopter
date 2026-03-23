from helaicopter_api.application.conversation_refs import (
    build_conversation_ref,
    parse_conversation_ref,
)
from helaicopter_api.application.conversations import _merge_summary
from helaicopter_api.schema.conversations import ConversationSummaryResponse


def _summary(*, project_path: str, session_id: str, conversation_ref: str) -> ConversationSummaryResponse:
    return ConversationSummaryResponse(
        session_id=session_id,
        project_path=project_path,
        project_name=project_path,
        route_slug="shared-session",
        conversation_ref=conversation_ref,
        thread_type="main",
        first_message="Shared session",
        timestamp=1,
        created_at=1,
        last_updated_at=1,
        is_running=False,
        model="openclaw-v1",
        provider="openclaw",
        token_counts={
            "input": 0,
            "output": 0,
            "cache_creation": 0,
            "cache_read": 0,
            "reasoning": 0,
        },
        cost_usd=0.0,
        message_count=1,
        tool_call_count=0,
        notes=[],
    )


def test_openclaw_conversation_refs_include_project_path_for_uniqueness() -> None:
    main_ref = build_conversation_ref(
        "shared-session",
        "openclaw",
        "shared-session-id",
        "openclaw:agent:main",
    )
    secondary_ref = build_conversation_ref(
        "shared-session",
        "openclaw",
        "shared-session-id",
        "openclaw:agent:secondary",
    )

    assert main_ref != secondary_ref
    assert parse_conversation_ref(main_ref).project_path == "openclaw:agent:main"
    assert parse_conversation_ref(secondary_ref).project_path == "openclaw:agent:secondary"


def test_openclaw_legacy_conversation_refs_still_parse() -> None:
    parsed = parse_conversation_ref("shared-session--openclaw-shared-session-id")

    assert parsed is not None
    assert parsed.provider == "openclaw"
    assert parsed.session_id == "shared-session-id"
    assert parsed.project_path is None


def test_merge_summary_keeps_openclaw_sessions_separate_per_project_path() -> None:
    summaries: dict[tuple[str, str], ConversationSummaryResponse] = {}
    _merge_summary(
        summaries,
        _summary(
            project_path="openclaw:agent:main",
            session_id="shared-session-id",
            conversation_ref=build_conversation_ref(
                "shared-session",
                "openclaw",
                "shared-session-id",
                "openclaw:agent:main",
            ),
        ),
    )
    _merge_summary(
        summaries,
        _summary(
            project_path="openclaw:agent:secondary",
            session_id="shared-session-id",
            conversation_ref=build_conversation_ref(
                "shared-session",
                "openclaw",
                "shared-session-id",
                "openclaw:agent:secondary",
            ),
        ),
    )
    assert len(summaries) == 2
    assert summaries[0].conversation_ref != summaries[1].conversation_ref
