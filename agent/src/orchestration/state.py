import json
import logging
from typing import Any, Optional
from uuid import uuid4

import asyncpg
import psycopg2

logger = logging.getLogger(__name__)


class ThreadAccessError(Exception):
    """Raised when a thread is missing or not owned by the authenticated user."""


def initialize_runtime_tables(db_url: str) -> None:
    connection = psycopg2.connect(db_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.thread_runs (
                    thread_id UUID PRIMARY KEY REFERENCES public.threads(id) ON DELETE CASCADE,
                    status TEXT NOT NULL DEFAULT 'idle',
                    active_agent TEXT,
                    pending_approval BOOLEAN NOT NULL DEFAULT FALSE,
                    approval_gate_id UUID,
                    last_error TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.thread_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    thread_id UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            except Exception as exc:  # noqa: BLE001
                logger.warning("vector extension: %s", exc)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.knowledge_chunks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    embedding vector(1536),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.finance_client_metrics (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    client_key TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    margin_pct NUMERIC NOT NULL,
                    revenue_ytd NUMERIC NOT NULL DEFAULT 0,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.finance_revenue_totals (
                    timeframe TEXT PRIMARY KEY,
                    total_revenue NUMERIC NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                INSERT INTO public.finance_client_metrics (client_key, display_name, margin_pct, revenue_ytd)
                VALUES
                    ('acme', 'Acme Corp', 68.5, 45000),
                    ('contoso', 'Contoso Ltd', 42.0, 120000)
                ON CONFLICT (client_key) DO NOTHING;
                """
            )
            cursor.execute(
                """
                INSERT INTO public.finance_revenue_totals (timeframe, total_revenue)
                VALUES ('YTD', 1250000), ('Q1', 310000), ('LAST_MONTH', 98000)
                ON CONFLICT (timeframe) DO NOTHING;
                """
            )
    finally:
        connection.close()


async def _connect(db_url: str) -> asyncpg.Connection:
    return await asyncpg.connect(db_url)


async def get_or_create_user_id(db_url: str, clerk_user_id: str) -> str:
    """Returns internal public.users.id as string for the given Clerk subject."""
    connection = await _connect(db_url)
    try:
        row = await connection.fetchrow(
            """
            INSERT INTO public.users (clerk_user_id)
            VALUES ($1)
            ON CONFLICT (clerk_user_id) DO UPDATE
            SET updated_at = NOW()
            RETURNING id::text
            """,
            clerk_user_id,
        )
    finally:
        await connection.close()
    if row is None:
        raise RuntimeError("failed to resolve user")
    return row[0]


async def assert_thread_owned(db_url: str, thread_id: str, user_internal_id: str) -> None:
    connection = await _connect(db_url)
    try:
        row = await connection.fetchrow(
            """
            SELECT 1 AS ok
            FROM public.threads
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            thread_id,
            user_internal_id,
        )
    finally:
        await connection.close()
    if row is None:
        raise ThreadAccessError("Thread not found or access denied")


async def create_thread_state(db_url: str, thread_id: str, user_internal_id: str) -> None:
    connection = await _connect(db_url)
    try:
        await connection.execute(
            """
            INSERT INTO public.threads (id, user_id)
            VALUES ($1::uuid, $2::uuid)
            ON CONFLICT (id) DO NOTHING
            """,
            thread_id,
            user_internal_id,
        )
        await connection.execute(
            """
            INSERT INTO public.thread_runs (thread_id, status, updated_at)
            VALUES ($1::uuid, 'idle', NOW())
            ON CONFLICT (thread_id)
            DO UPDATE SET status = 'idle', updated_at = NOW()
            """,
            thread_id,
        )
    finally:
        await connection.close()


async def append_message(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    role: str,
    content: str,
) -> None:
    await assert_thread_owned(db_url, thread_id, user_internal_id)
    connection = await _connect(db_url)
    try:
        await connection.execute(
            """
            INSERT INTO public.thread_messages (id, thread_id, role, content)
            VALUES ($1::uuid, $2::uuid, $3, $4)
            """,
            str(uuid4()),
            thread_id,
            role,
            content,
        )
    finally:
        await connection.close()


async def set_run_state(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    *,
    status: str,
    active_agent: Optional[str] = None,
    pending_approval: Optional[bool] = None,
    approval_gate_id: Optional[str] = None,
    last_error: Optional[str] = None,
) -> None:
    await assert_thread_owned(db_url, thread_id, user_internal_id)
    connection = await _connect(db_url)
    try:
        await connection.execute(
            """
            INSERT INTO public.thread_runs (
                thread_id,
                status,
                active_agent,
                pending_approval,
                approval_gate_id,
                last_error,
                updated_at
            )
            VALUES (
                $1::uuid,
                $2,
                $3,
                COALESCE($4, FALSE),
                $5::uuid,
                $6,
                NOW()
            )
            ON CONFLICT (thread_id)
            DO UPDATE SET
                status = EXCLUDED.status,
                active_agent = COALESCE(EXCLUDED.active_agent, public.thread_runs.active_agent),
                pending_approval = COALESCE($4, public.thread_runs.pending_approval),
                approval_gate_id = $5::uuid,
                last_error = $6,
                updated_at = NOW()
            """,
            thread_id,
            status,
            active_agent,
            pending_approval,
            approval_gate_id,
            last_error,
        )
    finally:
        await connection.close()


async def create_approval_gate(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    tool_name: str,
    payload: dict[str, Any],
) -> str:
    await assert_thread_owned(db_url, thread_id, user_internal_id)
    gate_id = str(uuid4())
    connection = await _connect(db_url)
    try:
        await connection.execute(
            """
            INSERT INTO public.approval_gates (id, thread_id, tool_name, payload, status)
            VALUES ($1::uuid, $2::uuid, $3, $4::jsonb, 'PENDING')
            """,
            gate_id,
            thread_id,
            tool_name,
            json.dumps(payload),
        )
    finally:
        await connection.close()
    return gate_id


async def get_pending_approval(db_url: str, thread_id: str) -> Optional[dict[str, Any]]:
    connection = await _connect(db_url)
    try:
        row = await connection.fetchrow(
            """
            SELECT id, tool_name, payload, status, created_at
            FROM public.approval_gates
            WHERE thread_id = $1::uuid AND status = 'PENDING'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            thread_id,
        )
    finally:
        await connection.close()

    if row is None:
        return None

    return {
        "id": str(row["id"]),
        "tool_name": row["tool_name"],
        "payload": row["payload"],
        "status": row["status"],
    }


async def resolve_pending_approval(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    decision: str,
) -> Optional[dict[str, Any]]:
    await assert_thread_owned(db_url, thread_id, user_internal_id)
    pending = await get_pending_approval(db_url, thread_id)
    if pending is None:
        return None

    connection = await _connect(db_url)
    try:
        await connection.execute(
            """
            UPDATE public.approval_gates
            SET status = $2::approval_status, updated_at = NOW()
            WHERE id = $1::uuid
            """,
            pending["id"],
            decision,
        )
    finally:
        await connection.close()

    pending["status"] = decision
    return pending


async def get_thread_state(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
) -> dict[str, Any]:
    await assert_thread_owned(db_url, thread_id, user_internal_id)
    connection = await _connect(db_url)
    try:
        run_row = await connection.fetchrow(
            """
            SELECT status, active_agent, pending_approval, approval_gate_id, last_error
            FROM public.thread_runs
            WHERE thread_id = $1::uuid
            """,
            thread_id,
        )
        message_rows = await connection.fetch(
            """
            SELECT role, content
            FROM public.thread_messages
            WHERE thread_id = $1::uuid
            ORDER BY created_at ASC, id ASC
            """,
            thread_id,
        )
    finally:
        await connection.close()

    if run_row is None:
        return {"status": "idle", "messages": [], "pending_approval": False}

    pending_approval = bool(run_row["pending_approval"])
    approval_request = await get_pending_approval(db_url, thread_id) if pending_approval else None

    return {
        "status": run_row["status"],
        "active_agent": run_row["active_agent"],
        "pending_approval": pending_approval,
        "approval_request": approval_request,
        "last_error": run_row["last_error"],
        "messages": [{"role": row["role"], "content": row["content"]} for row in message_rows],
    }
