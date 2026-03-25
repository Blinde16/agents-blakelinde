from __future__ import annotations

import json
from typing import Any, Callable, Awaitable

from src.tools.google_workspace import (
    execute_archive_email,
    execute_mark_email_read,
    execute_mark_email_unread,
    execute_star_email,
    execute_unstar_email,
)


async def _run_bulk_action(
    *,
    action_name: str,
    message_ids: list[str],
    runner: Callable[[str, str], Awaitable[str]],
    user_internal_id: str,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for message_id in message_ids:
        raw = await runner(user_internal_id, message_id)
        parsed: dict[str, Any]
        try:
            parsed = json.loads(raw)
        except Exception:  # noqa: BLE001
            parsed = {"raw": raw}
        ok = "error" not in parsed
        results.append({"message_id": message_id, "ok": ok, "result": parsed})

    succeeded = [r["message_id"] for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    return {
        "action": action_name,
        "requested": message_ids,
        "succeeded": succeeded,
        "failed": failed,
        "count": len(message_ids),
        "success_count": len(succeeded),
    }


def _to_user_message(report: dict[str, Any]) -> str:
    action = report["action"]
    success_count = report["success_count"]
    total = report["count"]
    succeeded = report["succeeded"]
    failed = report["failed"]

    if not failed:
        return (
            f"Completed `{action}` for {success_count}/{total} emails. "
            f"Message IDs: {', '.join(succeeded)}"
        )

    failed_ids = [f.get("message_id", "") for f in failed]
    return (
        f"Partially completed `{action}`: {success_count}/{total} succeeded. "
        f"Failed message IDs: {', '.join(failed_ids)}"
    )


async def execute_direct_action(
    *,
    action_name: str,
    message_ids: list[str],
    user_internal_id: str,
) -> tuple[str, dict[str, Any]]:
    runners: dict[str, Callable[[str, str], Awaitable[str]]] = {
        "archive_email_bulk": execute_archive_email,
        "mark_email_read_bulk": execute_mark_email_read,
        "mark_email_unread_bulk": execute_mark_email_unread,
        "star_email_bulk": execute_star_email,
        "unstar_email_bulk": execute_unstar_email,
    }
    runner = runners.get(action_name)
    if runner is None:
        raise ValueError(f"Unsupported direct action: {action_name}")

    report = await _run_bulk_action(
        action_name=action_name,
        message_ids=message_ids,
        runner=runner,
        user_internal_id=user_internal_id,
    )
    return _to_user_message(report), report
