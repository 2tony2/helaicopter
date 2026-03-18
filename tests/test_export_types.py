from __future__ import annotations

from helaicopter_db.export_types import parse_export_conversation_envelope


def test_parse_export_conversation_envelope_rejects_non_object_detail() -> None:
    assert (
        parse_export_conversation_envelope(
            {
                "type": "conversation",
                "summary": {
                    "sessionId": "session-123",
                    "projectPath": "-Users-tony-Code-helaicopter",
                    "projectName": "Code/helaicopter",
                    "firstMessage": "Ship it",
                    "timestamp": 1_763_200_000_000,
                    "messageCount": 1,
                },
                "detail": "malformed",
                "tasks": [],
                "cost": {
                    "inputCost": 1.0,
                    "outputCost": 2.0,
                    "cacheWriteCost": 0.0,
                    "cacheReadCost": 0.0,
                    "totalCost": 3.0,
                },
            }
        )
        is None
    )
