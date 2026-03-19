from __future__ import annotations

from pathlib import Path
import re

from oats.models import RunSpec, TaskSpec


TASKS_SECTION_RE = re.compile(r"^##\s+Tasks\s*$", re.MULTILINE)
TASK_HEADING_RE = re.compile(r"^###\s+([A-Za-z0-9_-]+)\s*$", re.MULTILINE)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
LABEL_RE = re.compile(
    r"^(Title|Depends on|Agent|Model|Reasoning effort|Acceptance criteria|Notes|Validation override):\s*(.*)$"
)


class RunSpecParseError(RuntimeError):
    """Raised when a Markdown run spec cannot be parsed."""


def parse_run_spec(path: Path) -> RunSpec:
    text = path.read_text()
    title = _parse_title(text, path)
    tasks_section = _extract_tasks_section(text, path)
    tasks = _parse_tasks(tasks_section)
    if not tasks:
        raise RunSpecParseError(f"No tasks found in {path}")
    return RunSpec(title=title, tasks=tasks, source_path=path.resolve())


def _parse_title(text: str, path: Path) -> str:
    match = H1_RE.search(text)
    if not match:
        raise RunSpecParseError(f"Expected a top-level title in {path}")
    return match.group(1).strip()


def _extract_tasks_section(text: str, path: Path) -> str:
    match = TASKS_SECTION_RE.search(text)
    if not match:
        raise RunSpecParseError(f"Expected a '## Tasks' section in {path}")

    start = match.end()
    remaining = text[start:]
    next_section = re.search(r"^##\s+", remaining, re.MULTILINE)
    if next_section:
        return remaining[: next_section.start()]
    return remaining


def _parse_tasks(section_text: str) -> list[TaskSpec]:
    matches = list(TASK_HEADING_RE.finditer(section_text))
    tasks: list[TaskSpec] = []

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section_text)
        task_id = match.group(1).strip()
        body = section_text[start:end].strip()
        tasks.append(_parse_task(task_id, body))

    return tasks


def _parse_task(task_id: str, body: str) -> TaskSpec:
    title: str | None = None
    depends_on: list[str] = []
    agent: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    acceptance_criteria: list[str] = []
    notes: list[str] = []
    validation_override: list[str] = []
    prompt_parts: list[str] = []

    lines = body.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        label_match = LABEL_RE.match(stripped)
        if label_match:
            label, value = label_match.groups()
            if label == "Title":
                title = value.strip()
                index += 1
            elif label == "Depends on":
                depends_on = _parse_csv_values(value.strip())
                index += 1
            elif label == "Agent":
                agent = value.strip() or None
                index += 1
            elif label == "Model":
                model = value.strip() or None
                index += 1
            elif label == "Reasoning effort":
                reasoning_effort = value.strip() or None
                index += 1
            elif label == "Acceptance criteria":
                block_lines, index = _consume_block(lines, index + 1)
                combined = [value] if value else []
                combined.extend(block_lines)
                acceptance_criteria = _normalize_list_block(combined)
            elif label == "Notes":
                block_lines, index = _consume_block(lines, index + 1)
                combined = [value] if value else []
                combined.extend(block_lines)
                notes = _normalize_list_block(combined)
            elif label == "Validation override":
                block_lines, index = _consume_block(lines, index + 1)
                combined = [value] if value else []
                combined.extend(block_lines)
                validation_override = _normalize_list_block(combined)
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            next_line = lines[index].rstrip()
            next_stripped = next_line.strip()
            if not next_stripped:
                index += 1
                break
            if LABEL_RE.match(next_stripped):
                break
            paragraph_lines.append(next_stripped)
            index += 1
        prompt_parts.append("\n".join(paragraph_lines))

    prompt = "\n\n".join(part for part in prompt_parts if part).strip()
    if not prompt:
        raise RunSpecParseError(f"Task '{task_id}' must include implementation instructions")

    return TaskSpec(
        id=task_id,
        title=title,
        prompt=prompt,
        depends_on=depends_on,
        agent=agent,
        model=model,
        reasoning_effort=reasoning_effort,
        acceptance_criteria=acceptance_criteria,
        notes=notes,
        validation_override=validation_override,
        raw_body=body,
    )


def _consume_block(lines: list[str], index: int) -> tuple[list[str], int]:
    block: list[str] = []

    while index < len(lines):
        current = lines[index]
        stripped = current.strip()
        if not stripped:
            index += 1
            if block:
                break
            continue
        if LABEL_RE.match(stripped):
            break
        block.append(stripped)
        index += 1

    return block, index


def _normalize_inline_text(lines: list[str]) -> str:
    return " ".join(line.strip() for line in lines if line.strip()).strip()


def _normalize_list_block(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
        else:
            items.append(stripped)
    return items


def _parse_csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
