"""Social queue: draft and schedule in DB; public posting only after approval (no silent network posts)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from src.orchestration.db_pool import get_pool
from src.orchestration.state import create_approval_gate
from src.tools.sync_run import run_sync_tool
from src.tools.schemas import (
    SocialCreateDraftInput,
    SocialListQueueInput,
    SocialPostIdInput,
    SocialScheduleInput,
)


def _parse_iso_utc(s: str) -> datetime:
    t = s.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    return datetime.fromisoformat(t).astimezone(UTC)


async def _create_social_draft_impl(
    user_internal_id: str,
    platform: str,
    body: str,
    scheduled_at: Optional[str] = None,
) -> str:
    try:
        parsed = SocialCreateDraftInput(platform=platform, body=body, scheduled_at=scheduled_at)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    sched_dt: Optional[datetime] = None
    if parsed.scheduled_at:
        try:
            sched_dt = _parse_iso_utc(parsed.scheduled_at)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": "validation_error", "detail": f"scheduled_at: {exc}"})

    status = "scheduled" if sched_dt is not None else "draft"

    try:
        async with get_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.social_media_posts (
                    user_id, platform, body, status, scheduled_at, updated_at
                )
                VALUES ($1::uuid, $2, $3, $4, $5, NOW())
                RETURNING id::text
                """,
                user_internal_id,
                parsed.platform,
                parsed.body,
                status,
                sched_dt,
            )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "database_error", "detail": str(exc)})

    return json.dumps(
        {
            "post_id": row[0],
            "platform": parsed.platform,
            "status": status,
            "detail": "Stored as queue row only. No external post until publish_social_post is approved.",
        },
        ensure_ascii=False,
    )


async def _list_social_queue_impl(user_internal_id: str, status: Optional[str] = None) -> str:
    try:
        parsed = SocialListQueueInput(status=status)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    try:
        async with get_pool().acquire() as conn:
            if parsed.status:
                rows = await conn.fetch(
                    """
                    SELECT id::text, platform, body, status, scheduled_at, published_at, external_post_id, created_at
                    FROM public.social_media_posts
                    WHERE user_id = $1::uuid AND status = $2
                    ORDER BY created_at DESC
                    LIMIT 100
                    """,
                    user_internal_id,
                    parsed.status,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id::text, platform, body, status, scheduled_at, published_at, external_post_id, created_at
                    FROM public.social_media_posts
                    WHERE user_id = $1::uuid
                    ORDER BY created_at DESC
                    LIMIT 100
                    """,
                    user_internal_id,
                )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "database_error", "detail": str(exc)})

    out = [dict(r) for r in rows]
    return json.dumps({"count": len(out), "posts": out}, default=str, ensure_ascii=False)


async def _schedule_social_post_impl(
    user_internal_id: str,
    post_id: str,
    scheduled_at: str,
) -> str:
    try:
        parsed = SocialScheduleInput(post_id=post_id, scheduled_at=scheduled_at)
        sched_dt = _parse_iso_utc(parsed.scheduled_at)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    try:
        async with get_pool().acquire() as conn:
            res = await conn.execute(
                """
                UPDATE public.social_media_posts
                SET scheduled_at = $3,
                    status = 'scheduled',
                    updated_at = NOW()
                WHERE id = $1::uuid AND user_id = $2::uuid
                  AND status IN ('draft', 'scheduled')
                """,
                str(parsed.post_id),
                user_internal_id,
                sched_dt,
            )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "database_error", "detail": str(exc)})

    if res == "UPDATE 0":
        return json.dumps({"detail": "Post not found, not owned, or not schedulable."})
    return json.dumps(
        {"post_id": str(parsed.post_id), "status": "scheduled", "scheduled_at": sched_dt.isoformat()},
        ensure_ascii=False,
    )


async def _cancel_social_post_impl(user_internal_id: str, post_id: str) -> str:
    try:
        parsed = SocialPostIdInput(post_id=post_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    try:
        async with get_pool().acquire() as conn:
            res = await conn.execute(
                """
                UPDATE public.social_media_posts
                SET status = 'cancelled', updated_at = NOW()
                WHERE id = $1::uuid AND user_id = $2::uuid
                  AND status IN ('draft', 'scheduled')
                """,
                str(parsed.post_id),
                user_internal_id,
            )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "database_error", "detail": str(exc)})

    if res == "UPDATE 0":
        return json.dumps({"detail": "Post not found, not owned, or already published/cancelled."})
    return json.dumps({"post_id": str(parsed.post_id), "status": "cancelled"})


async def publish_social_post_request(context: Any, post_id: str) -> str:
    try:
        parsed = SocialPostIdInput(post_id=post_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    await create_approval_gate(
        context.db_url,
        context.thread_id,
        context.user_internal_id,
        "publish_social_post",
        {
            "user_internal_id": context.user_internal_id,
            "post_id": str(parsed.post_id),
        },
    )
    return (
        "Approval required. External publish will run only after human approval in the UI."
    )


async def execute_publish_social_post(user_internal_id: str, post_id: str) -> str:
    try:
        parsed = SocialPostIdInput(post_id=post_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    ext = f"simulated:{uuid.uuid4()}"
    now = datetime.now(UTC)

    try:
        async with get_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE public.social_media_posts
                SET status = 'published',
                    published_at = $3,
                    external_post_id = $4,
                    updated_at = NOW()
                WHERE id = $1::uuid AND user_id = $2::uuid
                  AND status IN ('draft', 'scheduled')
                RETURNING platform, body
                """,
                str(parsed.post_id),
                user_internal_id,
                now,
                ext,
            )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "database_error", "detail": str(exc)})

    if row is None:
        return json.dumps(
            {"detail": "Post not found, not owned, or not publishable (already published/cancelled)."}
        )

    return json.dumps(
        {
            "status": "published",
            "post_id": str(parsed.post_id),
            "platform": row["platform"],
            "external_post_id": ext,
            "detail": "Marked published in queue. Live API posting is gated for future OAuth wiring.",
        },
        ensure_ascii=False,
    )


def build_social_cmo_tools(context: Any):
    def create_social_draft(
        platform: str,
        body: str,
        scheduled_at: Optional[str] = None,
    ) -> str:
        return run_sync_tool(
            _create_social_draft_impl(context.user_internal_id, platform, body, scheduled_at)
        )

    def list_social_queue(status: Optional[str] = None) -> str:
        return run_sync_tool(_list_social_queue_impl(context.user_internal_id, status))

    def schedule_social_post(post_id: str, scheduled_at: str) -> str:
        return run_sync_tool(_schedule_social_post_impl(context.user_internal_id, post_id, scheduled_at))

    def cancel_social_post(post_id: str) -> str:
        return run_sync_tool(_cancel_social_post_impl(context.user_internal_id, post_id))

    def publish_social_post(post_id: str) -> str:
        return run_sync_tool(publish_social_post_request(context, post_id))

    create_social_draft.__name__ = "create_social_draft"
    list_social_queue.__name__ = "list_social_queue"
    schedule_social_post.__name__ = "schedule_social_post"
    cancel_social_post.__name__ = "cancel_social_post"
    publish_social_post.__name__ = "publish_social_post"

    return [
        create_social_draft,
        list_social_queue,
        schedule_social_post,
        cancel_social_post,
        publish_social_post,
    ]
