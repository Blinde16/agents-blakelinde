import os
from typing import Optional

from agno.agent import Agent
from agno.memory.agent import AgentMemory
from agno.models.openai import OpenAIChat

from src.prompts.loader import load_prompt
from src.tools.registry import ToolRuntimeContext, build_tools_by_role


def _build_agent(
    *,
    name: str,
    role: str,
    description: str,
    prompt_name: str,
    storage=None,
    memory_db=None,
    tool_context: Optional[ToolRuntimeContext] = None,
) -> Agent:
    tools_by_role = build_tools_by_role(tool_context)
    return Agent(
        name=name,
        role=role,
        model=OpenAIChat(id=os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
        description=description,
        instructions=load_prompt(prompt_name),
        tools=tools_by_role.get(role, []),
        storage=storage,
        memory=AgentMemory(db=memory_db) if memory_db else None,
        add_history_to_messages=True,
        num_history_responses=10,
        tool_call_limit=25,
        show_tool_calls=True,
    )


def build_cfo_agent(
    storage=None,
    memory_db=None,
    tool_context: Optional[ToolRuntimeContext] = None,
) -> Agent:
    """Finance Layer Agent"""
    return _build_agent(
        name="Finance_Layer",
        role="CFO",
        description=(
            "You are the financial reality checkpoint for Blake Linde. "
            "Give exact figures. Do not pad answers. "
            "You handle financial analysis, margin validation, and cash flow tracking. "
            "Never alter CRM records or write public text."
        ),
        storage=storage,
        memory_db=memory_db,
        prompt_name="cfo.md",
        tool_context=tool_context,
    )


def build_cro_agent(
    storage=None,
    memory_db=None,
    tool_context: Optional[ToolRuntimeContext] = None,
) -> Agent:
    """Sales Operations Layer Agent"""
    return _build_agent(
        name="Sales_Ops_Layer",
        role="CRO",
        description=(
            "You are revenue structure. Identify pipeline bottlenecks and enforce CRM hygiene. "
            "You handle deal structuring, outreach systems, and CRM state. "
            "You cannot modify accounting data or approve your own CRM-stage moves."
        ),
        storage=storage,
        memory_db=memory_db,
        prompt_name="cro.md",
        tool_context=tool_context,
    )


def build_cmo_agent(
    storage=None,
    memory_db=None,
    tool_context: Optional[ToolRuntimeContext] = None,
) -> Agent:
    """Brand & Marketing Layer Agent"""
    return _build_agent(
        name="Brand_Layer",
        role="CMO",
        description=(
            "You are brand architecture. Verify all messaging against established guidelines. "
            "Ensure positioning strategy matches the public narrative. "
            "You cannot access financial or pipeline data."
        ),
        storage=storage,
        memory_db=memory_db,
        prompt_name="cmo.md",
        tool_context=tool_context,
    )


def build_ops_agent(
    storage=None,
    memory_db=None,
    tool_context: Optional[ToolRuntimeContext] = None,
) -> Agent:
    """Generalist & Triage Layer Agent"""
    return _build_agent(
        name="Operations_Layer",
        role="Ops",
        description=(
            "You are the primary administrative fallback interface. "
            "If a request is vague, ask exactly one clarifying question. Do not assume. "
            "You handle general task administration and ambiguous routing."
        ),
        storage=storage,
        memory_db=memory_db,
        prompt_name="ops.md",
        tool_context=tool_context,
    )
