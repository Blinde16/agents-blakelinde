import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from pydantic import BaseModel

from src.agents.builder import build_specialist_agent
from src.api.dependencies import authenticate_internal
from src.orchestration.router import route_message
from src.orchestration.state import (
    ThreadAccessError,
    append_message,
    create_thread_state,
    get_or_create_user_id,
    get_pending_approval,
    get_thread_state,
    resolve_pending_approval,
    set_run_state,
)
from src.tools.registry import execute_mutating_tool

router = APIRouter(prefix="/api")


class MessagePayload(BaseModel):
    message: str


class ApprovalPayload(BaseModel):
    decision: str  # "APPROVED" or "REJECTED"


async def async_run_agent(
    request: Request,
    thread_id: str,
    message: str,
    user_internal_id: str,
):
    db_url = request.app.state.database_url
    agent_storage = request.app.state.agent_storage
    agent_memory = getattr(request.app.state, "agent_memory", None)
    route = route_message(message)

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
        print(f"[ERROR] Agent run error for thread {thread_id}: {exc}")
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


@router.post("/threads")
async def create_thread(request: Request, clerk_sub: str = Depends(authenticate_internal)):
    """Instantiates a new thread with a unique UUID and persistent runtime state."""
    db_url = request.app.state.database_url
    user_internal_id = await get_or_create_user_id(db_url, clerk_sub)
    thread_id = str(uuid.uuid4())
    await create_thread_state(db_url, thread_id, user_internal_id)
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
    route = route_message(payload.message)

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
    )
    return {"status": "processing", "thread_id": thread_id, "active_agent": route.active_agent}


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
    decision = payload.decision.upper()

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

    background_tasks.add_task(finalize_approved_action)
    return {"status": "resumed"}
