from __future__ import annotations

import pytest

from oats.provider_session import ProviderSessionManager


def test_session_manager_starts_absent_and_transitions_to_ready_after_bootstrap() -> None:
    manager = ProviderSessionManager(provider="claude", auth_validator=lambda: None)

    assert manager.status == "absent"

    session = manager.ensure_session()

    assert manager.status == "ready"
    assert session is not None
    assert session.provider == "claude"


def test_session_manager_reset_discards_current_session_identity() -> None:
    manager = ProviderSessionManager(provider="claude", auth_validator=lambda: None)

    first = manager.ensure_session()
    manager.reset(reason="operator_requested")
    second = manager.ensure_session()

    assert first.session_id != second.session_id
    assert manager.failure_reason is None


def test_claude_session_manager_fails_when_cli_auth_is_missing() -> None:
    manager = ProviderSessionManager(
        provider="claude",
        auth_validator=lambda: (_ for _ in ()).throw(RuntimeError("Claude CLI session is not authenticated.")),
    )

    with pytest.raises(RuntimeError, match="Claude CLI session is not authenticated"):
        manager.ensure_session()

    assert manager.status == "failed"


def test_codex_session_manager_stays_absent_until_first_real_thread_is_observed() -> None:
    manager = ProviderSessionManager(provider="codex", auth_validator=lambda: None)

    session = manager.ensure_session()

    assert session is None
    assert manager.status == "absent"

    manager.record_session("thread_123")

    assert manager.status == "ready"
    assert manager.session is not None
    assert manager.session.session_id == "thread_123"
