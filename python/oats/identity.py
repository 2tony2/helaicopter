"""Durable identity generation for the Oats graph runtime.

Every entity carries a stable, unique identifier with a typed prefix:
  run_<id>, task_<slug|id>, sess_<id>, att_<id>, op_<id>, mut_<id>

IDs are never reused. Retried tasks get new attempt_ids but keep their task_id.
"""

from __future__ import annotations

import re
import uuid


def _unique_suffix() -> str:
    """Return a short unique hex string (UUID4-based)."""
    return uuid.uuid4().hex


def generate_run_id() -> str:
    return f"run_{_unique_suffix()}"


def generate_session_id() -> str:
    return f"sess_{_unique_suffix()}"


def generate_attempt_id() -> str:
    return f"att_{_unique_suffix()}"


def generate_operation_id() -> str:
    return f"op_{_unique_suffix()}"


def generate_mutation_id() -> str:
    return f"mut_{_unique_suffix()}"


def generate_discovered_task_id() -> str:
    return f"task_{_unique_suffix()}"


def task_id_from_slug(title: str) -> str:
    """Derive a deterministic task_id from a human-readable title.

    "Auth Service Setup" -> "task_auth-service-setup"
    """
    slug = title.strip().lower()
    # Remove non-alphanumeric chars (except spaces and hyphens)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    # Collapse whitespace to single hyphen
    slug = re.sub(r"\s+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return f"task_{slug}"
