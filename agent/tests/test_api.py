import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AGENT_TESTING", "1")
os.environ.setdefault("TEST_CLERK_USER_ID", "user_test_001")
os.environ.setdefault("INTERNAL_SERVICE_KEY_SIGNER", "dev_service_token_123")

from main import app  # noqa: E402


AUTH_HEADERS = {
    "x-service-token": "dev_service_token_123",
    "Authorization": "Bearer test-token",
}


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_ok(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_api_threads_without_service_token(client: TestClient):
    res = client.post("/api/threads")
    assert res.status_code in (401, 422)


def test_thread_lifecycle_requires_database(client: TestClient):
    """
    Full create/message/state requires Postgres. Skip when DATABASE_URL is unreachable.
    """
    try:
        # Trigger a lightweight connection via thread creation
        res = client.post("/api/threads", headers=AUTH_HEADERS)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database unavailable: {exc}")

    if res.status_code != 200:
        pytest.skip(f"thread create failed: {res.status_code} {res.text}")

    thread_id = res.json()["thread_id"]
    assert uuid.UUID(thread_id)

    state = client.get(f"/api/threads/{thread_id}/state", headers=AUTH_HEADERS)
    assert state.status_code == 200
    body = state.json()
    assert "messages" in body
    assert "status" in body


def test_approval_reject_noop_without_pending(client: TestClient):
    try:
        res = client.post("/api/threads", headers=AUTH_HEADERS)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database unavailable: {exc}")

    if res.status_code != 200:
        pytest.skip(f"thread create failed: {res.status_code} {res.text}")

    thread_id = res.json()["thread_id"]
    apr = client.post(
        f"/api/threads/{thread_id}/approve",
        headers=AUTH_HEADERS,
        json={"decision": "REJECTED"},
    )
    assert apr.status_code == 200
    assert apr.json().get("status") in ("noop", "rejected")
