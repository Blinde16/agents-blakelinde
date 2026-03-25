import json
import logging
import uuid
from enum import Enum

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

from src.agents.builder import build_specialist_agent
from src.api.dependencies import authenticate_internal
from src.orchestration.action_executor import execute_direct_action
from src.orchestration.context_engine import prepare_user_intent
from src.orchestration.router import RouteDecision, route_message
from src.orchestration.state import (
    ThreadAccessError,
    append_action_audit,
    append_message,
    create_thread_state,
    get_thread_context_state,
    get_or_create_user_id,
    get_pending_approval,
    get_recent_messages,
    get_thread_state,
    resolve_pending_approval,
    set_run_state,
    upsert_thread_context_state,
)
from src.tools.finance_staging import ingest_user_spreadsheet
from src.tools.google_workspace import upsert_user_google_credentials
from src.tools.google_workspace import exchange_google_oauth_code, get_google_connection_status
from src.tools.notion_calendar import get_notion_connection_status, upsert_user_notion_credentials
from src.tools.registry import execute_mutating_tool
from src.tools.schemas import GoogleCredentialsPayload, GoogleOAuthExchangePayload, NotionCredentialsPayload

try:
    from agno.run.response import RunEvent
except ImportError:  # pragma: no cover
    RunEvent = None  # type: ignore[misc, assignment]

router = APIRouter(prefix="/api")


def _norm_run_event(ev: object | None) -> str:
    if ev is None:
        return ""
    if isinstance(ev, Enum):
        return str(ev.value)
    return str(ev)


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


class MessagePayload(BaseModel):
    message: str
    stream: bool = False


