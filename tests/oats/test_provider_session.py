from __future__ import annotations

from oats.provider_session import ProviderSessionManager


def test_session_manager_starts_absent_and_transitions_to_ready_after_bootstrap() -> None:
    manager = ProviderSessionManager(provider="claude")

    assert manager.status == "absent"

    session = manager.ensure_session()

    assert manager.status == "ready"
    assert session is not None
    assert session.provider == "claude"


def test_session_manager_reset_discards_current_session_identity() -> None:
    manager = ProviderSessionManager(provider="codex")

    first = manager.ensure_session()
    manager.reset(reason="operator_requested")
    second = manager.ensure_session()

    assert first.session_id != second.session_id
    assert manager.failure_reason is None
