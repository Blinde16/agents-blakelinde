from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.builder import build_specialist_agent
from src.orchestration.router import RouteDecision
from src.orchestration.state import (
    append_action_audit,
    append_message,
    get_pending_approval,
    set_run_state,
)
from src.tools.registry import execute_mutating_tool

logger = logging.getLogger(__name__)


def _log_run_event(
    event: str,
    *,
    thread_id: str,
    user_internal_id: str,
    route: RouteDecision | None = None,
    extra: dict[str, object] | None = None,
) -> None:
    payload: dict[str, object] = {
        "event": event,
        "thread_id": thread_id,
        "user_internal_id": user_internal_id,
    }
    if route is not None:
        payload["route_target"] = route.target
        payload["active_agent"] = route.active_agent
    if extra:
        payload.update(extra)
    logger.info("thread_run %s", json.dumps(payload, ensure_ascii=False, default=str))


def route_from_payload(payload: dict[str, Any]) -> RouteDecision:
    return RouteDecision.model_validate(payload)


async def execute_agent_run_job(
    *,
    db_url: str,
    agent_storage: Any,
    agent_memory: Any,
    thread_id: str,
    message: str,
    user_internal_id: str,
    route: RouteDecision,
) -> None:
    await set_run_state(
        db_url,
        thread_id,
        user_internal_id,
        status="processing",
        active_agent=route.active_agent,
        pending_approval=False,
        approval_gate_id=None,
        last_error=None,
    )
    _log_run_event("agent_run_started", thread_id=thread_id, user_internal_id=user_internal_id, route=route)
    agent = build_specialist_agent(
        route.target,
        thread_id=thread_id,
        db_url=db_url,
        user_internal_id=user_internal_id,
        storage=agent_storage,
        memory_db=agent_memory,
    )
    response = await agent.arun(message, session_id=thread_id)

    agent_text = ""
    if hasattr(response, "content"):
        agent_text = response.content or ""
    elif isinstance(response, str):
        agent_text = response

    await append_message(db_url, thread_id, user_internal_id, "assistant", agent_text)
    approval_request = await get_pending_approval(db_url, thread_id)

    await set_run_state(
        db_url,
        thread_id,
        user_internal_id,
        status="awaiting_approval" if approval_request else "completed",
        active_agent=route.active_agent,
        pending_approval=bool(approval_request),
        approval_gate_id=approval_request["id"] if approval_request else None,
        last_error=None,
    )
    _log_run_event(
        "agent_run_completed",
        thread_id=thread_id,
        user_internal_id=user_internal_id,
        route=route,
        extra={
            "status": ("awaiting_approval" if approval_request else "completed"),
            "approval_gate_id": (approval_request["id"] if approval_request else None),
        },
    )


async def execute_approved_tool_job(
    *,
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    approval: dict[str, Any],
) -> None:
    await set_run_state(
        db_url,
        thread_id,
        user_internal_id,
        status="processing",
        pending_approval=False,
        approval_gate_id=None,
        last_error=None,
    )
    _log_run_event(
        "approval_resumed",
        thread_id=thread_id,
        user_internal_id=user_internal_id,
        extra={"tool_name": approval["tool_name"], "approval_gate_id": approval["id"]},
    )

    result = await execute_mutating_tool(approval["tool_name"], approval["payload"])
    await append_message(db_url, thread_id, user_internal_id, "assistant", result)
    await append_action_audit(
        db_url,
        thread_id,
        user_internal_id,
        approval["tool_name"],
        {"result": result, "payload": approval["payload"]},
    )
    await set_run_state(
        db_url,
        thread_id,
        user_internal_id,
        status="completed",
        pending_approval=False,
        approval_gate_id=None,
        last_error=None,
    )
    _log_run_event(
        "approved_action_completed",
        thread_id=thread_id,
        user_internal_id=user_internal_id,
        extra={"tool_name": approval["tool_name"], "approval_gate_id": approval["id"]},
    )


async def record_agent_run_failure(
    *,
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    route: RouteDecision,
    error: str,
) -> None:
    logger.exception("Agent run error for thread %s", thread_id)
    await append_message(db_url, thread_id, user_internal_id, "assistant", f"Agent error: {error}")
    await set_run_state(
        db_url,
        thread_id,
        user_internal_id,
        status="error",
        pending_approval=False,
        approval_gate_id=None,
        last_error=error,
    )
    _log_run_event(
        "agent_run_failed",
        thread_id=thread_id,
        user_internal_id=user_internal_id,
        route=route,
        extra={"error": error},
    )


async def record_approved_tool_failure(
    *,
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    approval: dict[str, Any],
    error: str,
) -> None:
    logger.exception("Approved action failed thread=%s", thread_id)
    await append_message(
        db_url,
        thread_id,
        user_internal_id,
        "assistant",
        f"Approved action failed: {error}",
    )
    await set_run_state(
        db_url,
        thread_id,
        user_internal_id,
        status="error",
        pending_approval=False,
        approval_gate_id=None,
        last_error=error,
    )
    _log_run_event(
        "approved_action_failed",
        thread_id=thread_id,
        user_internal_id=user_internal_id,
        extra={"tool_name": approval["tool_name"], "approval_gate_id": approval["id"], "error": error},
    )
