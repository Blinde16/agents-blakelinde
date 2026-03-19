import uuid
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel

from src.api.dependencies import verify_internal_token
from src.agents.builder import build_lead_router_agent

router = APIRouter(prefix="/api", dependencies=[Depends(verify_internal_token)])

# In-memory dict to store the latest agent response per thread.
# For MVP polling: the background task writes here, the state endpoint reads here.
# This is intentionally simple — replace with a Postgres-backed status table post-MVP.
_thread_responses: dict[str, dict] = {}


class MessagePayload(BaseModel):
    message: str


class ApprovalPayload(BaseModel):
    decision: str  # "APPROVED" or "REJECTED"


async def async_run_agent(request: Request, thread_id: str, message: str):
    """
    Executes the Agno Agent operation in an asyncio background task.
    Returns 202 Accepted instantly to Next.js while this runs in the background.
    Writes the output into _thread_responses so the polling endpoint can serve it.
    """
    agent_memory = request.app.state.agent_memory
    agent_storage = request.app.state.agent_storage

    agent = build_lead_router_agent(memory_db=agent_memory, storage=agent_storage)

    # Mark this thread as actively processing
    _thread_responses[thread_id] = {"status": "processing", "messages": [], "pending_approval": False}

    try:
        # Agno arun: pass session_id so the memory/storage adapters scope to this thread
        response = await agent.arun(message, session_id=thread_id)

        # Extract the agent's text response
        agent_text = ""
        if hasattr(response, "content"):
            agent_text = response.content or ""
        elif isinstance(response, str):
            agent_text = response

        # Update the in-memory store so SWR polling can pick it up
        _thread_responses[thread_id] = {
            "status": "completed",
            "messages": [
                {"role": "user", "content": message},
                {"role": "assistant", "content": agent_text},
            ],
            "pending_approval": False,
        }

    except Exception as e:
        print(f"[ERROR] Agent run error for thread {thread_id}: {e}")
        _thread_responses[thread_id] = {
            "status": "error",
            "messages": [{"role": "assistant", "content": f"Agent error: {str(e)}"}],
            "pending_approval": False,
        }


@router.post("/threads")
async def create_thread():
    """Instantiates a new thread with a unique UUID. Stored in memory until first message."""
    thread_id = str(uuid.uuid4())
    _thread_responses[thread_id] = {"status": "idle", "messages": [], "pending_approval": False}
    return {"thread_id": thread_id}


@router.post("/threads/{thread_id}/messages")
async def push_message(
    thread_id: str,
    payload: MessagePayload,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Accepts a user message and fires agent execution as a background task."""
    background_tasks.add_task(async_run_agent, request, thread_id, payload.message)
    return {"status": "processing", "thread_id": thread_id}


@router.get("/threads/{thread_id}/state")
async def get_state(thread_id: str):
    """
    SWR polling endpoint. Returns current processing status and latest messages.
    The frontend polls this at a 1.5s interval until status = 'completed'.
    """
    state = _thread_responses.get(thread_id)

    if not state:
        return {"status": "idle", "messages": [], "pending_approval": False}

    return state


@router.post("/threads/{thread_id}/approve")
async def approve_tool(
    thread_id: str,
    payload: ApprovalPayload,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Resumes a paused execution after human approval/rejection of a tool call."""
    resume_message = (
        f"SYSTEM: The user has {payload.decision} the pending tool call. Please proceed accordingly."
    )
    background_tasks.add_task(async_run_agent, request, thread_id, resume_message)
    return {"status": "resumed"}
