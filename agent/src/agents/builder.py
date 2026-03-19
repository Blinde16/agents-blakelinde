import os
from agno.agent import Agent
from agno.memory.agent import AgentMemory
from agno.models.openai import OpenAIChat


def build_lead_router_agent(memory_db=None, storage=None) -> Agent:
    """
    MVP: Single Lead Router Agent.
    No specialist team delegation yet — the agent answers directly.
    This isolates the core Agno + OpenAI + Postgres loop for first-pass testing.

    To add specialist delegation later, re-introduce the team=[...] parameter
    and import the specialist builder functions from this same file.
    """
    model_id = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    agent = Agent(
        name="Lead_Router_Agent",
        model=OpenAIChat(id=model_id),
        description=(
            "You are the primary operations agent for Blake Linde. "
            "You are direct, data-focused, and professional. "
            "You assist with business analysis, pipeline management, financial queries, and operational tasks. "
            "When you cannot complete a task without external data, you clearly state what information you would need."
        ),
        memory=AgentMemory(db=memory_db) if memory_db else None,
        storage=storage,
        show_tool_calls=True,
        # Enable Agno's built-in session memory so the agent recalls prior messages
        add_history_to_messages=True,
        num_history_responses=10,
    )

    return agent
