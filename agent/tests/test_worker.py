import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestration.worker import _record_terminal_stale_job_failure, process_claimed_job


def _app_state() -> SimpleNamespace:
    return SimpleNamespace(
        state=SimpleNamespace(
            database_url="postgresql://example",
            agent_storage=object(),
            agent_memory=object(),
        )
    )


def test_process_claimed_agent_run_dispatches(monkeypatch) -> None:
    called: dict[str, object] = {}

    async def fake_execute_agent_run_job(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr("src.orchestration.worker.execute_agent_run_job", fake_execute_agent_run_job)

    job = {
        "id": "job-1",
        "thread_id": "thread-1",
        "user_id": "user-1",
        "job_type": "agent_run",
        "payload": {
            "message": "hello",
            "route": {
                "target": "OPS",
                "confidence_score": 1.0,
                "reasoning": "test",
                "normalized_message": "hello",
                "active_agent": "Operations_Layer",
            },
        },
    }

    asyncio.run(process_claimed_job(_app_state(), job))

    assert called["thread_id"] == "thread-1"
    assert called["user_internal_id"] == "user-1"
    assert called["message"] == "hello"
    assert called["route"].active_agent == "Operations_Layer"


def test_process_claimed_approved_tool_dispatches(monkeypatch) -> None:
    called: dict[str, object] = {}

    async def fake_execute_approved_tool_job(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr("src.orchestration.worker.execute_approved_tool_job", fake_execute_approved_tool_job)

    job = {
        "id": "job-2",
        "thread_id": "thread-2",
        "user_id": "user-2",
        "job_type": "approved_tool",
        "payload": {
            "approval": {
                "id": "approval-1",
                "tool_name": "send_email",
                "payload": {"to_addr": "x@example.com"},
            }
        },
    }

    asyncio.run(process_claimed_job(_app_state(), job))

    assert called["thread_id"] == "thread-2"
    assert called["user_internal_id"] == "user-2"
    assert called["approval"]["tool_name"] == "send_email"


def test_process_claimed_job_rejects_unknown_type() -> None:
    job = {
        "id": "job-3",
        "thread_id": "thread-3",
        "user_id": "user-3",
        "job_type": "mystery",
        "payload": {},
    }

    try:
        asyncio.run(process_claimed_job(_app_state(), job))
    except ValueError as exc:
        assert "Unsupported agent job type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown job type")


def test_record_terminal_stale_agent_run_failure(monkeypatch) -> None:
    called: dict[str, object] = {}

    async def fake_record_agent_run_failure(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr("src.orchestration.worker.record_agent_run_failure", fake_record_agent_run_failure)

    job = {
        "id": "job-4",
        "thread_id": "thread-4",
        "user_id": "user-4",
        "job_type": "agent_run",
        "last_error": "worker expired",
        "payload": {
            "route": {
                "target": "OPS",
                "confidence_score": 1.0,
                "reasoning": "test",
                "normalized_message": "hello",
                "active_agent": "Operations_Layer",
            },
        },
    }

    asyncio.run(_record_terminal_stale_job_failure("postgresql://example", job))

    assert called["thread_id"] == "thread-4"
    assert called["user_internal_id"] == "user-4"
    assert called["error"] == "worker expired"
    assert called["route"].target == "OPS"


def test_record_terminal_stale_approved_tool_failure(monkeypatch) -> None:
    called: dict[str, object] = {}

    async def fake_record_approved_tool_failure(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr("src.orchestration.worker.record_approved_tool_failure", fake_record_approved_tool_failure)

    job = {
        "id": "job-5",
        "thread_id": "thread-5",
        "user_id": "user-5",
        "job_type": "approved_tool",
        "last_error": "worker expired",
        "payload": {
            "approval": {
                "id": "approval-2",
                "tool_name": "send_email",
                "payload": {"to_addr": "x@example.com"},
            },
        },
    }

    asyncio.run(_record_terminal_stale_job_failure("postgresql://example", job))

    assert called["thread_id"] == "thread-5"
    assert called["user_internal_id"] == "user-5"
    assert called["error"] == "worker expired"
    assert called["approval"]["tool_name"] == "send_email"
