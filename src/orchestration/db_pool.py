"""Shared asyncpg pool for runtime queries (avoids connect/disconnect per call)."""

from __future__ import annotations

import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def init_pool(dsn: str | None = None) -> asyncpg.Pool:
    """Create the global pool once. Call from FastAPI lifespan."""
    global _pool
    if _pool is not None:
        return _pool
    url = dsn or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    _pool = await asyncpg.create_pool(
        url,
        min_size=int(os.getenv("PG_POOL_MIN", "1")),
        max_size=int(os.getenv("PG_POOL_MAX", "12")),
        command_timeout=float(os.getenv("PG_POOL_COMMAND_TIMEOUT", "120")),
    )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized; call init_pool from app lifespan")
    return _pool

async def run_with_pool(coro):
    await init_pool()
    try:
        return await coro
    finally:
        await close_pool()
