import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import psycopg2

from src.orchestration.db_pool import get_pool

logger = logging.getLogger(__name__)

DEFAULT_STALE_RUN_SECONDS = 8 * 60
DEFAULT_JOB_RETRY_DELAY_SECONDS = 30
DEFAULT_JOB_STALE_SECONDS = 5 * 60


class ThreadAccessError(Exception):
    """Raised when a thread is missing or not owned by the authenticated user."""


class AgentJobNotFoundError(Exception):
    """Raised when a durable agent job is missing."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stale_run_threshold_seconds() -> int:
    raw = os.getenv("THREAD_RUN_STALE_SECONDS", "").strip()
    if not raw:
        return DEFAULT_STALE_RUN_SECONDS
    try:
        parsed = int(raw)
    except ValueError:
        logger.warning("Invalid THREAD_RUN_STALE_SECONDS=%r; using default %s", raw, DEFAULT_STALE_RUN_SECONDS)
        return DEFAULT_STALE_RUN_SECONDS
    return max(parsed, 30)


def _job_retry_delay_seconds() -> int:
    raw = os.getenv("AGENT_JOB_RETRY_DELAY_SECONDS", "").strip()
    if not raw:
        return DEFAULT_JOB_RETRY_DELAY_SECONDS
    try:
        parsed = int(raw)
    except ValueError:
        logger.warning(
            "Invalid AGENT_JOB_RETRY_DELAY_SECONDS=%r; using default %s",
            raw,
            DEFAULT_JOB_RETRY_DELAY_SECONDS,
        )
        return DEFAULT_JOB_RETRY_DELAY_SECONDS
    return max(parsed, 5)


def _job_stale_threshold_seconds() -> int:
    raw = os.getenv("AGENT_JOB_STALE_SECONDS", "").strip()
    if not raw:
        return DEFAULT_JOB_STALE_SECONDS
    try:
        parsed = int(raw)
    except ValueError:
        logger.warning(
            "Invalid AGENT_JOB_STALE_SECONDS=%r; using default %s",
            raw,
            DEFAULT_JOB_STALE_SECONDS,
        )
        return DEFAULT_JOB_STALE_SECONDS
    return max(parsed, 30)


def derive_run_state(
    run_row: Any,
    *,
    approval_request: Optional[dict[str, Any]],
    messages: list[dict[str, str]],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    if run_row is None:
        return {
            "status": "idle",
            "active_agent": None,
            "messages": messages,
            "pending_approval": False,
            "approval_request": None,
            "last_error": None,
            "stale": False,
            "status_detail": None,
            "updated_at": None,
            "started_at": None,
            "completed_at": None,
        }

    status = run_row["status"]
    pending_approval = bool(run_row["pending_approval"])
    last_error = run_row["last_error"]
    updated_at = run_row["updated_at"]
    started_at = run_row["started_at"]
    completed_at = run_row["completed_at"]
    threshold_seconds = _stale_run_threshold_seconds()
    stale = False
    status_detail = None

    if (
        status == "processing"
        and not pending_approval
        and updated_at is not None
    ):
        reference_now = now or _utcnow()
        if reference_now - updated_at >= timedelta(seconds=threshold_seconds):
            stale = True
            status = "error"
            status_detail = (
                f"Run stalled after {threshold_seconds} seconds without a state update. "
                "The agent may have crashed or an external tool may be hanging."
            )
            if not last_error:
                last_error = status_detail

    return {
        "status": status,
        "active_agent": run_row["active_agent"],
        "pending_approval": pending_approval,
        "approval_request": approval_request,
        "last_error": last_error,
        "messages": messages,
        "stale": stale,
        "status_detail": status_detail,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "started_at": started_at.isoformat() if started_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
    }


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
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                ALTER TABLE public.thread_runs
                ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
                """
            )
            cursor.execute(
                """
                ALTER TABLE public.thread_runs
                ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
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
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.thread_context_state (
                    thread_id UUID PRIMARY KEY REFERENCES public.threads(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
                    context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.action_audit_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    thread_id UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
                    action_name TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.agent_jobs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    thread_id UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
                    job_type TEXT NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    status TEXT NOT NULL DEFAULT 'queued',
                    priority INT NOT NULL DEFAULT 100,
                    attempts INT NOT NULL DEFAULT 0,
                    max_attempts INT NOT NULL DEFAULT 3,
                    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    worker_id TEXT,
                    heartbeat_at TIMESTAMPTZ,
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    last_error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT agent_jobs_status_check CHECK (
                        status IN ('queued', 'running', 'completed', 'failed')
                    )
                );
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_jobs_status_available
                    ON public.agent_jobs (status, available_at, priority, created_at);
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_jobs_thread_created
                    ON public.agent_jobs (thread_id, created_at DESC);
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
            INSERT INTO public.thread_runs (thread_id, status, started_at, completed_at, updated_at)
            VALUES ($1::uuid, 'idle', NULL, NULL, NOW())
            ON CONFLICT (thread_id)
            DO UPDATE SET status = 'idle', started_at = NULL, completed_at = NULL, updated_at = NOW()
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
                started_at,
                completed_at,
                updated_at
            )
            VALUES (
                $1::uuid,
                $2,
                $3,
                COALESCE($4, FALSE),
                $5::uuid,
                $6,
                CASE WHEN $2 = 'processing' THEN NOW() ELSE NULL END,
                CASE WHEN $2 IN ('completed', 'error') THEN NOW() ELSE NULL END,
                NOW()
            )
            ON CONFLICT (thread_id)
            DO UPDATE SET
                status = EXCLUDED.status,
                active_agent = COALESCE(EXCLUDED.active_agent, public.thread_runs.active_agent),
                pending_approval = COALESCE($4, public.thread_runs.pending_approval),
                approval_gate_id = $5::uuid,
                last_error = $6,
                started_at = CASE
                    WHEN EXCLUDED.status = 'processing' THEN NOW()
                    WHEN EXCLUDED.status = 'idle' THEN NULL
                    ELSE public.thread_runs.started_at
                END,
                completed_at = CASE
                    WHEN EXCLUDED.status IN ('completed', 'error') THEN NOW()
                    WHEN EXCLUDED.status IN ('processing', 'awaiting_approval', 'idle') THEN NULL
                    ELSE public.thread_runs.completed_at
                END,
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


async def get_thread_context_state(
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

        row = await conn.fetchrow(
            """
            SELECT context_json
            FROM public.thread_context_state
            WHERE thread_id = $1::uuid AND user_id = $2::uuid
            """,
            thread_id,
            user_internal_id,
        )
    if row is None:
        return {}
    payload = row["context_json"] or {}
    return payload if isinstance(payload, dict) else {}


async def upsert_thread_context_state(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    _ = db_url
    if not patch:
        return await get_thread_context_state(db_url, thread_id, user_internal_id)

    current = await get_thread_context_state(db_url, thread_id, user_internal_id)
    merged = {**current, **patch}

    async with get_pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO public.thread_context_state (thread_id, user_id, context_json, updated_at)
            VALUES ($1::uuid, $2::uuid, $3::jsonb, NOW())
            ON CONFLICT (thread_id)
            DO UPDATE SET
                user_id = EXCLUDED.user_id,
                context_json = EXCLUDED.context_json,
                updated_at = NOW()
            """,
            thread_id,
            user_internal_id,
            json.dumps(merged),
        )
    return merged


