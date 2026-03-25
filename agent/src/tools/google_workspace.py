"""Google Gmail + Calendar (async httpx). Reads/drafts/low-risk triage without approval; send, trash, label changes, and calendar writes require approval where noted."""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from email.mime.text import MIMEText
from typing import Any, Optional

import httpx

from src.orchestration.db_pool import get_pool
from src.orchestration.state import create_approval_gate
from src.tools.google_gmail_decode import extract_headers, extract_plain_text_from_payload
from src.tools.schemas import (
    CreateCalendarEventInput,
    DeleteCalendarEventInput,
    DraftEmailInput,
    FreeBusyInput,
    GetCalendarEventsInput,
    GoogleMessageIdInput,
    GoogleModifyLabelsInput,
    GoogleSearchEmailInput,
    GoogleThreadIdInput,
    ListRecentThreadsInput,
    SendEmailInput,
    UpdateCalendarEventInput,
)
from src.tools.secret_store import decrypt_secret, encrypt_secret
from src.tools.sync_run import run_sync_tool

logger = logging.getLogger(__name__)

_GMAIL = "https://gmail.googleapis.com/gmail/v1"
_CAL = "https://www.googleapis.com/calendar/v3"


def _primary_calendar() -> str:
    return (os.getenv("GOOGLE_PRIMARY_CALENDAR_ID") or "primary").strip() or "primary"


def _oauth_client() -> tuple[str, str]:
    return (
        os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip(),
        os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip(),
    )


async def get_refresh_token_for_user(user_internal_id: str) -> Optional[str]:
    env_tok = (os.getenv("GOOGLE_REFRESH_TOKEN") or "").strip()
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT refresh_token_cipher
            FROM public.user_google_credentials
            WHERE user_id = $1::uuid
            """,
            user_internal_id,
        )
    if row is None:
        return env_tok or None
    try:
        return decrypt_secret(row["refresh_token_cipher"])
    except Exception:  # noqa: BLE001
        return env_tok or None


async def upsert_user_google_credentials(
    user_internal_id: str,
    refresh_token: str,
    google_email: Optional[str],
) -> None:
    cipher = encrypt_secret(refresh_token)
    async with get_pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO public.user_google_credentials (user_id, refresh_token_cipher, google_email, updated_at)
            VALUES ($1::uuid, $2, $3, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                refresh_token_cipher = EXCLUDED.refresh_token_cipher,
                google_email = COALESCE(EXCLUDED.google_email, public.user_google_credentials.google_email),
                updated_at = NOW()
            """,
            user_internal_id,
            cipher,
            google_email,
        )


async def _access_token(user_internal_id: str) -> Optional[str]:
    refresh = await get_refresh_token_for_user(user_internal_id)
    if not refresh:
        logger.warning(
            "Google OAuth: no refresh token for user (set GOOGLE_REFRESH_TOKEN or POST /api/integrations/google/credentials)."
        )
        return None
    cid, secret = _oauth_client()
    if not cid or not secret:
        logger.warning("Google OAuth: GOOGLE_OAUTH_CLIENT_ID or GOOGLE_OAUTH_CLIENT_SECRET missing.")
        return None
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": cid,
                "client_secret": secret,
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code >= 400:
        logger.warning(
            "Google OAuth token refresh failed: status=%s body=%s",
            resp.status_code,
            (resp.text or "")[:500],
        )
        return None
    data = resp.json()
    return data.get("access_token")


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _not_configured() -> str:
    return json.dumps(
        {
            "error": "google_not_configured",
            "detail": "Set GOOGLE_OAUTH_CLIENT_ID/SECRET and GOOGLE_REFRESH_TOKEN or POST /api/integrations/google/credentials.",
        }
    )


