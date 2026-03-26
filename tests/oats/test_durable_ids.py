"""Tests for durable identity generation."""

from __future__ import annotations


def test_id_generation_uniqueness() -> None:
    """Generated IDs are unique and correctly prefixed."""
    from oats.identity import (
        generate_attempt_id,
        generate_operation_id,
        generate_run_id,
        generate_session_id,
    )

    run_ids = {generate_run_id() for _ in range(100)}
    assert len(run_ids) == 100
    assert all(rid.startswith("run_") for rid in run_ids)

    sess_ids = {generate_session_id() for _ in range(100)}
    assert len(sess_ids) == 100
    assert all(sid.startswith("sess_") for sid in sess_ids)

    att_ids = {generate_attempt_id() for _ in range(100)}
    assert len(att_ids) == 100
    assert all(aid.startswith("att_") for aid in att_ids)

    op_ids = {generate_operation_id() for _ in range(100)}
    assert len(op_ids) == 100
    assert all(oid.startswith("op_") for oid in op_ids)


def test_task_id_from_slug() -> None:
    """Task IDs from spec use slug format."""
    from oats.identity import task_id_from_slug

    assert task_id_from_slug("Auth Service Setup") == "task_auth-service-setup"
    assert task_id_from_slug("  Leading Spaces  ") == "task_leading-spaces"
    assert task_id_from_slug("Multiple   Spaces") == "task_multiple-spaces"
    assert task_id_from_slug("UPPERCASE") == "task_uppercase"
    assert task_id_from_slug("special!@#chars") == "task_specialchars"


def test_task_id_for_discovered() -> None:
    """Discovered task IDs use unique generated format."""
    from oats.identity import generate_discovered_task_id

    tid = generate_discovered_task_id()
    assert tid.startswith("task_")
    assert len(tid) > len("task_")

    # Uniqueness
    ids = {generate_discovered_task_id() for _ in range(100)}
    assert len(ids) == 100


def test_mutation_id_generation() -> None:
    """Mutation IDs are unique and correctly prefixed."""
    from oats.identity import generate_mutation_id

    ids = {generate_mutation_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(mid.startswith("mut_") for mid in ids)