async def append_action_audit(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    action_name: str,
    payload: dict[str, Any],
) -> None:
    _ = db_url
    async with get_pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO public.action_audit_history (thread_id, user_id, action_name, payload)
            VALUES ($1::uuid, $2::uuid, $3, $4::jsonb)
            """,
            thread_id,
            user_internal_id,
            action_name,
            json.dumps(payload),
        )


async def enqueue_agent_job(
    db_url: str,
    thread_id: str,
    user_internal_id: str,
    *,
    job_type: str,
    payload: dict[str, Any],
    priority: int = 100,
    max_attempts: int = 3,
) -> str:
    _ = db_url
    job_id = str(uuid4())
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
            INSERT INTO public.agent_jobs (
                id,
                thread_id,
                user_id,
                job_type,
                payload,
                status,
                priority,
                attempts,
                max_attempts,
                available_at,
                created_at,
                updated_at
            )
            VALUES (
                $1::uuid,
                $2::uuid,
                $3::uuid,
                $4,
                $5::jsonb,
                'queued',
                $6,
                0,
                $7,
                NOW(),
                NOW(),
                NOW()
            )
            """,
            job_id,
            thread_id,
            user_internal_id,
            job_type,
            json.dumps(payload),
            priority,
            max_attempts,
        )
    return job_id