def _encode_raw_email(
    to_addr: str,
    subject: str,
    body: str,
    *,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> str:
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to_addr
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to.strip()
    if references:
        msg["References"] = references.strip()
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


async def _gmail_get(token: str, path: str, params: Optional[dict[str, Any]] = None) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45.0) as client:
        return await client.get(
            f"{_GMAIL}{path}",
            headers={**_auth_header(token), "Content-Type": "application/json"},
            params=params or {},
        )


async def _gmail_post(token: str, path: str, json_body: Optional[dict[str, Any]] = None) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45.0) as client:
        return await client.post(
            f"{_GMAIL}{path}",
            headers={**_auth_header(token), "Content-Type": "application/json"},
            json=json_body,
        )


async def _cal_get(token: str, path: str, params: Optional[dict[str, Any]] = None) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45.0) as client:
        return await client.get(
            f"{_CAL}{path}",
            headers={**_auth_header(token), "Content-Type": "application/json"},
            params=params or {},
        )


async def _cal_post(token: str, path: str, json_body: dict[str, Any]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45.0) as client:
        return await client.post(
            f"{_CAL}{path}",
            headers={**_auth_header(token), "Content-Type": "application/json"},
            json=json_body,
        )


async def _cal_patch(token: str, path: str, json_body: dict[str, Any]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45.0) as client:
        return await client.patch(
            f"{_CAL}{path}",
            headers={**_auth_header(token), "Content-Type": "application/json"},
            json=json_body,
        )


async def _cal_delete(token: str, path: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45.0) as client:
        return await client.delete(
            f"{_CAL}{path}",
            headers={**_auth_header(token), "Content-Type": "application/json"},
        )


# --- Read: search & retrieve ---


async def _search_emails_impl(user_internal_id: str, query: str, max_results: int = 20) -> str:
    try:
        parsed = GoogleSearchEmailInput(query=query, max_results=max_results)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    resp = await _gmail_get(
        token,
        "/users/me/messages",
        params={"q": parsed.query, "maxResults": parsed.max_results},
    )
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "gmail_api_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    data = resp.json()
    msgs = data.get("messages") or []
    out = [{"message_id": m.get("id"), "thread_id": m.get("threadId")} for m in msgs]
    return json.dumps({"count": len(out), "messages": out}, ensure_ascii=False)


