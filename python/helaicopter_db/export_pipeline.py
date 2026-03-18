from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from helaicopter_api.server.config import Settings, load_settings

from .export_types import (
    ExportConversationEnvelope,
    parse_export_conversation_envelope,
    parse_export_meta_payload,
)


@dataclass
class ExportMeta:
    conversation_count: int
    input_key: str
    scope_label: str
    window_days: int
    window_start: str | None
    window_end: str | None


def tsx_binary(settings: Settings | None = None) -> Path:
    project_root = (settings or load_settings()).project_root
    binary = project_root / "node_modules" / ".bin" / "tsx"
    if sys.platform.startswith("win"):
        binary = binary.with_suffix(".cmd")
    if not binary.exists():
        raise RuntimeError("Missing node_modules/.bin/tsx. Run `npm install` first.")
    return binary


def iter_export_rows(settings: Settings | None = None) -> Iterable[ExportConversationEnvelope]:
    project_root = (settings or load_settings()).project_root
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_handle:
        process = subprocess.Popen(
            [str(tsx_binary(settings)), "scripts/export-parsed-data.ts"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=stderr_handle,
            text=True,
        )

        assert process.stdout is not None
        try:
            for line in process.stdout:
                if not line.strip():
                    continue
                record = json.loads(line)
                envelope = parse_export_conversation_envelope(record)
                if envelope is not None and envelope.get("type") == "conversation":
                    yield envelope
        finally:
            return_code = process.wait()
            stderr_handle.seek(0)
            stderr = stderr_handle.read()
            if return_code != 0:
                raise RuntimeError(stderr.strip() or "The TypeScript export pipeline failed.")


def read_export_meta(settings: Settings | None = None) -> ExportMeta:
    project_root = (settings or load_settings()).project_root
    process = subprocess.run(
        [str(tsx_binary(settings)), "scripts/export-parsed-data.ts", "--meta-only"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("The export metadata pipeline did not return any output.")
    payload = parse_export_meta_payload(json.loads(lines[-1]))
    if payload is None:
        raise RuntimeError("The export metadata pipeline returned an invalid payload.")
    return ExportMeta(
        conversation_count=int(payload["conversationCount"]),
        input_key=str(payload["inputKey"]),
        scope_label=str(payload["scopeLabel"]),
        window_days=int(payload["windowDays"]),
        window_start=payload.get("windowStart"),
        window_end=payload.get("windowEnd"),
    )