async def claim_next_agent_job(db_url: str, worker_id: str) -> Optional[dict[str, Any]]:
    _ = db_url
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH next_job AS (
                SELECT id
                FROM public.agent_jobs
                WHERE status = 'queued' AND available_at <= NOW()
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE public.agent_jobs AS j
            SET
                status = 'running',
                worker_id = $1,
                attempts = j.attempts + 1,
                started_at = COALESCE(j.started_at, NOW()),
                heartbeat_at = NOW(),
                updated_at = NOW(),
                last_error = NULL
            FROM next_job
            WHERE j.id = next_job.id
            RETURNING
                j.id::text AS id,
                j.thread_id::text AS thread_id,
                j.user_id::text AS user_id,
                j.job_type,
                j.payload,
                j.status,
                j.priority,
                j.attempts,
                j.max_attempts,
                j.available_at,
                j.worker_id,
                j.heartbeat_at,
                j.started_at,
                j.completed_at,
                j.last_error,
                j.created_at,
                j.updated_at
            """,
            worker_id,
        )

    if row is None:
        return None
    return dict(row)


async def touch_agent_job(db_url: str, job_id: str, worker_id: str) -> None:
    _ = db_url
    async with get_pool().acquire() as conn:
        res = await conn.execute(
            """
            UPDATE public.agent_jobs
            SET heartbeat_at = NOW(), updated_at = NOW()
            WHERE id = $1::uuid AND worker_id = $2 AND status = 'running'
            """,
            job_id,
            worker_id,
        )
    if res == "UPDATE 0":
        raise AgentJobNotFoundError(f"Agent job {job_id} is not running for worker {worker_id}.")


async def complete_agent_job(db_url: str, job_id: str) -> None:
    _ = db_url
    async with get_pool().acquire() as conn:
        res = await conn.execute(
            """
            UPDATE public.agent_jobs
            SET
                status = 'completed',
                completed_at = NOW(),
                heartbeat_at = NOW(),
                updated_at = NOW(),
                last_error = NULL
            WHERE id = $1::uuid
            """,
            job_id,
        )
    if res == "UPDATE 0":
        raise AgentJobNotFoundError(f"Agent job {job_id} was not found.")


async def fail_agent_job(
    db_url: str,
    job_id: str,
    *,
    error: str,
    retry_delay_seconds: Optional[int] = None,
) -> dict[str, Any]:
    _ = db_url
    retry_seconds = retry_delay_seconds if retry_delay_seconds is not None else _job_retry_delay_seconds()
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT attempts, max_attempts
            FROM public.agent_jobs
            WHERE id = $1::uuid
            """,
            job_id,
        )
        if row is None:
            raise AgentJobNotFoundError(f"Agent job {job_id} was not found.")

        attempts = int(row["attempts"])
        max_attempts = int(row["max_attempts"])
        terminal = attempts >= max_attempts
        if terminal:
            await conn.execute(
                """
                UPDATE public.agent_jobs
                SET
                    status = 'failed',
                    completed_at = NOW(),
                    heartbeat_at = NOW(),
                    updated_at = NOW(),
                    last_error = $2
                WHERE id = $1::uuid
                """,
                job_id,
                error,
            )
        else:
            await conn.execute(
                """
                UPDATE public.agent_jobs
                SET
                    status = 'queued',
                    worker_id = NULL,
                    available_at = NOW() + ($2::int * INTERVAL '1 second'),
                    heartbeat_at = NULL,
                    updated_at = NOW(),
                    last_error = $3
                WHERE id = $1::uuid
                """,
                job_id,
                retry_seconds,
                error,
            )

    return {
        "terminal": terminal,
        "attempts": attempts,
        "max_attempts": max_attempts,
        "retry_delay_seconds": retry_seconds,
    }


async def recover_stale_agent_jobs(db_url: str) -> dict[str, Any]:
    _ = db_url
    stale_seconds = _job_stale_threshold_seconds()
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            """
            UPDATE public.agent_jobs
            SET
                status = CASE
                    WHEN attempts >= max_attempts THEN 'failed'
                    ELSE 'queued'
                END,
                worker_id = NULL,
                available_at = CASE
                    WHEN attempts >= max_attempts THEN available_at
                    ELSE NOW()
                END,
                heartbeat_at = NULL,
                completed_at = CASE
                    WHEN attempts >= max_attempts THEN NOW()
                    ELSE completed_at
                END,
                updated_at = NOW(),
                last_error = COALESCE(
                    last_error,
                    'Recovered stale running job after worker heartbeat expired.'
                )
            WHERE status = 'running'
              AND COALESCE(heartbeat_at, started_at, updated_at) < NOW() - ($1::int * INTERVAL '1 second')
            RETURNING
                id::text AS id,
                thread_id::text AS thread_id,
                user_id::text AS user_id,
                job_type,
                payload,
                status,
                attempts,
                max_attempts,
                last_error
            """,
            stale_seconds,
        )

    recovered = 0
    failed = 0
    terminal_jobs: list[dict[str, Any]] = []
    for row in rows:
        if row["status"] == "failed":
            failed += 1
            terminal_jobs.append(dict(row))
        else:
            recovered += 1
    return {"recovered": recovered, "failed": failed, "terminal_jobs": terminal_jobs}


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
            SELECT status, active_agent, pending_approval, approval_gate_id, last_error, updated_at, started_at, completed_at
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
    return derive_run_state(run_row, approval_request=approval_request, messages=messages)
