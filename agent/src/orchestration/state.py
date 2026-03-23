import json
import logging
from typing import Any, Optional
from uuid import uuid4

import psycopg2

from src.orchestration.db_pool import get_pool

logger = logging.getLogger(__name__)


class ThreadAccessError(Exception):
    """Raised when a thread is missing or not owned by the authenticated user."""


def initialize_runtime_tables(db_url: str) -> None:
    connection = psycopg2.connect(db_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            # Core tables (match supabase/migrations/001_initial_schema.sql) — must exist before FKs.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    clerk_user_id TEXT NOT NULL UNIQUE,
                    tenant_id UUID,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.threads (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
                    title TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                DO $$ BEGIN
                    CREATE TYPE approval_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.approval_gates (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    thread_id UUID REFERENCES public.threads(id) ON DELETE CASCADE,
                    tool_name TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    status approval_status DEFAULT 'PENDING',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
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
                CREATE TABLE IF NOT EXISTS public.finance_sheet_staging (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
                    upload_id UUID NOT NULL,
                    filename TEXT NOT NULL,
                    row_index INT NOT NULL,
                    row_payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_finance_staging_user_upload
                    ON public.finance_sheet_staging (user_id, upload_id);
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_finance_staging_upload_row
                    ON public.finance_sheet_staging (upload_id, row_index);
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.user_notion_credentials (
                    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
                    token_cipher TEXT NOT NULL,
                    content_database_id TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.user_google_credentials (
                    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
                    refresh_token_cipher TEXT NOT NULL,
                    google_email TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.social_media_posts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
                    platform TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    scheduled_at TIMESTAMPTZ,
                    published_at TIMESTAMPTZ,
                    external_post_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT social_media_posts_status_check CHECK (
                        status IN ('draft', 'scheduled', 'published', 'cancelled')
                    )
                );
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_social_posts_user_status
                    ON public.social_media_posts (user_id, status);
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


async def get_or_create_user_id(db_url: str, clerk_user_id: str) -> str:
    """Returns internal public.users.id as string for the given Clerk subject."""
    _ = db_url
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO public.users (clerk_user_id)
            VALUES ($1)
            ON CONFLICT (clerk_user_id) DO UPDATE
            SET updated_at = NOW()
            RETURNING id::text
            """,
            clerk_user_id,
        )
    if row is None:
        raise RuntimeError("failed to resolve user")
    return row[0]


async def create_thread_state(db_url: str, thread_id: str, user_internal_id: str) -> None:
    _ = db_url
    async with get_pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO public.threads (id, user_id)
            VALUES ($1::uuid, $2::uuid)
            ON CONFLICT (id) DO NOTHING
            """,
            thread_id,
            user_internal_id,
        )
        await conn.execute(
            """
            INSERT INTO public.thread_runs (thread_id, status, updated_at)
            VALUES ($1::uuid, 'idle', NOW())
            ON CONFLICT (thread_id)
            DO UPDATE SET status = 'idle', updated_at = NOW()
            """,
            thread_id,
        )


async def append_message(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    role: str,
    content: str,
) -> None:
    _ = db_url
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO public.thread_messages (id, thread_id, role, content)
            SELECT $1::uuid, $2::uuid, $3, $4
            WHERE EXISTS (
                SELECT 1 FROM public.threads
                WHERE id = $2::uuid AND user_id = $5::uuid
            )
            RETURNING id
            """,
            str(uuid4()),
            thread_id,
            role,
            content,
            user_internal_id,
        )
    if row is None:
        raise ThreadAccessError("Thread not found or access denied")


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
    _ = db_url
    async with get_pool().acquire() as conn:
        own = await conn.fetchrow(
            """
            SELECT 1 AS ok FROM public.threads
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            thread_id,
            user_internal_id,
        )
        if own is None:
            raise ThreadAccessError("Thread not found or access denied")
        await conn.execute(
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


async def create_approval_gate(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    tool_name: str,
    payload: dict[str, Any],
) -> str:
    _ = db_url
    gate_id = str(uuid4())
    async with get_pool().acquire() as conn:
        own = await conn.fetchrow(
            """
            SELECT 1 AS ok FROM public.threads
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            thread_id,
            user_internal_id,
        )
        if own is None:
            raise ThreadAccessError("Thread not found or access denied")
        await conn.execute(
            """
            INSERT INTO public.approval_gates (id, thread_id, tool_name, payload, status)
            VALUES ($1::uuid, $2::uuid, $3, $4::jsonb, 'PENDING')
            """,
            gate_id,
            thread_id,
            tool_name,
            json.dumps(payload),
        )
    return gate_id


async def get_pending_approval(db_url: str, thread_id: str) -> Optional[dict[str, Any]]:
    _ = db_url
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, tool_name, payload, status, created_at
            FROM public.approval_gates
            WHERE thread_id = $1::uuid AND status = 'PENDING'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            thread_id,
        )

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
    _ = db_url
    async with get_pool().acquire() as conn:
        own = await conn.fetchrow(
            """
            SELECT 1 AS ok FROM public.threads
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            thread_id,
            user_internal_id,
        )
        if own is None:
            raise ThreadAccessError("Thread not found or access denied")
        prow = await conn.fetchrow(
            """
            SELECT id, tool_name, payload, status, created_at
            FROM public.approval_gates
            WHERE thread_id = $1::uuid AND status = 'PENDING'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            thread_id,
        )
        if prow is None:
            return None
        pending = {
            "id": str(prow["id"]),
            "tool_name": prow["tool_name"],
            "payload": prow["payload"],
            "status": prow["status"],
        }
        await conn.execute(
            """
            UPDATE public.approval_gates
            SET status = $2::approval_status, updated_at = NOW()
            WHERE id = $1::uuid
            """,
            pending["id"],
            decision,
        )

    pending["status"] = decision
    return pending


async def get_recent_messages(
    thread_id: str,
    limit: int = 6,
) -> list[dict[str, str]]:
    """Return the most recent *limit* messages for a thread (oldest-first)."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content
            FROM public.thread_messages
            WHERE thread_id = $1::uuid
            ORDER BY created_at DESC, id DESC
            LIMIT $2
            """,
            thread_id,
            limit,
        )
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


async def get_thread_state(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
) -> dict[str, Any]:
    _ = db_url
    async with get_pool().acquire() as conn:
        owner = await conn.fetchrow(
            """
            SELECT 1 AS ok
            FROM public.threads
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            thread_id,
            user_internal_id,
        )
        if owner is None:
            raise ThreadAccessError("Thread not found or access denied")

        run_row = await conn.fetchrow(
            """
            SELECT status, active_agent, pending_approval, approval_gate_id, last_error
            FROM public.thread_runs
            WHERE thread_id = $1::uuid
            """,
            thread_id,
        )
        message_rows = await conn.fetch(
            """
            SELECT role, content
            FROM public.thread_messages
            WHERE thread_id = $1::uuid
            ORDER BY created_at ASC, id ASC
            """,
            thread_id,
        )

        approval_request = None
        if run_row is not None and bool(run_row["pending_approval"]):
            prow = await conn.fetchrow(
                """
                SELECT id, tool_name, payload, status, created_at
                FROM public.approval_gates
                WHERE thread_id = $1::uuid AND status = 'PENDING'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                thread_id,
            )
            if prow is not None:
                approval_request = {
                    "id": str(prow["id"]),
                    "tool_name": prow["tool_name"],
                    "payload": prow["payload"],
                    "status": prow["status"],
                }

    messages = [{"role": row["role"], "content": row["content"]} for row in message_rows]

    if run_row is None:
        return {
            "status": "idle",
            "active_agent": None,
            "messages": messages,
            "pending_approval": False,
            "approval_request": None,
            "last_error": None,
        }

    pending_approval = bool(run_row["pending_approval"])

    return {
        "status": run_row["status"],
        "active_agent": run_row["active_agent"],
        "pending_approval": pending_approval,
        "approval_request": approval_request,
        "last_error": run_row["last_error"],
        "messages": messages,
    }
