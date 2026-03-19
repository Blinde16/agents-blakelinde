from .finance import cfo_tools
from .hubspot import cro_tools
from .notion import cmo_tools

# Generic utilities for Ops
import datetime

async def get_current_time() -> str:
    """Read-only utility. Returns current system time in UTC."""
    return datetime.datetime.now(datetime.UTC).isoformat()

ops_tools = [get_current_time]

# A central registry to identify state-mutating tools that require Human-In-The-Loop pauses.
# Every tool name exactly matches the @tool("name") in the decorators above.
TOOLS_REQUIRING_APPROVAL = {
    "hubspot_update_deal_stage"
}

def requires_approval(tool_name: str) -> bool:
    """Evaluates if a requested tool execution must be paused for human approval."""
    return tool_name in TOOLS_REQUIRING_APPROVAL
