import os
from agno.agent import Agent
from agno.memory.agent import AgentMemory
from agno.models.openai import OpenAIChat

from src.tools.cmo_tools import cmo_tools


def build_cmo_agent(memory_db=None, storage=None) -> Agent:
    """
    CMO Agent — Chief Marketing Officer functional layer.

    Responsibilities:
    - Generate and maintain the content calendar across all brand platforms
    - Draft platform-specific copy aligned to brand guidelines
    - Write calendar entries to Notion
    - Surface daily posting reminders
    - Enforce brand voice and messaging standards

    Platforms covered:
    - Blake LinkedIn (personal professional brand)
    - X / Blake personal
    - SB Photography — Instagram + Meta
    - CV Business Stack — LinkedIn, X, Meta
    """
    model_id = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    agent = Agent(
        name="CMO_Agent",
        model=OpenAIChat(id=model_id),
        description=(
            "You are the CMO agent for Blake Linde. "
            "You own the content calendar and brand voice across all of Blake's platforms: "
            "Blake LinkedIn, X (personal), SB Photography (Instagram + Meta), "
            "and the CV Business Stack (LinkedIn, X, Meta). "
            "You are direct, data-focused, and professional. "
            "You never use exclamation points. You never produce filler preamble. "
            "When asked to create a content calendar, you call generate_content_calendar(), "
            "then write it to Notion with write_calendar_to_notion(). "
            "When asked what to post today, you call get_todays_posting_reminders(). "
            "When drafting copy, you call draft_post_copy() for the brief, then write the post. "
            "All brand decisions are anchored in read_notion_brand_guidelines(). "
            "You do not invent brand rules — if it's not in the guidelines, you say it's undefined."
        ),
        tools=cmo_tools,
        memory=AgentMemory(db=memory_db) if memory_db else None,
        storage=storage,
        show_tool_calls=True,
        add_history_to_messages=True,
        num_history_responses=10,
    )

    return agent


def build_lead_router_agent(memory_db=None, storage=None) -> Agent:
    """
    Lead Router Agent — primary entry point.

    Routes requests to the appropriate specialist agent or answers directly
    for general operational queries. CMO requests (content, calendar, posting,
    brand, copy) are handled by the CMO agent.

    MVP note: Specialist delegation is wired for CMO. CFO/CRO/Ops delegation
    will be added as those agents are built out.
    """
    model_id = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    cmo_agent = build_cmo_agent(memory_db=memory_db, storage=storage)

    agent = Agent(
        name="Lead_Router_Agent",
        model=OpenAIChat(id=model_id),
        description=(
            "You are the primary operations agent for Blake Linde. "
            "You are direct, data-focused, and professional. "
            "You assist with business analysis, pipeline management, financial queries, and operational tasks. "
            "For all content, marketing, brand, social media, or content calendar requests, "
            "delegate immediately to your CMO agent. "
            "When you cannot complete a task without external data, you clearly state what information you need."
        ),
        team=[cmo_agent],
        memory=AgentMemory(db=memory_db) if memory_db else None,
        storage=storage,
        show_tool_calls=True,
        add_history_to_messages=True,
        num_history_responses=10,
    )

    return agent
