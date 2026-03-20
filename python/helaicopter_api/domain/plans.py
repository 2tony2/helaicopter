"""Domain-owned plan parsing and summarization helpers."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlanContentSummary:
    slug: str
    title: str
    preview: str


@dataclass(frozen=True, slots=True)
class PlanStepData:
    step: str
    status: str


@dataclass(frozen=True, slots=True)
class CodexPlanSummary:
    slug: str
    title: str
    preview: str
    content: str


def summarize_plan_content(content: str, fallback_slug: str) -> PlanContentSummary:
    title, body_lines = split_markdown_body(content)
    return PlanContentSummary(
        slug=fallback_slug,
        title=title or fallback_slug,
        preview=" ".join(body_lines)[:200],
    )


def split_markdown_body(content: str) -> tuple[str | None, list[str]]:
    title: str | None = None
    body_lines: list[str] = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if title is None and line.startswith("# "):
            title = line.replace("# ", "", 1).strip()
            continue
        if not line.startswith("#"):
            body_lines.append(line)

    return title, body_lines


def parse_codex_explanation(payload: Mapping[str, object]) -> str | None:
    explanation = payload.get("explanation")
    if isinstance(explanation, str) and explanation.strip():
        return explanation.strip()
    return None


def parse_codex_plan_steps(raw_plan: Sequence[Mapping[str, object]] | None) -> list[PlanStepData]:
    if raw_plan is None:
        return []

    steps: list[PlanStepData] = []
    for item in raw_plan:
        step = item.get("step")
        if not isinstance(step, str) or not step.strip():
            continue
        steps.append(
            PlanStepData(
                step=step.strip(),
                status=normalize_plan_step_status(item.get("status")),
            )
        )
    return steps


def summarize_codex_plan(
    call_id: str,
    explanation: str | None,
    steps: Sequence[PlanStepData],
) -> CodexPlanSummary:
    title_source = first_non_empty_line(explanation) or (
        steps[0].step if steps else f"Plan update {call_id[-8:]}"
    )
    title = truncate(title_source.strip(), max_length=80)
    slug = f"codex-{slugify(title)}-{call_id[-8:]}"
    preview_parts = [explanation] if explanation else []
    preview_parts.extend(f"{checkbox_for_status(step.status)} {step.step}" for step in steps)
    preview = truncate(" ".join(part for part in preview_parts if part), max_length=200)

    content_lines = [f"# {title}"]
    if explanation:
        content_lines.extend(["", explanation])
    if steps:
        content_lines.extend(["", "## Steps", ""])
        for step in steps:
            content_lines.append(f"{checkbox_for_status(step.status)} {step.step}")

    return CodexPlanSummary(
        slug=slug,
        title=title,
        preview=preview,
        content="\n".join(content_lines),
    )


def normalize_plan_step_status(status: object) -> str:
    if isinstance(status, str) and status.strip():
        return status.strip()
    return "pending"


def first_non_empty_line(value: str | None) -> str | None:
    if value is None:
        return None
    for line in value.splitlines():
        if line.strip():
            return line.strip()
    return None


def truncate(value: str, *, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3].rstrip()}..."


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "plan"


def checkbox_for_status(status: str) -> str:
    if status == "completed":
        return "[x]"
    if status == "in_progress":
        return "[-]"
    return "[ ]"
