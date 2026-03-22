import os
from typing import Optional

from agno.agent import Agent
from agno.memory.agent import AgentMemory
from agno.models.openai import OpenAIChat

from src.orchestration.router import RouteTarget
from src.prompts.loader import load_prompt
from src.agents.specialists import (
    build_cfo_agent,
    build_cro_agent,
    build_cmo_agent,
    build_ops_agent,
)
from src.tools.registry import ToolRuntimeContext


def build_lead_router_agent(memory_db=None, storage=None) -> Agent:
    """
    Lead Router Agent.
    Delegates user tasks to the specialized functional layers (CFO, CRO, CMO, Ops)
    based on the routing strategy defined in AGENT_DESIGN.md.
    """
    model_id = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    cfo = build_cfo_agent(storage=storage, memory_db=memory_db, tool_context=None)
    cro = build_cro_agent(storage=storage, memory_db=memory_db, tool_context=None)
    cmo = build_cmo_agent(storage=storage, memory_db=memory_db, tool_context=None)
    ops = build_ops_agent(storage=storage, memory_db=memory_db, tool_context=None)

    agent = Agent(
        name="Lead_Router_Agent",
        model=OpenAIChat(id=model_id),
        description=(
            "You are the primary operations agent for Blake Linde. "
            "You are direct, data-focused, and professional. "
            "You assist with business analysis, pipeline management, financial queries, and operational tasks. "
            "When you cannot complete a task without external data, you clearly state what information you would need. "
            "Always delegate tasks to the appropriate team member if they match the required functional role."
        ),
        instructions=load_prompt("ops.md"),
        team=[cfo, cro, cmo, ops],
        memory=AgentMemory(db=memory_db) if memory_db else None,
        storage=storage,
        show_tool_calls=True,
        add_history_to_messages=True,
        num_history_responses=10,
        tool_call_limit=25,
    )

    return agent


def build_specialist_agent(
    target: RouteTarget,
    *,
    thread_id: str,
    db_url: str,
    user_internal_id: str,
    storage=None,
    memory_db: Optional[object] = None,
) -> Agent:
    tool_context = ToolRuntimeContext(
        thread_id=thread_id,
        db_url=db_url,
        user_internal_id=user_internal_id,
    )

    if target == "CFO":
        return build_cfo_agent(storage=storage, memory_db=memory_db, tool_context=tool_context)
    if target == "CRO":
        return build_cro_agent(storage=storage, memory_db=memory_db, tool_context=tool_context)
    if target == "CMO":
        return build_cmo_agent(storage=storage, memory_db=memory_db, tool_context=tool_context)
    return build_ops_agent(storage=storage, memory_db=memory_db, tool_context=tool_context)