async def _get_email_message_impl(user_internal_id: str, message_id: str) -> str:
    try:
        parsed = GoogleMessageIdInput(message_id=message_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    resp = await _gmail_get(token, f"/users/me/messages/{parsed.message_id}", params={"format": "full"})
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "gmail_api_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    m = resp.json()
    payload = m.get("payload") or {}
    text = extract_plain_text_from_payload(payload)
    hdrs = extract_headers(m)
    return json.dumps(
        {
            "message_id": m.get("id"),
            "thread_id": m.get("threadId"),
            "snippet": m.get("snippet"),
            "headers": hdrs,
            "body_plain": text[:120000],
            "truncated": len(text) > 120000,
        },
        ensure_ascii=False,
    )


async def _get_thread_messages_impl(user_internal_id: str, thread_id: str) -> str:
    try:
        parsed = GoogleThreadIdInput(thread_id=thread_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    resp = await _gmail_get(token, f"/users/me/threads/{parsed.thread_id}", params={"format": "full"})
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "gmail_api_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    t = resp.json()
    messages_out: list[dict[str, Any]] = []
    for m in t.get("messages") or []:
        payload = m.get("payload") or {}
        text = extract_plain_text_from_payload(payload)
        messages_out.append(
            {
                "message_id": m.get("id"),
                "headers": extract_headers(m),
                "snippet": m.get("snippet"),
                "body_plain": text[:80000],
                "truncated": len(text) > 80000,
            }
        )
    return json.dumps(
        {"thread_id": t.get("id"), "message_count": len(messages_out), "messages": messages_out},
        ensure_ascii=False,
    )


async def _list_email_labels_impl(user_internal_id: str) -> str:
    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    resp = await _gmail_get(token, "/users/me/labels")
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "gmail_api_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    data = resp.json()
    labels = data.get("labels") or []
    slim = [{"id": x.get("id"), "name": x.get("name"), "type": x.get("type")} for x in labels]
    return json.dumps({"count": len(slim), "labels": slim}, ensure_ascii=False)


async def _list_recent_threads_impl(user_internal_id: str, max_results: int = 10) -> str:
    try:
        parsed = ListRecentThreadsInput(max_results=max_results)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    resp = await _gmail_get(token, "/users/me/threads", params={"maxResults": parsed.max_results})
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "gmail_api_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    data = resp.json()
    threads = data.get("threads") or []
    out = [{"thread_id": t.get("id"), "snippet": t.get("snippet")} for t in threads]
    return json.dumps({"count": len(out), "threads": out}, ensure_ascii=False)


# --- Triage without approval (archive, read state, star) ---


async def _modify_message_impl(
    user_internal_id: str,
    message_id: str,
    add_label_ids: list[str],
    remove_label_ids: list[str],
) -> str:
    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    body: dict[str, Any] = {}
    if add_label_ids:
        body["addLabelIds"] = add_label_ids
    if remove_label_ids:
        body["removeLabelIds"] = remove_label_ids
    resp = await _gmail_post(token, f"/users/me/messages/{message_id}/modify", body)
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "gmail_modify_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    return json.dumps({"status": "ok", "message_id": message_id, "detail": resp.json()}, ensure_ascii=False)


async def _archive_email_impl(user_internal_id: str, message_id: str) -> str:
    try:
        parsed = GoogleMessageIdInput(message_id=message_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})
    return await _modify_message_impl(user_internal_id, parsed.message_id, [], ["INBOX"])


async def _mark_email_read_impl(user_internal_id: str, message_id: str) -> str:
    try:
        parsed = GoogleMessageIdInput(message_id=message_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})
    return await _modify_message_impl(user_internal_id, parsed.message_id, [], ["UNREAD"])


async def _mark_email_unread_impl(user_internal_id: str, message_id: str) -> str:
    try:
        parsed = GoogleMessageIdInput(message_id=message_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})
    return await _modify_message_impl(user_internal_id, parsed.message_id, ["UNREAD"], [])


async def _star_email_impl(user_internal_id: str, message_id: str) -> str:
    try:
        parsed = GoogleMessageIdInput(message_id=message_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})
    return await _modify_message_impl(user_internal_id, parsed.message_id, ["STARRED"], [])


async def _unstar_email_impl(user_internal_id: str, message_id: str) -> str:
    try:
        parsed = GoogleMessageIdInput(message_id=message_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})
    return await _modify_message_impl(user_internal_id, parsed.message_id, [], ["STARRED"])


async def execute_archive_email(user_internal_id: str, message_id: str) -> str:
    return await _archive_email_impl(user_internal_id, message_id)


async def execute_mark_email_read(user_internal_id: str, message_id: str) -> str:
    return await _mark_email_read_impl(user_internal_id, message_id)


async def execute_mark_email_unread(user_internal_id: str, message_id: str) -> str:
    return await _mark_email_unread_impl(user_internal_id, message_id)


async def execute_star_email(user_internal_id: str, message_id: str) -> str:
    return await _star_email_impl(user_internal_id, message_id)


async def execute_unstar_email(user_internal_id: str, message_id: str) -> str:
    return await _unstar_email_impl(user_internal_id, message_id)


# --- Approval: trash, arbitrary label changes ---


