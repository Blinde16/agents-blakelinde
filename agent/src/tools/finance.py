"""Read-only finance metrics from Postgres (asyncpg)."""

from __future__ import annotations

import json
from typing import Any

from src.orchestration.db_pool import get_pool
from src.tools.schemas import ClientMarginInput, RevenueSummaryInput


async def get_client_margin(client_name: str, db_url: str) -> str:
    """Read-only. Returns margin and YTD revenue for a client row in finance_client_metrics."""
    try:
        ClientMarginInput(client_name=client_name)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    _ = db_url
    key = client_name.strip().lower()
    try:
        async with get_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT display_name, margin_pct, revenue_ytd
                FROM public.finance_client_metrics
                WHERE LOWER(client_key) = $1
                   OR LOWER(display_name) LIKE $2
                ORDER BY CASE WHEN LOWER(client_key) = $1 THEN 0 ELSE 1 END
                LIMIT 1
                """,
                key,
                f"%{key}%",
            )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "database_error", "detail": str(exc)})

    if row is None:
        return json.dumps({"detail": f"Client {client_name!r} not found in finance_client_metrics."})

    payload: dict[str, Any] = {
        "client": row["display_name"],
        "margin_percentage": float(row["margin_pct"]),
        "total_revenue_ytd": float(row["revenue_ytd"]),
    }
    return json.dumps(payload)


async def get_revenue_summary(timeframe: str, db_url: str) -> str:
    """Read-only. Aggregated revenue for a named period from finance_revenue_totals."""
    try:
        RevenueSummaryInput(timeframe=timeframe)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    _ = db_url
    tf = timeframe.strip().upper()
    try:
        async with get_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT total_revenue
                FROM public.finance_revenue_totals
                WHERE UPPER(timeframe) = $1
                """,
                tf,
            )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "database_error", "detail": str(exc)})

    if row is None:
        return json.dumps({"timeframe": tf, "total_revenue": 0, "detail": "Period not found."})

    return json.dumps({"timeframe": tf, "total_revenue": float(row["total_revenue"])})
