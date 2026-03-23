"""Extract plain text from Gmail API message/thread payloads (nested MIME)."""

from __future__ import annotations

import base64
from typing import Any


def _b64decode(data: str) -> str:
    pad = 4 - len(data) % 4
    if pad != 4:
        data += "=" * pad
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def extract_plain_text_from_payload(payload: dict[str, Any]) -> str:
    """Best-effort plain text from a Gmail message payload part tree."""
    if not payload:
        return ""

    body = payload.get("body") or {}
    if body.get("data"):
        return _b64decode(body["data"])

    mime = (payload.get("mimeType") or "").lower()
    if mime == "text/plain" and body.get("data"):
        return _b64decode(body["data"])

    for part in payload.get("parts") or []:
        ptype = (part.get("mimeType") or "").lower()
        if ptype == "text/plain":
            b = part.get("body") or {}
            if b.get("data"):
                return _b64decode(b["data"])
        nested = extract_plain_text_from_payload(part)
        if nested.strip():
            return nested

    return ""


def extract_headers(message: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for h in message.get("payload", {}).get("headers") or []:
        name = (h.get("name") or "").lower()
        if name in ("from", "to", "subject", "date", "cc", "message-id"):
            out[h.get("name") or ""] = h.get("value") or ""
    return out
