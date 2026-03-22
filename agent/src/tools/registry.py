from dataclasses import dataclass
from typing import Optional

from src.orchestration.state import create_approval_gate

from .finance import get_client_margin, get_revenue_summary
from .hubspot import cro_tools, execute_hubspot_update_deal_stage
from .schemas import BrandKnowledgeInput, HubSpotUpdateDealStageInput
from src.rag.knowledge_search import search_brand_knowledge as rag_search_brand_knowledge

import datetime


@dataclass(frozen=True)
class ToolRuntimeContext:
    thread_id: str
    db_url: str
    user_internal_id: str


async def get_current_time() -> str:
    """Read-only utility. Returns current system time in UTC."""
    return datetime.datetime.now(datetime.UTC).isoformat()


ops_tools = [get_current_time]

# State-mutating tools that require Human-In-The-Loop pauses.
TOOLS_REQUIRING_APPROVAL = {
    "hubspot_update_deal_stage",
}


def requires_approval(tool_name: str) -> bool:
    return tool_name in TOOLS_REQUIRING_APPROVAL


def build_cfo_tools(context: ToolRuntimeContext):
    async def get_client_margin_tool(client_name: str) -> str:
        return await get_client_margin(client_name, context.db_url)

    async def get_revenue_summary_tool(timeframe: str) -> str:
        return await get_revenue_summary(timeframe, context.db_url)

    get_client_margin_tool.__name__ = "get_client_margin"
    get_revenue_summary_tool.__name__ = "get_revenue_summary"
    return [get_client_margin_tool, get_revenue_summary_tool]


def build_cmo_tools(context: ToolRuntimeContext):
    async def search_brand_knowledge(query: str) -> str:
        try:
            BrandKnowledgeInput(query=query)
        except Exception as exc:  # noqa: BLE001
            return f"validation_error: {exc}"
        return await rag_search_brand_knowledge(context.db_url, query)

    search_brand_knowledge.__name__ = "search_brand_knowledge"
    return [search_brand_knowledge]


def build_cro_tools(context: ToolRuntimeContext):
    async def hubspot_update_deal_stage(deal_id: str, new_stage: str) -> str:
        try:
            HubSpotUpdateDealStageInput(deal_id=deal_id, new_stage=new_stage)
        except Exception as exc:  # noqa: BLE001
            return f"validation_error: {exc}"
        await create_approval_gate(
            context.db_url,
            context.thread_id,
            context.user_internal_id,
            "hubspot_update_deal_stage",
            {"deal_id": deal_id, "new_stage": new_stage},
        )
        return (
            "Approval required. The requested HubSpot stage update has been queued "
            "for human review before execution."
        )

    hubspot_update_deal_stage.__name__ = "hubspot_update_deal_stage"
    return [*cro_tools, hubspot_update_deal_stage]


def build_tools_by_role(context: Optional[ToolRuntimeContext] = None) -> dict[str, list]:
    if context is None:
        return {
            "CFO": [],
            "CRO": cro_tools,
            "CMO": [],
            "Ops": ops_tools,
            "OPS": ops_tools,
        }
    return {
        "CFO": build_cfo_tools(context),
        "CRO": build_cro_tools(context),
        "CMO": build_cmo_tools(context),
        "Ops": ops_tools,
        "OPS": ops_tools,
    }


EXECUTABLE_MUTATING_TOOLS = {
    "hubspot_update_deal_stage": execute_hubspot_update_deal_stage,
}


async def execute_mutating_tool(tool_name: str, payload: dict):
    tool = EXECUTABLE_MUTATING_TOOLS[tool_name]
    return await tool(**payload)
