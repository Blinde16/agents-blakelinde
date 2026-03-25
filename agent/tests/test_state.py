import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestration.state import derive_run_state


def _run_row(
    *,
    status: str = "processing",
    pending_approval: bool = False,
    last_error: str | None = None,
    updated_at: datetime | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    return {
        "status": status,
        "active_agent": "Operations_Layer",
        "pending_approval": pending_approval,
        "approval_gate_id": None,
        "last_error": last_error,
        "updated_at": updated_at or now,
        "started_at": started_at or now,
        "completed_at": completed_at,
    }


def test_derive_run_state_marks_stale_processing_run_as_error(monkeypatch) -> None:
    monkeypatch.setenv("THREAD_RUN_STALE_SECONDS", "120")
    now = datetime(2026, 3, 25, 18, 0, tzinfo=timezone.utc)
    run_row = _run_row(updated_at=now - timedelta(minutes=5), started_at=now - timedelta(minutes=6))

    payload = derive_run_state(run_row, approval_request=None, messages=[], now=now)

    assert payload["stale"] is True
    assert payload["status"] == "error"
    assert "stalled" in str(payload["last_error"]).lower()
    assert payload["started_at"] == (now - timedelta(minutes=6)).isoformat()


def test_derive_run_state_keeps_awaiting_approval_non_stale(monkeypatch) -> None:
    monkeypatch.setenv("THREAD_RUN_STALE_SECONDS", "120")
    now = datetime(2026, 3, 25, 18, 0, tzinfo=timezone.utc)
    approval = {"id": "gate-1", "tool_name": "send_email", "payload": {}, "status": "PENDING"}
    run_row = _run_row(
        status="awaiting_approval",
        pending_approval=True,
        updated_at=now - timedelta(hours=2),
        started_at=now - timedelta(hours=2),
    )

    payload = derive_run_state(run_row, approval_request=approval, messages=[], now=now)

    assert payload["stale"] is False
    assert payload["status"] == "awaiting_approval"
    assert payload["approval_request"] == approval


def test_derive_run_state_idle_without_run_row() -> None:
    payload = derive_run_state(None, approval_request=None, messages=[{"role": "user", "content": "hi"}])

    assert payload["status"] == "idle"
    assert payload["messages"] == [{"role": "user", "content": "hi"}]
    assert payload["updated_at"] is None
