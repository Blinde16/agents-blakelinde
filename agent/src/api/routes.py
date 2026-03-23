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
from src.orchestration.router import RouteDecision, route_message
from src.orchestration.state import (
    ThreadAccessError,
    append_message,
    create_thread_state,
    get_or_create_user_id,
    get_pending_approval,
    get_recent_messages,
    get_thread_state,
    resolve_pending_approval,
    set_run_state,
)
from src.tools.finance_staging import ingest_user_spreadsheet
from src.tools.google_workspace import upsert_user_google_credentials
from src.tools.notion_calendar import upsert_user_notion_credentials
from src.tools.registry import execute_mutating_tool
from src.tools.schemas import GoogleCredentialsPayload, NotionCredentialsPayload

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


async def async_run_agent_stream(
    request: Request,
    thread_id: str,
    message: str,
    user_internal_id: str,
):
    """Runs the specialist with Agno streaming; emits SSE `data:` JSON lines.

    Emits a status line before intent classification so the client is not idle while the LLM router runs.
    """
    yield _sse_data_line({"type": "status", "text": "Classifying intent…"})
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
        return StreamingResponse(
            async_run_agent_stream(request, thread_id, payload.message, user_internal_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )

    route = await route_message(payload.message)

    try:
        await append_message(db_url, thread_id, user_internal_id, "user", payload.message)
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
    except ThreadAccessError:
        raise HTTPException(status_code=403, detail="Forbidden") from None

    background_tasks.add_task(
        async_run_agent,
        request,
        thread_id,
        payload.message,
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
        return await get_thread_state(db_url, thread_id, user_internal_id)
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
    except ThreadAccessError:
        raise HTTPException(status_code=403, detail="Forbidden") from None

    async def finalize_approved_action():
        try:
            result = await execute_mutating_tool(approval["tool_name"], approval["payload"])
            await append_message(db_url, thread_id, user_internal_id, "assistant", result)
            await set_run_state(
                db_url,
                thread_id,
                user_internal_id,
                status="completed",
                pending_approval=False,
                approval_gate_id=None,
                last_error=None,
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
            except ThreadAccessError:
                logger.warning("finalize_approved_action could not persist error for thread=%s", thread_id)

    background_tasks.add_task(finalize_approved_action)
    return {"status": "resumed"}