def _sse_data_line(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class ApprovalPayload(BaseModel):
    decision: str

    @field_validator("decision")
    @classmethod
    def _normalize_decision(cls, v: str) -> str:
        d = (v or "").strip().upper()
        if d not in ("APPROVED", "REJECTED"):
            raise ValueError('decision must be "APPROVED" or "REJECTED"')
        return d


def _route_from_domain(domain: str, message: str) -> RouteDecision:
    target = domain if domain in ("CFO", "CRO", "CMO", "OPS") else "OPS"
    active = {
        "CFO": "Finance_Layer",
        "CRO": "Sales_Ops_Layer",
        "CMO": "Brand_Layer",
        "OPS": "Operations_Layer",
    }[target]
    return RouteDecision(
        target=target,  # type: ignore[arg-type]
        confidence_score=0.95,
        reasoning=f"Context resolver pinned domain to {target}.",
        normalized_message=message,
        active_agent=active,
    )


async def _stream_direct_action(
    *,
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    action_name: str,
    message_ids: list[str],
):
    yield _sse_data_line({"type": "status", "text": "Executing direct email action..."})
    assistant_text, report = await execute_direct_action(
        action_name=action_name,
        message_ids=message_ids,
        user_internal_id=user_internal_id,
    )
    await append_message(db_url, thread_id, user_internal_id, "assistant", assistant_text)
    await append_action_audit(db_url, thread_id, user_internal_id, action_name, report)
    await upsert_thread_context_state(
        db_url,
        thread_id,
        user_internal_id,
        {
            "selected_email_message_ids": message_ids,
            "last_direct_action": action_name,
            "last_direct_action_report": report,
        },
    )
    await set_run_state(
        db_url,
        thread_id,
        user_internal_id,
        status="completed",
        active_agent="Operations_Layer",
        pending_approval=False,
        approval_gate_id=None,
        last_error=None,
    )
    _log_run_event(
        "direct_action_started",
        thread_id=thread_id,
        user_internal_id=user_internal_id,
        extra={"action_name": action_name, "message_count": len(message_ids)},
    )
    yield _sse_data_line({"type": "delta", "text": assistant_text})
    yield _sse_data_line(
        {
            "type": "done",
            "thread_id": thread_id,
            "active_agent": "Operations_Layer",
            "status": "completed",
            "pending_approval": False,
            "approval_gate_id": None,
        }
    )
    _log_run_event(
        "direct_action_completed",
        thread_id=thread_id,
        user_internal_id=user_internal_id,
        extra={"action_name": action_name, "success_count": report.get("success_count")},
    )


async def async_run_agent(
    request: Request,
    thread_id: str,
    message: str,
    user_internal_id: str,
    route: RouteDecision | None = None,
):
    db_url = request.app.state.database_url
    agent_storage = request.app.state.agent_storage
    agent_memory = getattr(request.app.state, "agent_memory", None)
    if route is None:
        history = await get_recent_messages(thread_id, limit=6)
        route = await route_message(message, history=history)

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

    try:
        agent = build_specialist_agent(
            route.target,
            thread_id=thread_id,
            db_url=db_url,
            user_internal_id=user_internal_id,
            storage=agent_storage,
            memory_db=agent_memory,
        )
        response = await agent.arun(route.normalized_message, session_id=thread_id)

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
    except Exception as exc:
        logger.exception("Agent run error for thread %s", thread_id)
        await append_message(db_url, thread_id, user_internal_id, "assistant", f"Agent error: {str(exc)}")
        await set_run_state(
            db_url,
            thread_id,
            user_internal_id,
            status="error",
            pending_approval=False,
            approval_gate_id=None,
            last_error=str(exc),
        )
        _log_run_event(
            "agent_run_failed",
            thread_id=thread_id,
            user_internal_id=user_internal_id,
            route=route,
            extra={"error": str(exc)},
        )


async def async_run_agent_stream(
    request: Request,
    thread_id: str,
    message: str,
    user_internal_id: str,
    route: RouteDecision | None = None,
):
    """Runs the specialist with Agno streaming; emits SSE `data:` JSON lines.

    Emits a status line before intent classification so the client is not idle while the LLM router runs.
    """
    yield _sse_data_line({"type": "status", "text": "Classifying intent…"})
    if route is None:
        history = await get_recent_messages(thread_id, limit=6)
        route = await route_message(message, history=history)
    yield _sse_data_line(
        {
            "type": "status",
            "text": (
                f"{route.active_agent}: starting — Gmail and other tools may take several seconds "
                "before the reply streams."
            ),
        }
    )
    db_url = request.app.state.database_url
    agent_storage = request.app.state.agent_storage
    agent_memory = getattr(request.app.state, "agent_memory", None)

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
    _log_run_event("agent_stream_started", thread_id=thread_id, user_internal_id=user_internal_id, route=route)

    try:
        logger.info(
            "agent_stream_build thread=%s target=%s active=%s",
            thread_id,
            route.target,
            route.active_agent,
        )
        agent = build_specialist_agent(
            route.target,
            thread_id=thread_id,
            db_url=db_url,
            user_internal_id=user_internal_id,
            storage=agent_storage,
            memory_db=agent_memory,
        )
        stream_iter = await agent.arun(
            route.normalized_message,
            session_id=thread_id,
            stream=True,
        )
        full_text = ""
        event_count = 0
        skip_text_events = (
            {
                RunEvent.run_started.value,
                RunEvent.run_completed.value,
                RunEvent.updating_memory.value,
            }
            if RunEvent is not None
            else set()
        )
        async for run_response in stream_iter:
            event_count += 1
            ev = _norm_run_event(getattr(run_response, "event", None))
            chunk = run_response.content
            if RunEvent is not None and ev in (
                RunEvent.tool_call_started.value,
                RunEvent.tool_call_completed.value,
            ):
                if ev == RunEvent.tool_call_started.value:
                    yield _sse_data_line(
                        {
                            "type": "status",
                            "text": "Running tools (e.g. Gmail) — this can take 10–30s with no text yet.",
                        }
                    )
                else:
                    yield _sse_data_line(
                        {
                            "type": "status",
                            "text": "Tool finished; generating reply…",
                        }
                    )
            elif ev in skip_text_events:
                pass
            elif isinstance(chunk, str) and chunk:
                full_text += chunk
                yield _sse_data_line({"type": "delta", "text": chunk})

            if event_count <= 12 or (
                RunEvent is not None
                and ev
                in (
                    RunEvent.tool_call_started.value,
                    RunEvent.tool_call_completed.value,
                )
            ):
                logger.info(
                    "agno_stream thread=%s event=%s chunk_type=%s chunk_len=%s",
                    thread_id,
                    ev,
                    type(chunk).__name__,
                    len(chunk) if isinstance(chunk, str) else None,
                )

        if not full_text.strip():
            logger.warning(
                "agent_stream_empty_reply thread=%s events=%s — model returned no assistant text",
                thread_id,
                event_count,
            )
            fallback = (
                "No assistant text was produced (tools may have failed or the model returned empty output). "
                "Check the API terminal for ERROR lines and verify OPENAI_API_KEY / Google OAuth."
            )
            full_text = fallback
            yield _sse_data_line({"type": "delta", "text": fallback})

        logger.info(
            "agent_stream_done thread=%s events=%s reply_chars=%s",
            thread_id,
            event_count,
            len(full_text),
        )
        await append_message(db_url, thread_id, user_internal_id, "assistant", full_text)
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
            "agent_stream_completed",
            thread_id=thread_id,
            user_internal_id=user_internal_id,
            route=route,
            extra={
                "status": ("awaiting_approval" if approval_request else "completed"),
                "approval_gate_id": (approval_request["id"] if approval_request else None),
                "reply_chars": len(full_text),
            },
        )
        yield _sse_data_line(
            {
                "type": "done",
                "thread_id": thread_id,
                "active_agent": route.active_agent,
                "status": ("awaiting_approval" if approval_request else "completed"),
                "pending_approval": bool(approval_request),
                "approval_gate_id": (approval_request["id"] if approval_request else None),
            }
        )
    except Exception as exc:
        logger.exception("Agent stream run error for thread %s", thread_id)
        await append_message(db_url, thread_id, user_internal_id, "assistant", f"Agent error: {str(exc)}")
        await set_run_state(
            db_url,
            thread_id,
            user_internal_id,
            status="error",
            pending_approval=False,
            approval_gate_id=None,
            last_error=str(exc),
        )
        _log_run_event(
            "agent_stream_failed",
            thread_id=thread_id,
            user_internal_id=user_internal_id,
            route=route,
            extra={"error": str(exc)},
        )
        yield _sse_data_line({"type": "error", "message": str(exc)})


