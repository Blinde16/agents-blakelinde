import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestration import action_executor


def test_execute_direct_action_archive_success(monkeypatch):
    async def _ok(_user_id: str, message_id: str) -> str:
        return json.dumps({"status": "ok", "message_id": message_id})

    monkeypatch.setattr(action_executor, "execute_archive_email", _ok)

    text, report = asyncio.run(
        action_executor.execute_direct_action(
            action_name="archive_email_bulk",
            message_ids=["m1", "m2"],
            user_internal_id="user-1",
        )
    )
    assert "2/2" in text
    assert report["success_count"] == 2


def test_execute_direct_action_partial_failure(monkeypatch):
    async def _mixed(_user_id: str, message_id: str) -> str:
        if message_id == "bad":
            return json.dumps({"error": "gmail_modify_error"})
        return json.dumps({"status": "ok", "message_id": message_id})

    monkeypatch.setattr(action_executor, "execute_star_email", _mixed)

    text, report = asyncio.run(
        action_executor.execute_direct_action(
            action_name="star_email_bulk",
            message_ids=["good", "bad"],
            user_internal_id="user-1",
        )
    )
    assert "Partially completed" in text
    assert report["success_count"] == 1
