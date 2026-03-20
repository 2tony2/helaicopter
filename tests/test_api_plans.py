"""Endpoint tests for the plans API."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from helaicopter_api.bootstrap.services import build_services
from helaicopter_api.domain import plans as domain_plans
from helaicopter_api.server.config import Settings
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app


def _write_codex_thread_db(path: Path, session_id: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE threads (
              id TEXT PRIMARY KEY,
              title TEXT,
              cwd TEXT,
              source TEXT,
              model_provider TEXT,
              tokens_used INTEGER,
              git_sha TEXT,
              git_branch TEXT,
              git_origin_url TEXT,
              cli_version TEXT,
              first_user_message TEXT,
              created_at INTEGER,
              updated_at INTEGER,
              rollout_path TEXT,
              agent_role TEXT,
              agent_nickname TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO threads (
              id,
              title,
              cwd,
              source,
              model_provider,
              tokens_used,
              git_sha,
              git_branch,
              git_origin_url,
              cli_version,
              first_user_message,
              created_at,
              updated_at,
              rollout_path,
              agent_role,
              agent_nickname
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "Plans rollout",
                "/Users/tony/Code/helaicopter",
                '{"kind":"main"}',
                "openai",
                0,
                None,
                "main",
                None,
                "0.1.0",
                "Implement the plans API",
                1_763_200_000,
                1_763_200_123,
                None,
                None,
                None,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _seed_plan_sources(tmp_path: Path) -> Settings:
    claude_dir = tmp_path / ".claude"
    codex_dir = tmp_path / ".codex"
    project_path = "-Users-tony-Code-helaicopter"
    claude_dir.joinpath("plans").mkdir(parents=True)
    claude_dir.joinpath("projects", project_path).mkdir(parents=True)
    codex_dir.joinpath("sessions", "2026", "03", "16").mkdir(parents=True)

    file_plan = claude_dir / "plans" / "alpha.md"
    file_plan.write_text("# Alpha file\n\nShip the backend.\nVerify endpoints.\n", encoding="utf-8")
    os.utime(file_plan, (1_763_100_000, 1_763_100_000))

    claude_session = claude_dir / "projects" / project_path / "claude-session-1.jsonl"
    claude_session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "uuid": "evt-claude-user",
                        "timestamp": "2026-03-15T09:59:00Z",
                        "sessionId": "claude-session-1",
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Review the plan panel"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "evt-claude-plan",
                        "timestamp": "2026-03-15T10:00:00Z",
                        "sessionId": "claude-session-1",
                        "message": {"role": "assistant", "model": "claude-sonnet-4-5"},
                        "planContent": "# Claude session rollout\n\nBuild the plans API.\nKeep previews short.\n",
                        "slug": "claude-session-rollout",
                    }
                )
            ]
        ),
        encoding="utf-8",
    )

    codex_session_id = "019cdbff-dbb7-71d0-baaf-c669c55af628"
    codex_session = (
        codex_dir
        / "sessions"
        / "2026"
        / "03"
        / "16"
        / f"rollout-2026-03-16T10-00-00-{codex_session_id}.jsonl"
    )
    codex_session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-16T10:00:00Z",
                        "type": "session_meta",
                        "payload": {
                            "id": codex_session_id,
                            "timestamp": "2026-03-16T10:00:00Z",
                            "cwd": "/Users/tony/Code/helaicopter",
                            "originator": "codex_cli_rs",
                            "cli_version": "0.1.0",
                            "source": "cli",
                            "model_provider": "openai",
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-16T10:00:01Z",
                        "type": "turn_context",
                        "payload": {"model": "gpt-5"},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-16T10:00:02Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "update_plan",
                            "call_id": "call-12345678",
                            "arguments": json.dumps(
                                {
                                    "explanation": "Codex rollout plan",
                                    "plan": [
                                        {"step": "Wire router", "status": "in_progress"},
                                        {"step": "Add tests", "status": "pending"},
                                    ],
                                }
                            ),
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    _write_codex_thread_db(codex_dir / "state_5.sqlite", codex_session_id)

    return Settings(project_root=tmp_path, claude_dir=claude_dir, codex_dir=codex_dir)


@pytest.fixture()
def plans_client(tmp_path: Path):
    settings = _seed_plan_sources(tmp_path)
    services = build_services(settings)
    application = create_app()
    application.dependency_overrides[get_services] = lambda: services

    with TestClient(application) as client:
        yield client

    application.dependency_overrides.clear()
    services.sqlite_engine.dispose()


class TestPlansEndpoints:
    def test_list_plans_summarizes_each_claude_plan_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _seed_plan_sources(tmp_path)
        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services
        summarize_calls = 0
        original = domain_plans.summarize_plan_content

        def count_calls(content: str, fallback_slug: str) -> domain_plans.PlanContentSummary:
            nonlocal summarize_calls
            summarize_calls += 1
            return original(content, fallback_slug)

        monkeypatch.setattr(domain_plans, "summarize_plan_content", count_calls)

        try:
            with TestClient(application) as client:
                response = client.get("/plans")
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert response.status_code == 200
        assert summarize_calls == 2

    def test_list_plans_ignores_codex_lines_with_non_object_payloads(self, tmp_path: Path) -> None:
        settings = _seed_plan_sources(tmp_path)
        codex_session = next(settings.codex_dir.glob("sessions/**/*.jsonl"))
        codex_session.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "timestamp": "2026-03-16T10:00:01.500Z",
                            "type": "response_item",
                            "payload": "malformed",
                        }
                    ),
                    codex_session.read_text(encoding="utf-8"),
                ]
            ),
            encoding="utf-8",
        )
        services = build_services(settings)
        application = create_app()
        application.dependency_overrides[get_services] = lambda: services

        try:
            with TestClient(application) as client:
                response = client.get("/plans")
        finally:
            application.dependency_overrides.clear()
            services.sqlite_engine.dispose()

        assert response.status_code == 200
        assert [plan["provider"] for plan in response.json()] == ["codex", "claude", "claude"]

    def test_list_plans_includes_claude_and_codex_sources(self, plans_client: TestClient) -> None:
        response = plans_client.get("/plans")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 3
        assert [plan["provider"] for plan in payload] == ["codex", "claude", "claude"]

        codex_plan = payload[0]
        assert codex_plan["slug"] == "codex-codex-rollout-plan-12345678"
        assert codex_plan["preview"] == "Codex rollout plan [-] Wire router [ ] Add tests"
        assert codex_plan["session_id"] == "019cdbff-dbb7-71d0-baaf-c669c55af628"
        assert codex_plan["project_path"] == "codex:-Users-tony-Code-helaicopter"
        assert codex_plan["route_slug"] == "implement-the-plans-api"
        assert (
            codex_plan["conversation_ref"]
            == "implement-the-plans-api--codex-019cdbff-dbb7-71d0-baaf-c669c55af628"
        )

        claude_session_plan = payload[1]
        assert claude_session_plan["slug"] == "claude-session-rollout"
        assert claude_session_plan["model"] == "claude-sonnet-4-5"
        assert claude_session_plan["route_slug"] == "review-the-plan-panel"
        assert (
            claude_session_plan["conversation_ref"]
            == "review-the-plan-panel--claude-claude-session-1"
        )

        file_plan = payload[2]
        assert file_plan["slug"] == "alpha"
        assert file_plan["source_path"].endswith("/.claude/plans/alpha.md")
        assert file_plan["route_slug"] is None
        assert file_plan["conversation_ref"] is None

    def test_detail_returns_session_plan_content_and_steps(self, plans_client: TestClient) -> None:
        plans = plans_client.get("/plans").json()
        codex_plan_id = plans[0]["id"]

        response = plans_client.get(f"/plans/{codex_plan_id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "codex"
        assert payload["title"] == "Codex rollout plan"
        assert payload["explanation"] == "Codex rollout plan"
        assert payload["steps"] == [
            {"step": "Wire router", "status": "in_progress"},
            {"step": "Add tests", "status": "pending"},
        ]
        assert payload["content"].startswith("# Codex rollout plan")
        assert payload["route_slug"] == "implement-the-plans-api"
        assert payload["conversation_ref"] == "implement-the-plans-api--codex-019cdbff-dbb7-71d0-baaf-c669c55af628"

    def test_missing_plain_slug_returns_404(self, plans_client: TestClient) -> None:
        response = plans_client.get("/plans/missing-plan")

        assert response.status_code == 404
        assert response.json() == {"detail": "Plan not found"}
