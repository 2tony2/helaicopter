"""Worker session visibility and reset endpoint tests."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db.models.oltp import OltpBase, WorkerRegistryRecord


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def _worker_client() -> Iterator[TestClient]:
    application = create_app()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)
    application.dependency_overrides[get_services] = lambda: _services_stub(sqlite_engine=engine)
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()
        engine.dispose()


def _register_worker(client: TestClient) -> str:
    response = client.post(
        "/workers/register",
        json={
            "workerType": "pi_shell",
            "provider": "claude",
            "capabilities": {
                "provider": "claude",
                "models": ["claude-sonnet-4-6"],
                "maxConcurrentTasks": 1,
                "supportsDiscovery": False,
                "supportsResume": False,
                "tags": [],
            },
            "host": "local",
        },
    )
    assert response.status_code == 201
    return response.json()["workerId"]


def test_worker_detail_includes_materialized_session_state() -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        engine = client.app.dependency_overrides[get_services]().sqlite_engine
        now = datetime.now(timezone.utc).isoformat()
        with Session(engine) as session:
            row = session.get(WorkerRegistryRecord, worker_id)
            assert row is not None
            row.metadata_json = json.dumps(
                {
                    "session": {
                        "status": "ready",
                        "started_at": now,
                        "last_used_at": now,
                        "failure_reason": None,
                    }
                }
            )
            session.commit()

        payload = client.get(f"/workers/{worker_id}").json()

        assert payload["sessionStatus"] == "ready"
        assert payload["sessionStartedAt"] == now
        assert payload["sessionLastUsedAt"] == now
        assert payload["sessionFailureReason"] is None
        assert payload["sessionResetAvailable"] is True


def test_reset_worker_session_marks_session_absent() -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        engine = client.app.dependency_overrides[get_services]().sqlite_engine
        with Session(engine) as session:
            row = session.get(WorkerRegistryRecord, worker_id)
            assert row is not None
            row.metadata_json = json.dumps(
                {
                    "session": {
                        "status": "failed",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "last_used_at": datetime.now(timezone.utc).isoformat(),
                        "failure_reason": "bootstrap failed",
                    }
                }
            )
            session.commit()

        response = client.post(f"/workers/{worker_id}/reset-session")

        assert response.status_code == 200
        payload = response.json()
        assert payload["sessionStatus"] == "absent"
        assert payload["sessionStartedAt"] is None
        assert payload["sessionLastUsedAt"] is None
        assert payload["sessionFailureReason"] is None


def test_worker_heartbeat_preserves_reset_request_until_worker_acknowledges_absent_state() -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        reset_response = client.post(f"/workers/{worker_id}/reset-session")
        assert reset_response.status_code == 200
        requested_at = reset_response.json()["sessionResetRequestedAt"]
        assert requested_at is not None

        heartbeat_ready = client.post(
            f"/workers/{worker_id}/heartbeat",
            json={
                "status": "idle",
                "currentTaskId": None,
                "currentRunId": None,
                "providerSessionId": "sess_existing",
                "sessionStatus": "ready",
                "sessionStartedAt": "2026-03-26T12:00:00+00:00",
                "sessionLastUsedAt": "2026-03-26T12:05:00+00:00",
                "sessionFailureReason": None,
            },
        )
        assert heartbeat_ready.status_code == 200
        ready_payload = client.get(f"/workers/{worker_id}").json()
        assert ready_payload["sessionResetRequestedAt"] == requested_at

        heartbeat_absent = client.post(
            f"/workers/{worker_id}/heartbeat",
            json={
                "status": "idle",
                "currentTaskId": None,
                "currentRunId": None,
                "providerSessionId": None,
                "sessionStatus": "absent",
                "sessionStartedAt": None,
                "sessionLastUsedAt": None,
                "sessionFailureReason": None,
            },
        )
        assert heartbeat_absent.status_code == 200
        absent_payload = client.get(f"/workers/{worker_id}").json()
        assert absent_payload["sessionResetRequestedAt"] is None