@router.post("/threads")
async def create_thread(request: Request, clerk_sub: str = Depends(authenticate_internal)):
    """Instantiates a new thread with a unique UUID and persistent runtime state."""
    db_url = request.app.state.database_url
    try:
        user_internal_id = await get_or_create_user_id(db_url, clerk_sub)
        thread_id = str(uuid.uuid4())
        await create_thread_state(db_url, thread_id, user_internal_id)
    except Exception as exc:
        logger.exception("create_thread failed")
        raise HTTPException(
            status_code=500,
            detail={"error": "create_thread_failed", "message": str(exc)},
        ) from exc
    return {"thread_id": thread_id}


@router.post("/threads/{thread_id}/messages")
async def push_message(
    thread_id: str,
    payload: MessagePayload,
    request: Request,
    background_tasks: BackgroundTasks,
    clerk_sub: str = Depends(authenticate_internal),
):
    """Accepts a user message and fires agent execution as a background task."""
    db_url = request.app.state.database_url
    user_internal_id = await get_or_create_user_id(db_url, clerk_sub)

    history = await get_recent_messages(thread_id, limit=12)
    try:
        prior_context = await get_thread_context_state(db_url, thread_id, user_internal_id)
    except ThreadAccessError:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    intent_decision = prepare_user_intent(
        payload.message,
        prior_context=prior_context,
        history=history,
    )
    if intent_decision.context_patch:
        await upsert_thread_context_state(
            db_url,
            thread_id,
            user_internal_id,
            intent_decision.context_patch,
        )

    resolved_message = intent_decision.resolved_message
    route_override: RouteDecision | None = None
    if intent_decision.domain in ("CFO", "CRO", "CMO", "OPS") and intent_decision.intent != "unknown":
        route_override = _route_from_domain(intent_decision.domain, resolved_message)

    if payload.stream:
        try:
            await append_message(db_url, thread_id, user_internal_id, "user", payload.message)
            await set_run_state(
                db_url,
                thread_id,
                user_internal_id,
                status="processing",
                active_agent="Classifying intent",
                pending_approval=False,
                approval_gate_id=None,
                last_error=None,
            )
        except ThreadAccessError:
            raise HTTPException(status_code=403, detail="Forbidden") from None

        if intent_decision.direct_action and intent_decision.message_ids:
            return StreamingResponse(
                _stream_direct_action(
                    db_url=db_url,
                    thread_id=thread_id,
                    user_internal_id=user_internal_id,
                    action_name=intent_decision.direct_action,
                    message_ids=intent_decision.message_ids,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-store",
                    "X-Accel-Buffering": "no",
                },
            )

        return StreamingResponse(
            async_run_agent_stream(
                request,
                thread_id,
                resolved_message,
                user_internal_id,
                route_override,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        await append_message(db_url, thread_id, user_internal_id, "user", payload.message)
    except ThreadAccessError:
        raise HTTPException(status_code=403, detail="Forbidden") from None

    if intent_decision.direct_action and intent_decision.message_ids:
        await set_run_state(
            db_url,
            thread_id,
            user_internal_id,
            status="processing",
            active_agent="Operations_Layer",
            pending_approval=False,
            approval_gate_id=None,
            last_error=None,
        )
        assistant_text, report = await execute_direct_action(
            action_name=intent_decision.direct_action,
            message_ids=intent_decision.message_ids,
            user_internal_id=user_internal_id,
        )
        await append_message(db_url, thread_id, user_internal_id, "assistant", assistant_text)
        await append_action_audit(
            db_url,
            thread_id,
            user_internal_id,
            intent_decision.direct_action,
            report,
        )
        await upsert_thread_context_state(
            db_url,
            thread_id,
            user_internal_id,
            {
                "selected_email_message_ids": intent_decision.message_ids,
                "last_direct_action": intent_decision.direct_action,
                "last_direct_action_report": report,
            },
        )
        await set_run_state(
            db_url,
            thread_id,
            user_internal_id,
            status="completed",
            active_agent="Operations_Layer",
            pending_approval=False,
            approval_gate_id=None,
            last_error=None,
        )
        return {"status": "completed", "thread_id": thread_id, "active_agent": "Operations_Layer"}

    route = route_override or await route_message(resolved_message, history=history)
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

    background_tasks.add_task(
        async_run_agent,
        request,
        thread_id,
        resolved_message,
        user_internal_id,
        route,
    )
    return {"status": "processing", "thread_id": thread_id, "active_agent": route.active_agent}


@router.post("/finance/sheets/upload")
async def upload_finance_sheet(
    request: Request,
    file: UploadFile = File(...),
    clerk_sub: str = Depends(authenticate_internal),
):
    """Ingest CSV/XLSX into user-scoped staging rows; returns upload_id for CFO tools."""
    db_url = request.app.state.database_url
    user_internal_id = await get_or_create_user_id(db_url, clerk_sub)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    raw = await file.read()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 15MB)")
    try:
        return await ingest_user_spreadsheet(user_internal_id, file.filename, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/integrations/notion/credentials")
async def save_notion_credentials(
    request: Request,
    payload: NotionCredentialsPayload,
    clerk_sub: str = Depends(authenticate_internal),
):
    """Store encrypted Notion integration token and optional content calendar database id."""
    db_url = request.app.state.database_url
    user_internal_id = await get_or_create_user_id(db_url, clerk_sub)
    try:
        await upsert_user_notion_credentials(
            user_internal_id,
            payload.token,
            payload.content_database_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "saved"}


@router.post("/integrations/google/credentials")
async def save_google_credentials(
    request: Request,
    payload: GoogleCredentialsPayload,
    clerk_sub: str = Depends(authenticate_internal),
):
    """Store encrypted Google OAuth refresh token for Gmail + Calendar tools."""
    db_url = request.app.state.database_url
    user_internal_id = await get_or_create_user_id(db_url, clerk_sub)
    try:
        await upsert_user_google_credentials(
            user_internal_id,
            payload.refresh_token,
            payload.google_email,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "saved"}


@router.get("/integrations/status")
async def integration_status(
    request: Request,
    clerk_sub: str = Depends(authenticate_internal),
):
    db_url = request.app.state.database_url
    user_internal_id = await get_or_create_user_id(db_url, clerk_sub)
    google = await get_google_connection_status(user_internal_id)
    notion = await get_notion_connection_status(user_internal_id)
    return {"connectors": [google, notion]}


@router.post("/integrations/google/oauth/exchange")
async def exchange_google_oauth(
    request: Request,
    payload: GoogleOAuthExchangePayload,
    clerk_sub: str = Depends(authenticate_internal),
):
    db_url = request.app.state.database_url
    user_internal_id = await get_or_create_user_id(db_url, clerk_sub)
    try:
        return await exchange_google_oauth_code(
            user_internal_id,
            code=payload.code,
            redirect_uri=payload.redirect_uri,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/threads/{thread_id}/state")
async def get_state(
    thread_id: str,
    request: Request,
    clerk_sub: str = Depends(authenticate_internal),
):
    """SWR polling endpoint. Returns current processing status and persisted messages."""
    db_url = request.app.state.database_url
    user_internal_id = await get_or_create_user_id(db_url, clerk_sub)
    try:
        payload = await get_thread_state(db_url, thread_id, user_internal_id)
        if payload.get("stale"):
            logger.warning(
                "thread_run_stale thread=%s user=%s active=%s updated_at=%s",
                thread_id,
                user_internal_id,
                payload.get("active_agent"),
                payload.get("updated_at"),
            )
        return payload
    except ThreadAccessError:
        raise HTTPException(status_code=403, detail="Forbidden") from None


@router.post("/threads/{thread_id}/approve")
async def approve_tool(
    thread_id: str,
    payload: ApprovalPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    clerk_sub: str = Depends(authenticate_internal),
):
    """Executes or rejects a pending approval-gated tool call."""
    db_url = request.app.state.database_url
    user_internal_id = await get_or_create_user_id(db_url, clerk_sub)
    decision = payload.decision

    try:
        approval = await resolve_pending_approval(db_url, thread_id, user_internal_id, decision)
    except ThreadAccessError:
        raise HTTPException(status_code=403, detail="Forbidden") from None

    if approval is None:
        return {"status": "noop", "detail": "No pending approval found."}

    if decision == "REJECTED":
        try:
            await append_message(
                db_url,
                thread_id,
                user_internal_id,
                "assistant",
                f"Action rejected. `{approval['tool_name']}` was not executed.",
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
                "approval_rejected",
                thread_id=thread_id,
                user_internal_id=user_internal_id,
                extra={"tool_name": approval["tool_name"], "approval_gate_id": approval["id"]},
            )
        except ThreadAccessError:
            raise HTTPException(status_code=403, detail="Forbidden") from None
        return {"status": "rejected"}

    try:
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
    except ThreadAccessError:
        raise HTTPException(status_code=403, detail="Forbidden") from None

    async def finalize_approved_action():
        try:
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("finalize_approved_action failed thread=%s", thread_id)
            try:
                await append_message(
                    db_url,
                    thread_id,
                    user_internal_id,
                    "assistant",
                    f"Approved action failed: {exc}",
                )
                await set_run_state(
                    db_url,
                    thread_id,
                    user_internal_id,
                    status="error",
                    pending_approval=False,
                    approval_gate_id=None,
                    last_error=str(exc),
                )
                _log_run_event(
                    "approved_action_failed",
                    thread_id=thread_id,
                    user_internal_id=user_internal_id,
                    extra={"tool_name": approval["tool_name"], "approval_gate_id": approval["id"], "error": str(exc)},
                )
            except ThreadAccessError:
                logger.warning("finalize_approved_action could not persist error for thread=%s", thread_id)

    background_tasks.add_task(finalize_approved_action)
    return {"status": "resumed"}