async def trash_email_request(context: Any, message_id: str) -> str:
    try:
        parsed = GoogleMessageIdInput(message_id=message_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    await create_approval_gate(
        context.db_url,
        context.thread_id,
        context.user_internal_id,
        "trash_email",
        {"user_internal_id": context.user_internal_id, "message_id": parsed.message_id},
    )
    return "Approval required. Message will move to Trash only after human approval."


async def modify_email_labels_request(
    context: Any,
    message_id: str,
    add_label_ids: str = "",
    remove_label_ids: str = "",
) -> str:
    """Comma-separated Gmail label ids (e.g. Label_123,STARRED)."""
    try:
        parsed = GoogleMessageIdInput(message_id=message_id)
        add_ids = [x.strip() for x in add_label_ids.split(",") if x.strip()]
        rem_ids = [x.strip() for x in remove_label_ids.split(",") if x.strip()]
        if not add_ids and not rem_ids:
            return json.dumps({"error": "validation_error", "detail": "Provide add_label_ids or remove_label_ids."})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    await create_approval_gate(
        context.db_url,
        context.thread_id,
        context.user_internal_id,
        "modify_email_labels",
        {
            "user_internal_id": context.user_internal_id,
            "message_id": parsed.message_id,
            "add_label_ids": add_ids,
            "remove_label_ids": rem_ids,
        },
    )
    return "Approval required. Label changes apply only after human approval."


async def execute_trash_message(user_internal_id: str, message_id: str) -> str:
    try:
        parsed = GoogleMessageIdInput(message_id=message_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    resp = await _gmail_post(token, f"/users/me/messages/{parsed.message_id}/trash", {})
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "gmail_trash_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    return json.dumps({"status": "trashed", "message_id": parsed.message_id}, ensure_ascii=False)


async def execute_modify_email_labels(
    user_internal_id: str,
    message_id: str,
    add_label_ids: list[str],
    remove_label_ids: list[str],
) -> str:
    return await _modify_message_impl(user_internal_id, message_id, add_label_ids, remove_label_ids)


# --- Draft / send ---


async def _draft_email_impl(user_internal_id: str, to: str, subject: str, body: str) -> str:
    try:
        parsed = DraftEmailInput(
            to=to,
            subject=subject,
            body=body,
            cc=None,
            bcc=None,
            thread_id=None,
            reply_to_message_id=None,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    raw = _encode_raw_email(parsed.to, parsed.subject, parsed.body)
    dbody: dict[str, Any] = {"message": {"raw": raw}}
    resp = await _gmail_post(token, "/users/me/drafts", dbody)
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "gmail_draft_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    data = resp.json()
    mid = (data.get("message") or {}).get("id")
    did = data.get("id")
    return json.dumps(
        {"draft_id": did, "message_id": mid, "detail": "Draft created. Not sent."},
        ensure_ascii=False,
    )


async def _draft_email_full_impl(
    user_internal_id: str,
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    thread_id: Optional[str] = None,
    reply_to_message_id: Optional[str] = None,
) -> str:
    try:
        parsed = DraftEmailInput(
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            thread_id=thread_id,
            reply_to_message_id=reply_to_message_id,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    raw = _encode_raw_email(
        parsed.to,
        parsed.subject,
        parsed.body,
        cc=parsed.cc,
        bcc=parsed.bcc,
        in_reply_to=parsed.reply_to_message_id,
        references=parsed.reply_to_message_id,
    )
    msg: dict[str, Any] = {"raw": raw}
    if parsed.thread_id:
        msg["threadId"] = parsed.thread_id.strip()
    resp = await _gmail_post(token, "/users/me/drafts", {"message": msg})
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "gmail_draft_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    data = resp.json()
    return json.dumps(
        {
            "draft_id": data.get("id"),
            "message_id": (data.get("message") or {}).get("id"),
            "thread_id": (data.get("message") or {}).get("threadId"),
            "detail": "Draft created. Not sent.",
        },
        ensure_ascii=False,
    )


async def send_email_request(context: Any, to: str, subject: str, body: str) -> str:
    try:
        parsed = SendEmailInput(to=to, subject=subject, body=body)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    await create_approval_gate(
        context.db_url,
        context.thread_id,
        context.user_internal_id,
        "send_email",
        {
            "user_internal_id": context.user_internal_id,
            "to": parsed.to,
            "subject": parsed.subject,
            "body": parsed.body,
        },
    )
    return "Approval required. Email will send only after human approval."


async def execute_send_email(
    user_internal_id: str,
    to: str,
    subject: str,
    body: str,
) -> str:
    try:
        SendEmailInput(to=to, subject=subject, body=body)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    raw = _encode_raw_email(to, subject, body)
    resp = await _gmail_post(token, "/users/me/messages/send", {"raw": raw})
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "gmail_send_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    data = resp.json()
    return json.dumps(
        {"status": "sent", "message_id": data.get("id"), "thread_id": data.get("threadId")},
        ensure_ascii=False,
    )


# --- Calendar: read, free/busy, create/update/delete ---


async def _get_calendar_events_impl(
    user_internal_id: str,
    days_ahead: int = 7,
    max_results: int = 20,
    calendar_id: Optional[str] = None,
) -> str:
    try:
        parsed = GetCalendarEventsInput(days_ahead=days_ahead, max_results=max_results)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    cal = calendar_id or _primary_calendar()
    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    now = datetime.now(UTC)
    end = now + timedelta(days=parsed.days_ahead)
    params = {
        "timeMin": now.isoformat().replace("+00:00", "Z"),
        "timeMax": end.isoformat().replace("+00:00", "Z"),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": parsed.max_results,
    }

    from urllib.parse import quote

    cid = quote(cal, safe="")
    resp = await _cal_get(token, f"/calendars/{cid}/events", params=params)
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "calendar_api_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    data = resp.json()
    items = data.get("items") or []
    slim = []
    for ev in items:
        slim.append(
            {
                "id": ev.get("id"),
                "summary": ev.get("summary"),
                "start": ev.get("start"),
                "end": ev.get("end"),
                "htmlLink": ev.get("htmlLink"),
                "location": ev.get("location"),
            }
        )
    return json.dumps({"calendar_id": cal, "count": len(slim), "events": slim}, ensure_ascii=False)


async def _get_calendar_event_impl(user_internal_id: str, event_id: str) -> str:
    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    from urllib.parse import quote

    cal = quote(_primary_calendar(), safe="")
    eid = quote(event_id, safe="")
    resp = await _cal_get(token, f"/calendars/{cal}/events/{eid}")
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "calendar_api_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    return json.dumps(resp.json(), ensure_ascii=False)


async def _freebusy_impl(user_internal_id: str, days_ahead: int = 7) -> str:
    try:
        parsed = FreeBusyInput(days_ahead=days_ahead)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    now = datetime.now(UTC)
    end = now + timedelta(days=parsed.days_ahead)
    body = {
        "timeMin": now.isoformat().replace("+00:00", "Z"),
        "timeMax": end.isoformat().replace("+00:00", "Z"),
        "items": [{"id": _primary_calendar()}],
    }
    resp = await _cal_post(token, "/freeBusy", body)
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "calendar_freebusy_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    return json.dumps(resp.json(), ensure_ascii=False)


async def create_calendar_event_request(
    context: Any,
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
) -> str:
    try:
        parsed = CreateCalendarEventInput(
            summary=summary,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            description=description,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    await create_approval_gate(
        context.db_url,
        context.thread_id,
        context.user_internal_id,
        "create_calendar_event",
        {
            "user_internal_id": context.user_internal_id,
            "summary": parsed.summary,
            "start_datetime": parsed.start_datetime.strip(),
            "end_datetime": parsed.end_datetime.strip(),
            "description": parsed.description,
        },
    )
    return "Approval required. Calendar event will be created only after human approval."


async def update_calendar_event_request(
    context: Any,
    event_id: str,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    summary: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    try:
        parsed = UpdateCalendarEventInput(
            event_id=event_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            summary=summary,
            description=description,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    await create_approval_gate(
        context.db_url,
        context.thread_id,
        context.user_internal_id,
        "update_calendar_event",
        {
            "user_internal_id": context.user_internal_id,
            "event_id": parsed.event_id,
            "start_datetime": parsed.start_datetime,
            "end_datetime": parsed.end_datetime,
            "summary": parsed.summary,
            "description": parsed.description,
        },
    )
    return "Approval required. Calendar update runs only after human approval."


async def delete_calendar_event_request(context: Any, event_id: str) -> str:
    try:
        parsed = DeleteCalendarEventInput(event_id=event_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    await create_approval_gate(
        context.db_url,
        context.thread_id,
        context.user_internal_id,
        "delete_calendar_event",
        {
            "user_internal_id": context.user_internal_id,
            "event_id": parsed.event_id,
        },
    )
    return "Approval required. Event deletion runs only after human approval."


async def execute_create_calendar_event(
    user_internal_id: str,
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
) -> str:
    try:
        parsed = CreateCalendarEventInput(
            summary=summary,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            description=description,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    body: dict[str, Any] = {
        "summary": parsed.summary,
        "start": {"dateTime": parsed.start_datetime.strip(), "timeZone": "UTC"},
        "end": {"dateTime": parsed.end_datetime.strip(), "timeZone": "UTC"},
    }
    if parsed.description:
        body["description"] = parsed.description

    from urllib.parse import quote

    cal = quote(_primary_calendar(), safe="")
    resp = await _cal_post(token, f"/calendars/{cal}/events", body)
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "calendar_create_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    data = resp.json()
    return json.dumps(
        {"status": "created", "event_id": data.get("id"), "htmlLink": data.get("htmlLink")},
        ensure_ascii=False,
    )


async def execute_update_calendar_event(
    user_internal_id: str,
    event_id: str,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    summary: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    try:
        parsed = UpdateCalendarEventInput(
            event_id=event_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            summary=summary,
            description=description,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    patch: dict[str, Any] = {}
    if parsed.start_datetime:
        patch["start"] = {"dateTime": parsed.start_datetime.strip(), "timeZone": "UTC"}
    if parsed.end_datetime:
        patch["end"] = {"dateTime": parsed.end_datetime.strip(), "timeZone": "UTC"}
    if parsed.summary is not None:
        patch["summary"] = parsed.summary
    if parsed.description is not None:
        patch["description"] = parsed.description

    from urllib.parse import quote

    cal = quote(_primary_calendar(), safe="")
    eid = quote(parsed.event_id, safe="")
    resp = await _cal_patch(token, f"/calendars/{cal}/events/{eid}", patch)
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "calendar_update_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    data = resp.json()
    return json.dumps(
        {"status": "updated", "event_id": data.get("id"), "htmlLink": data.get("htmlLink")},
        ensure_ascii=False,
    )


async def execute_delete_calendar_event(user_internal_id: str, event_id: str) -> str:
    try:
        parsed = DeleteCalendarEventInput(event_id=event_id)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = await _access_token(user_internal_id)
    if not token:
        return _not_configured()

    from urllib.parse import quote

    cal = quote(_primary_calendar(), safe="")
    eid = quote(parsed.event_id, safe="")
    resp = await _cal_delete(token, f"/calendars/{cal}/events/{eid}")
    if resp.status_code >= 400:
        return json.dumps(
            {"error": "calendar_delete_error", "status": resp.status_code, "body": resp.text[:4000]}
        )
    return json.dumps({"status": "deleted", "event_id": parsed.event_id}, ensure_ascii=False)


def build_google_ops_tools(context: Any):
    """Sync tool entrypoints; async impls run via :func:`run_sync_tool` (Agno + validate_call quirk)."""

    def search_emails(query: str, max_results: int = 20) -> str:
        return run_sync_tool(_search_emails_impl(context.user_internal_id, query, max_results))

    def get_email_message(message_id: str) -> str:
        return run_sync_tool(_get_email_message_impl(context.user_internal_id, message_id))

    def get_thread_messages(thread_id: str) -> str:
        return run_sync_tool(_get_thread_messages_impl(context.user_internal_id, thread_id))

    def list_email_labels() -> str:
        return run_sync_tool(_list_email_labels_impl(context.user_internal_id))

    def list_recent_threads(max_results: int = 10) -> str:
        return run_sync_tool(_list_recent_threads_impl(context.user_internal_id, max_results))

    def archive_email(message_id: str) -> str:
        return run_sync_tool(_archive_email_impl(context.user_internal_id, message_id))

    def mark_email_read(message_id: str) -> str:
        return run_sync_tool(_mark_email_read_impl(context.user_internal_id, message_id))

    def mark_email_unread(message_id: str) -> str:
        return run_sync_tool(_mark_email_unread_impl(context.user_internal_id, message_id))

    def star_email(message_id: str) -> str:
        return run_sync_tool(_star_email_impl(context.user_internal_id, message_id))

    def unstar_email(message_id: str) -> str:
        return run_sync_tool(_unstar_email_impl(context.user_internal_id, message_id))

    def trash_email(message_id: str) -> str:
        return run_sync_tool(trash_email_request(context, message_id))

    def modify_email_labels(
        message_id: str,
        add_label_ids: str = "",
        remove_label_ids: str = "",
    ) -> str:
        return run_sync_tool(modify_email_labels_request(context, message_id, add_label_ids, remove_label_ids))

    async def _draft_email_async(
        to: str,
        subject: str,
        body: str,
        cc: Optional[str],
        bcc: Optional[str],
        thread_id: Optional[str],
        reply_to_message_id: Optional[str],
    ) -> str:
        if cc or bcc or thread_id or reply_to_message_id:
            return await _draft_email_full_impl(
                context.user_internal_id,
                to,
                subject,
                body,
                cc=cc,
                bcc=bcc,
                thread_id=thread_id,
                reply_to_message_id=reply_to_message_id,
            )
        return await _draft_email_impl(context.user_internal_id, to, subject, body)

    def draft_email(
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        thread_id: Optional[str] = None,
        reply_to_message_id: Optional[str] = None,
    ) -> str:
        return run_sync_tool(
            _draft_email_async(to, subject, body, cc, bcc, thread_id, reply_to_message_id)
        )

    def send_email(to: str, subject: str, body: str) -> str:
        return run_sync_tool(send_email_request(context, to, subject, body))

    def get_calendar_events(
        days_ahead: int = 7,
        max_results: int = 20,
        calendar_id: Optional[str] = None,
    ) -> str:
        return run_sync_tool(
            _get_calendar_events_impl(context.user_internal_id, days_ahead, max_results, calendar_id)
        )

    def get_calendar_event(event_id: str) -> str:
        return run_sync_tool(_get_calendar_event_impl(context.user_internal_id, event_id))

    def get_calendar_freebusy(days_ahead: int = 7) -> str:
        return run_sync_tool(_freebusy_impl(context.user_internal_id, days_ahead))

    def create_calendar_event(
        summary: str,
        start_datetime: str,
        end_datetime: str,
        description: Optional[str] = None,
    ) -> str:
        return run_sync_tool(
            create_calendar_event_request(context, summary, start_datetime, end_datetime, description)
        )

    def update_calendar_event(
        event_id: str,
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        return run_sync_tool(
            update_calendar_event_request(
                context,
                event_id,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                summary=summary,
                description=description,
            )
        )

    def delete_calendar_event(event_id: str) -> str:
        return run_sync_tool(delete_calendar_event_request(context, event_id))

    return [
        search_emails,
        get_email_message,
        get_thread_messages,
        list_email_labels,
        list_recent_threads,
        archive_email,
        mark_email_read,
        mark_email_unread,
        star_email,
        unstar_email,
        trash_email,
        modify_email_labels,
        draft_email,
        send_email,
        get_calendar_events,
        get_calendar_event,
        get_calendar_freebusy,
        create_calendar_event,
        update_calendar_event,
        delete_calendar_event,
    ]
