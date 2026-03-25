from dataclasses import dataclass
from typing import Optional

from src.tools.sync_run import run_sync_tool

from src.orchestration.state import create_approval_gate

from .finance import get_client_margin, get_revenue_summary
from .finance_staging import query_staging_metrics, summarize_sheet
from .notion_calendar import (
    build_notion_cmo_tools,
    execute_notion_create_calendar_entry,
    execute_notion_update_calendar_entry,
)
from .google_workspace import (
    build_google_ops_tools,
    execute_create_calendar_event,
    execute_delete_calendar_event,
    execute_modify_email_labels,
    execute_send_email,
    execute_trash_message,
    execute_update_calendar_event,
)
from .hubspot import cro_tools, execute_hubspot_update_deal_stage
from .social import build_social_cmo_tools, execute_publish_social_post
from .schemas import BrandKnowledgeInput, HubSpotUpdateDealStageInput
from src.rag.knowledge_search import search_brand_knowledge as rag_search_brand_knowledge

import datetime


@dataclass(frozen=True)
class ToolRuntimeContext:
    thread_id: str
    db_url: str
    user_internal_id: str


def get_current_time() -> str:
    """Read-only utility. Returns current system time in UTC.

    Must be synchronous: Agno executes tools in a sync path; ``async def`` tools
    leak a coroutine into message content (see sync_run.py).
    """
    return datetime.datetime.now(datetime.UTC).isoformat()


# State-mutating tools that require Human-In-The-Loop pauses.
TOOLS_REQUIRING_APPROVAL = {
    "hubspot_update_deal_stage",
    "notion_create_calendar_entry",
    "notion_update_calendar_entry",
    "send_email",
    "create_calendar_event",
    "trash_email",
    "modify_email_labels",
    "update_calendar_event",
    "delete_calendar_event",
    "publish_social_post",
}


def requires_approval(tool_name: str) -> bool:
    return tool_name in TOOLS_REQUIRING_APPROVAL


def build_ops_tools(context: Optional[ToolRuntimeContext] = None):
    if context is None:
        return [get_current_time]
    return [get_current_time, *build_google_ops_tools(context)]


def build_cfo_tools(context: ToolRuntimeContext):
    def get_client_margin_tool(client_name: str) -> str:
        return run_sync_tool(get_client_margin(client_name, context.db_url))

    def get_revenue_summary_tool(timeframe: str) -> str:
        return run_sync_tool(get_revenue_summary(timeframe, context.db_url))

    def query_staging_metrics_tool(upload_id: str, limit: int = 50, offset: int = 0) -> str:
        return run_sync_tool(query_staging_metrics(upload_id, context.user_internal_id, limit, offset))

    def summarize_sheet_tool(upload_id: str) -> str:
        return run_sync_tool(summarize_sheet(upload_id, context.user_internal_id))

    get_client_margin_tool.__name__ = "get_client_margin"
    get_revenue_summary_tool.__name__ = "get_revenue_summary"
    query_staging_metrics_tool.__name__ = "query_staging_metrics"
    summarize_sheet_tool.__name__ = "summarize_sheet"
    return [
        get_client_margin_tool,
        get_revenue_summary_tool,
        query_staging_metrics_tool,
        summarize_sheet_tool,
    ]


def build_cmo_tools(context: ToolRuntimeContext):
    def search_brand_knowledge(query: str) -> str:
        try:
            BrandKnowledgeInput(query=query)
        except Exception as exc:  # noqa: BLE001
            return f"validation_error: {exc}"
        return run_sync_tool(rag_search_brand_knowledge(context.db_url, query))

    search_brand_knowledge.__name__ = "search_brand_knowledge"
    return [
        search_brand_knowledge,
        *build_notion_cmo_tools(context),
        *build_social_cmo_tools(context),
    ]


def build_cro_tools(context: ToolRuntimeContext):
    async def _hubspot_update_deal_stage_async(deal_id: str, new_stage: str) -> str:
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

    def hubspot_update_deal_stage(deal_id: str, new_stage: str) -> str:
        return run_sync_tool(_hubspot_update_deal_stage_async(deal_id, new_stage))

    hubspot_update_deal_stage.__name__ = "hubspot_update_deal_stage"
    return [*cro_tools, hubspot_update_deal_stage]


def build_tools_by_role(context: Optional[ToolRuntimeContext] = None) -> dict[str, list]:
    if context is None:
        return {
            "CFO": [],
            "CRO": cro_tools,
            "CMO": [],
            "Ops": build_ops_tools(None),
            "OPS": build_ops_tools(None),
        }
    return {
        "CFO": build_cfo_tools(context),
        "CRO": build_cro_tools(context),
        "CMO": build_cmo_tools(context),
        "Ops": build_ops_tools(context),
        "OPS": build_ops_tools(context),
    }


EXECUTABLE_MUTATING_TOOLS = {
    "hubspot_update_deal_stage": execute_hubspot_update_deal_stage,
    "notion_create_calendar_entry": execute_notion_create_calendar_entry,
    "notion_update_calendar_entry": execute_notion_update_calendar_entry,
    "send_email": execute_send_email,
    "create_calendar_event": execute_create_calendar_event,
    "trash_email": execute_trash_message,
    "modify_email_labels": execute_modify_email_labels,
    "update_calendar_event": execute_update_calendar_event,
    "delete_calendar_event": execute_delete_calendar_event,
    "publish_social_post": execute_publish_social_post,
}


async def execute_mutating_tool(tool_name: str, payload: dict):
    tool = EXECUTABLE_MUTATING_TOOLS.get(tool_name)
    if tool is None:
        raise ValueError(f"Unknown mutating tool: {tool_name!r}")
    return await tool(**payload)
