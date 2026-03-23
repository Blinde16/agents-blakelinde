"""Notion content-calendar tools (httpx async). Reads are open; creates/updates require approval."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from typing import Any, Optional

import httpx

from src.orchestration.db_pool import get_pool
from src.orchestration.state import create_approval_gate
from src.tools.sync_run import run_sync_tool
from src.tools.schemas import (
    NotionCreateCalendarInput,
    NotionListCalendarInput,
    NotionUpdateCalendarInput,
)
from src.tools.secret_store import decrypt_secret, encrypt_secret

_NOTION_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _title_prop() -> str:
    return os.getenv("NOTION_TITLE_PROPERTY", "Name").strip() or "Name"


def _date_prop() -> str:
    return os.getenv("NOTION_DATE_PROPERTY", "Date").strip() or "Date"


def _status_prop() -> str:
    return os.getenv("NOTION_STATUS_PROPERTY", "Status").strip() or "Status"


async def get_notion_token_for_user(user_internal_id: str) -> Optional[str]:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT token_cipher
            FROM public.user_notion_credentials
            WHERE user_id = $1::uuid
            """,
            user_internal_id,
        )
    if row is None:
        return os.getenv("NOTION_API_KEY") or os.getenv("NOTION_INTEGRATION_TOKEN")
    try:
        return decrypt_secret(row["token_cipher"])
    except Exception:  # noqa: BLE001
        return None


async def resolve_notion_database_id(user_internal_id: str) -> Optional[str]:
    env_d = (os.getenv("NOTION_CONTENT_CALENDAR_DB_ID") or "").strip()
    if env_d:
        return env_d
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT content_database_id
            FROM public.user_notion_credentials
            WHERE user_id = $1::uuid
            """,
            user_internal_id,
        )
    if row and row["content_database_id"]:
        return str(row["content_database_id"]).strip()
    return None


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


async def _notion_post(token: str, path: str, body: dict[str, Any]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45.0) as client:
        return await client.post(
            f"{_NOTION_BASE}{path}",
            headers=_headers(token),
            json=body,
        )


async def _notion_patch(token: str, path: str, body: dict[str, Any]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45.0) as client:
        return await client.patch(
            f"{_NOTION_BASE}{path}",
            headers=_headers(token),
            json=body,
        )


async def upsert_user_notion_credentials(
    user_internal_id: str,
    token: str,
    content_database_id: Optional[str],
) -> None:
    cipher = encrypt_secret(token)
    async with get_pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO public.user_notion_credentials (user_id, token_cipher, content_database_id, updated_at)
            VALUES ($1::uuid, $2, $3, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                token_cipher = EXCLUDED.token_cipher,
                content_database_id = COALESCE(
                    EXCLUDED.content_database_id,
                    public.user_notion_credentials.content_database_id
                ),
                updated_at = NOW()
            """,
            user_internal_id,
            cipher,
            content_database_id,
        )


async def _list_upcoming_calendar_entries_impl(
    user_internal_id: str,
    limit: int = 20,
    days_ahead: int = 30,
) -> str:
    try:
        parsed = NotionListCalendarInput(limit=limit, days_ahead=days_ahead)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await get_notion_token_for_user(user_internal_id)
    if not token:
        return json.dumps(
            {
                "error": "notion_not_configured",
                "detail": "Set NOTION_API_KEY or POST /api/integrations/notion/credentials.",
            }
        )

    db_id = await resolve_notion_database_id(user_internal_id)
    if not db_id:
        return json.dumps(
            {
                "error": "notion_database_missing",
                "detail": "Set NOTION_CONTENT_CALENDAR_DB_ID or save content_database_id with credentials.",
            }
        )

    today = datetime.now(UTC).date()
    dp = _date_prop()

    body: dict[str, Any] = {
        "page_size": parsed.limit,
        "sorts": [{"property": dp, "direction": "ascending"}],
        "filter": {"property": dp, "date": {"on_or_after": today.isoformat()}},
    }

    resp = await _notion_post(token, f"/databases/{db_id}/query", body)
    if resp.status_code >= 400:
        return json.dumps(
            {
                "error": "notion_api_error",
                "status": resp.status_code,
                "body": resp.text[:4000],
            }
        )

    data = resp.json()
    pages = data.get("results") or []
    out: list[dict[str, Any]] = []
    for p in pages:
        out.append(
            {
                "page_id": p.get("id"),
                "url": p.get("url"),
                "properties": p.get("properties"),
            }
        )
    return json.dumps(
        {
            "database_id": db_id,
            "count": len(out),
            "pages": out,
            "days_ahead": parsed.days_ahead,
        },
        ensure_ascii=False,
    )


