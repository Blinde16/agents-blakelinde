"""Helpers for Agno/LangChain tool entrypoints."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Coroutine
from typing import Any, Optional, TypeVar

T = TypeVar("T")

_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Register the FastAPI/uvicorn loop so sync tool wrappers can schedule async work safely."""
    global _main_loop
    _main_loop = loop


def run_sync_tool(coro: Coroutine[Any, Any, T]) -> T:
    """Run *coro* without leaking a coroutine into Agno message content.

    ``Function.from_callable`` wraps tools with Pydantic ``validate_call``, which makes
    ``inspect.iscoroutinefunction`` false for async callables while ``__call__`` still returns a
    coroutine. Agno's synchronous :meth:`agno.tools.function.FunctionCall.execute` then assigns
    that coroutine to ``result`` without awaiting. Sync ``def`` tools that delegate here avoid that.

    Agno executes sync tools via ``asyncio.to_thread``. Using :func:`asyncio.run` inside that
    thread would create a **new** event loop and break ``asyncpg`` (pool is bound to the app loop).
    When the app loop is registered, coroutines are run with :func:`asyncio.run_coroutine_threadsafe`
    on that loop instead.
    """
    timeout = float(os.getenv("TOOL_SYNC_TIMEOUT", "120"))
    if _main_loop is not None:
        fut = asyncio.run_coroutine_threadsafe(coro, _main_loop)
        return fut.result(timeout=timeout)
    return asyncio.run(coro)
