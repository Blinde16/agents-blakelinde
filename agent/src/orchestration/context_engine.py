from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

EMAIL_ACTIONS: dict[str, tuple[str, ...]] = {
    "archive": ("archive", "archive it", "archive them"),
    "mark_read": ("mark read", "mark as read", "read all"),
    "mark_unread": ("mark unread", "mark as unread", "unread"),
    "star": ("star", "flag"),
    "unstar": ("unstar", "remove star"),
    "summarize": ("summarize", "summary", "recap"),
}

FOLLOW_UP_REFERENCES = {
    "those",
    "them",
    "both",
    "all",
    "these",
    "that",
    "it",
    "do it",
}


class IntentDecision(BaseModel):
    domain: Literal["CFO", "CRO", "CMO", "OPS"] = "OPS"
    intent: str = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    message_ids: list[str] = Field(default_factory=list)
    direct_action: str | None = None
    resolved_message: str
    context_patch: dict[str, Any] = Field(default_factory=dict)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def extract_message_ids(text: str) -> list[str]:
    ids: list[str] = []

    for pattern in (
        r"message_id\s*=\s*([A-Za-z0-9_-]{6,128})",
        r'"message_id"\s*:\s*"([A-Za-z0-9_-]{6,128})"',
        r"/messages/([A-Za-z0-9_-]{6,128})",
    ):
        ids.extend(re.findall(pattern, text))

    return _unique(ids)


def collect_recent_message_ids(history: list[dict[str, str]], limit: int = 10) -> list[str]:
    ids: list[str] = []
    for msg in history[-limit:]:
        ids.extend(extract_message_ids(msg.get("content", "")))
    return _unique(ids)


def _contains_followup_reference(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in FOLLOW_UP_REFERENCES)


def _detect_email_intent(text: str) -> tuple[str, float]:
    lowered = text.lower()
    if "mark" in lowered and "unread" in lowered:
        return "mark_unread", 0.93
    if "mark" in lowered and "read" in lowered:
        return "mark_read", 0.93
    for intent, keywords in EMAIL_ACTIONS.items():
        if any(k in lowered for k in keywords):
            return intent, 0.92
    return "unknown", 0.0


def _resolve_message_ids(
    user_message: str,
    prior_context: dict[str, Any],
    history: list[dict[str, str]],
) -> list[str]:
    from_user = extract_message_ids(user_message)
    if from_user:
        return from_user

    from_context = prior_context.get("selected_email_message_ids") or []
    if isinstance(from_context, list) and from_context:
        return [str(x) for x in from_context if str(x).strip()]

    return collect_recent_message_ids(history, limit=10)


def prepare_user_intent(
    user_message: str,
    *,
    prior_context: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> IntentDecision:
    prior_context = prior_context or {}
    history = history or []
    raw = user_message.strip()
    intent, confidence = _detect_email_intent(raw)

    resolved_ids = _resolve_message_ids(raw, prior_context, history)
    has_followup_ref = _contains_followup_reference(raw)
    mentions_email = any(x in raw.lower() for x in ("email", "gmail", "inbox", "message"))
    infer_email_context = bool(resolved_ids) and (has_followup_ref or mentions_email or intent != "unknown")

    if infer_email_context and intent == "archive" and resolved_ids:
        resolved_message = (
            f"Archive these Gmail message IDs: {', '.join(resolved_ids)}. "
            "Use archive_email for each message and report success/fail per ID."
        )
        return IntentDecision(
            domain="OPS",
            intent="archive",
            confidence=0.97,
            reason="Resolved follow-up archive intent from prior message IDs.",
            message_ids=resolved_ids,
            direct_action="archive_email_bulk",
            resolved_message=resolved_message,
            context_patch={
                "selected_email_message_ids": resolved_ids,
                "last_intent": "archive",
                "last_domain": "OPS",
            },
        )

    if infer_email_context and intent in {"mark_read", "mark_unread", "star", "unstar"} and resolved_ids:
        action_map = {
            "mark_read": "mark_email_read_bulk",
            "mark_unread": "mark_email_unread_bulk",
            "star": "star_email_bulk",
            "unstar": "unstar_email_bulk",
        }
        resolved_message = (
            f"Apply '{intent}' for Gmail message IDs: {', '.join(resolved_ids)}. "
            "Report per-message results."
        )
        return IntentDecision(
            domain="OPS",
            intent=intent,
            confidence=0.96,
            reason="Resolved follow-up triage action from prior message IDs.",
            message_ids=resolved_ids,
            direct_action=action_map[intent],
            resolved_message=resolved_message,
            context_patch={
                "selected_email_message_ids": resolved_ids,
                "last_intent": intent,
                "last_domain": "OPS",
            },
        )

    if infer_email_context and intent == "summarize" and resolved_ids:
        resolved_message = (
            f"Summarize these Gmail messages: {', '.join(resolved_ids)}. "
            "Fetch each with get_email_message first."
        )
        return IntentDecision(
            domain="OPS",
            intent="summarize",
            confidence=0.93,
            reason="Resolved follow-up summary intent with known message IDs.",
            message_ids=resolved_ids,
            resolved_message=resolved_message,
            context_patch={
                "selected_email_message_ids": resolved_ids,
                "last_intent": "summarize",
                "last_domain": "OPS",
            },
        )

    explicit_ids = extract_message_ids(raw)
    context_patch: dict[str, Any] = {}
    if explicit_ids:
        context_patch["selected_email_message_ids"] = explicit_ids

    return IntentDecision(
        domain="OPS" if infer_email_context else "OPS",
        intent=intent,
        confidence=confidence,
        reason="No deterministic action selected; continue normal routing.",
        message_ids=resolved_ids if infer_email_context else explicit_ids,
        resolved_message=raw,
        context_patch=context_patch,
    )
