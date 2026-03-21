"""
MCP Server — Blake Linde Agents
================================
Exposes the CMO agent tools as an MCP server so you can connect directly
from Claude.ai desktop app or ChatGPT (via custom connector).

USAGE
-----
# Mode 1: stdio (Claude desktop app — recommended)
  python mcp_server.py

# Mode 2: HTTP/SSE (remote connections, ChatGPT, etc.)
  python mcp_server.py --http [--port 8001]

CONNECTING FROM CLAUDE DESKTOP
-------------------------------
Add to ~/Library/Application Support/Claude/claude_desktop_config.json:

  {
    "mcpServers": {
      "blake-agents": {
        "command": "python",
        "args": ["/absolute/path/to/agent/mcp_server.py"],
        "env": {
          "OPENAI_API_KEY": "sk-...",
          "NOTION_API_KEY": "secret_...",
          "NOTION_CONTENT_CALENDAR_DB_ID": "...",
          "NOTION_BRAND_GUIDELINES_DB_ID": "..."
        }
      }
    }
  }

CONNECTING VIA HTTP (remote)
----------------------------
Run the server: python mcp_server.py --http --port 8001
Connect to:     http://your-server:8001/sse
Auth header:    x-api-key: <MCP_API_KEY env var>
"""

import os
import sys
import asyncio

# Ensure src/ is importable when running as a standalone script
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP

from src.tools.cmo_tools import (
    generate_content_calendar,
    draft_post_copy,
    write_calendar_to_notion,
    get_todays_posting_reminders,
    read_notion_brand_guidelines,
)

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Blake Linde — CMO Agent",
    instructions=(
        "You are connected to Blake Linde's CMO agent. "
        "You can generate content calendars, draft platform-specific copy, "
        "write to Notion, and surface daily posting reminders. "
        "Platforms: Blake LinkedIn, X, SB Photography (Instagram + Meta), "
        "CV Business Stack (LinkedIn, X, Meta). "
        "All outputs follow strict brand rules: direct, data-focused, no exclamation points, "
        "no filler preamble, specific numbers over vague claims."
    ),
)

# Register CMO tools — docstrings become tool descriptions, type hints become parameters
mcp.tool()(generate_content_calendar)
mcp.tool()(draft_post_copy)
mcp.tool()(write_calendar_to_notion)
mcp.tool()(get_todays_posting_reminders)
mcp.tool()(read_notion_brand_guidelines)

# ---------------------------------------------------------------------------
# HTTP mode: API key validation middleware
# ---------------------------------------------------------------------------

def _build_http_app_with_auth():
    """Wraps the FastMCP Starlette app with an API key check."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response

    MCP_API_KEY = os.getenv("MCP_API_KEY")

    class APIKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            # Health check passthrough (for Railway/Render probes)
            if request.url.path in ("/health", "/"):
                return await call_next(request)

            if MCP_API_KEY:
                provided = (
                    request.headers.get("x-api-key")
                    or request.query_params.get("api_key")
                )
                if provided != MCP_API_KEY:
                    return Response(
                        content='{"error":"Unauthorized — provide x-api-key header or api_key query param"}',
                        status_code=401,
                        media_type="application/json",
                    )
            return await call_next(request)

    app = mcp.sse_app()
    app.add_middleware(APIKeyMiddleware)
    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]
    use_http = "--http" in args

    # Parse optional --port flag
    port = 8001
    if "--port" in args:
        try:
            port = int(args[args.index("--port") + 1])
        except (ValueError, IndexError):
            pass

    if use_http:
        import uvicorn

        MCP_API_KEY = os.getenv("MCP_API_KEY")
        key_status = "API key required (MCP_API_KEY)" if MCP_API_KEY else "WARNING: No MCP_API_KEY set — server is open"

        print(f"[MCP] Starting HTTP/SSE server on port {port}")
        print(f"[MCP] {key_status}")
        print(f"[MCP] SSE endpoint: http://0.0.0.0:{port}/sse")

        app = _build_http_app_with_auth()
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        # stdio mode — for Claude desktop local connection
        mcp.run(transport="stdio")
