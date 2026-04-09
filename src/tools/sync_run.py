import asyncio

def run_sync_tool(coro):
    return asyncio.run(coro)