async def notion_create_calendar_entry_request(
    context: Any,
    title: str,
    scheduled_date: Optional[str] = None,
    status: Optional[str] = None,
    database_id: Optional[str] = None,
) -> str:
    try:
        parsed = NotionCreateCalendarInput(
            title=title,
            scheduled_date=scheduled_date,
            status=status,
            database_id=database_id,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    if parsed.scheduled_date and not _ISO_DATE.match(parsed.scheduled_date):
        return json.dumps(
            {"error": "validation_error", "detail": "scheduled_date must be YYYY-MM-DD."}
        )

    db_id = (parsed.database_id or "").strip() or await resolve_notion_database_id(context.user_internal_id)
    if not db_id:
        return json.dumps(
            {
                "error": "notion_database_missing",
                "detail": "Provide database_id or configure NOTION_CONTENT_CALENDAR_DB_ID.",
            }
        )

    payload = {
        "user_internal_id": context.user_internal_id,
        "title": parsed.title,
        "scheduled_date": parsed.scheduled_date,
        "status": parsed.status,
        "database_id": db_id,
    }
    await create_approval_gate(
        context.db_url,
        context.thread_id,
        context.user_internal_id,
        "notion_create_calendar_entry",
        payload,
    )
    return (
        "Approval required. The Notion calendar entry will be created after human approval."
    )


async def notion_update_calendar_entry_request(
    context: Any,
    page_id: str,
    title: Optional[str] = None,
    scheduled_date: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    try:
        parsed = NotionUpdateCalendarInput(
            page_id=page_id,
            title=title,
            scheduled_date=scheduled_date,
            status=status,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    if parsed.scheduled_date and not _ISO_DATE.match(parsed.scheduled_date):
        return json.dumps(
            {"error": "validation_error", "detail": "scheduled_date must be YYYY-MM-DD."}
        )

    if not any([parsed.title, parsed.scheduled_date, parsed.status]):
        return json.dumps(
            {"error": "validation_error", "detail": "Provide at least one of title, scheduled_date, status."}
        )

    payload = {
        "user_internal_id": context.user_internal_id,
        "page_id": parsed.page_id.strip(),
        "title": parsed.title,
        "scheduled_date": parsed.scheduled_date,
        "status": parsed.status,
    }
    await create_approval_gate(
        context.db_url,
        context.thread_id,
        context.user_internal_id,
        "notion_update_calendar_entry",
        payload,
    )
    return (
        "Approval required. The Notion page will be updated after human approval."
    )


async def execute_notion_create_calendar_entry(
    user_internal_id: str,
    title: str,
    database_id: str,
    scheduled_date: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    try:
        NotionCreateCalendarInput(
            title=title,
            scheduled_date=scheduled_date,
            status=status,
            database_id=database_id,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await get_notion_token_for_user(user_internal_id)
    if not token:
        return json.dumps({"error": "notion_not_configured", "detail": "Missing Notion token."})

    tp, dp, sp = _title_prop(), _date_prop(), _status_prop()
    properties: dict[str, Any] = {
        tp: {"title": [{"text": {"content": title}}]},
    }
    if scheduled_date:
        properties[dp] = {"date": {"start": scheduled_date}}
    if status:
        properties[sp] = {"select": {"name": status}}

    body = {"parent": {"database_id": database_id}, "properties": properties}
    resp = await _notion_post(token, "/pages", body)
    if resp.status_code >= 400:
        return json.dumps(
            {
                "error": "notion_api_error",
                "status": resp.status_code,
                "body": resp.text[:4000],
            }
        )
    data = resp.json()
    return json.dumps(
        {
            "status": "success",
            "page_id": data.get("id"),
            "url": data.get("url"),
        },
        ensure_ascii=False,
    )


async def execute_notion_update_calendar_entry(
    user_internal_id: str,
    page_id: str,
    title: Optional[str] = None,
    scheduled_date: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    try:
        NotionUpdateCalendarInput(
            page_id=page_id,
            title=title,
            scheduled_date=scheduled_date,
            status=status,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    if scheduled_date and not _ISO_DATE.match(scheduled_date):
        return json.dumps({"error": "validation_error", "detail": "scheduled_date must be YYYY-MM-DD."})

    token = await get_notion_token_for_user(user_internal_id)
    if not token:
        return json.dumps({"error": "notion_not_configured", "detail": "Missing Notion token."})

    tp, dp, sp = _title_prop(), _date_prop(), _status_prop()
    properties: dict[str, Any] = {}
    if title is not None:
        properties[tp] = {"title": [{"text": {"content": title}}]}
    if scheduled_date is not None:
        properties[dp] = {"date": {"start": scheduled_date}}
    if status is not None:
        properties[sp] = {"select": {"name": status}}

    if not properties:
        return json.dumps({"error": "validation_error", "detail": "No properties to update."})

    clean_id = page_id.strip()
    resp = await _notion_patch(token, f"/pages/{clean_id}", {"properties": properties})
    if resp.status_code >= 400:
        return json.dumps(
            {
                "error": "notion_api_error",
                "status": resp.status_code,
                "body": resp.text[:4000],
            }
        )
    data = resp.json()
    return json.dumps(
        {
            "status": "success",
            "page_id": data.get("id"),
            "url": data.get("url"),
        },
        ensure_ascii=False,
    )


def build_notion_cmo_tools(context: Any):
    def notion_list_upcoming_calendar_entries(limit: int = 20, days_ahead: int = 30) -> str:
        return run_sync_tool(_list_upcoming_calendar_entries_impl(context.user_internal_id, limit, days_ahead))

    def notion_create_calendar_entry(
        title: str,
        scheduled_date: Optional[str] = None,
        status: Optional[str] = None,
        database_id: Optional[str] = None,
    ) -> str:
        return run_sync_tool(
            notion_create_calendar_entry_request(context, title, scheduled_date, status, database_id)
        )

    def notion_update_calendar_entry(
        page_id: str,
        title: Optional[str] = None,
        scheduled_date: Optional[str] = None,
        status: Optional[str] = None,
    ) -> str:
        return run_sync_tool(
            notion_update_calendar_entry_request(context, page_id, title, scheduled_date, status)
        )

    notion_list_upcoming_calendar_entries.__name__ = "notion_list_upcoming_calendar_entries"
    notion_create_calendar_entry.__name__ = "notion_create_calendar_entry"
    notion_update_calendar_entry.__name__ = "notion_update_calendar_entry"

    return [
        notion_list_upcoming_calendar_entries,
        notion_create_calendar_entry,
        notion_update_calendar_entry,
    ]
