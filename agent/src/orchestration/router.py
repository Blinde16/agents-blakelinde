import json
import logging
import os
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


RouteTarget = Literal["CFO", "CRO", "CMO", "OPS"]

AGENT_IDS: dict[RouteTarget, str] = {
    "CFO": "Finance_Layer",
    "CRO": "Sales_Ops_Layer",
    "CMO": "Brand_Layer",
    "OPS": "Operations_Layer",
}

SLASH_TARGETS: dict[str, RouteTarget] = {
    "cfo": "CFO",
    "cro": "CRO",
    "cmo": "CMO",
    "social": "CMO",
    "ops": "OPS",
}

KEYWORD_TARGETS: dict[RouteTarget, tuple[str, ...]] = {
    "CFO": ("margin", "revenue", "cash", "financial", "finance", "profit", "invoice", "billing"),
    "CRO": ("deal", "hubspot", "pipeline", "crm", "stage", "sales", "prospect", "close"),
    "OPS": (
        "inbox",
        "gmail",
        "email",
        "unread",
        "reschedule",
        "calendar invite",
        "meeting invite",
        "freebusy",
        "free busy",
        "google calendar",
        "calendar",
        "appointment",
        "availability",
        "schedule a meeting",
        "my calendar",
        "draft a reply",
        "reply to",
    ),
    "CMO": (
        "brand",
        "copy",
        "marketing",
        "messaging",
        "tone",
        "positioning",
        "campaign",
        "newsletter",
        "content calendar",
        "social",
        "linkedin",
        "instagram",
        "twitter",
        "x post",
        "feed",
        "scheduled post",
    ),
}

KEYWORD_PRIORITY: tuple[RouteTarget, ...] = ("CFO", "CRO", "CMO", "OPS")


class RouteDecision(BaseModel):
    target: RouteTarget
    confidence_score: float
    reasoning: str
    normalized_message: str
    active_agent: str


class _LLMRouteSchema(BaseModel):
    target: RouteTarget
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(..., min_length=1, max_length=500)

    @field_validator("target", mode="before")
    @classmethod
    def _normalize_target(cls, v: object) -> str:
        if isinstance(v, str):
            u = v.strip().upper()
            if u in ("CFO", "CRO", "CMO", "OPS"):
                return u
        raise ValueError("invalid target")


def _should_use_llm_router() -> bool:
    if os.getenv("OPENAI_API_KEY", "").strip() == "":
        return False
    flag = os.getenv("ROUTER_USE_LLM", "1").strip().lower()
    return flag not in ("0", "false", "no", "off")


def _keyword_route(stripped_message: str) -> RouteDecision:
    lowered = stripped_message.lower()
    matched_targets = [
        target for target, keywords in KEYWORD_TARGETS.items() if any(keyword in lowered for keyword in keywords)
    ]

    unique = list(dict.fromkeys(matched_targets))
    if len(unique) == 1:
        target = unique[0]
        return RouteDecision(
            target=target,
            confidence_score=0.92,
            reasoning=f"Matched {target} domain keywords.",
            normalized_message=stripped_message,
            active_agent=AGENT_IDS[target],
        )

    if len(unique) > 1:
        for target in KEYWORD_PRIORITY:
            if target in unique:
                return RouteDecision(
                    target=target,
                    confidence_score=0.78,
                    reasoning=(
                        "Multiple domain keywords matched; selected by specialist priority "
                        "(CFO→CRO→CMO→OPS) — keyword fallback."
                    ),
                    normalized_message=stripped_message,
                    active_agent=AGENT_IDS[target],
                )

    return RouteDecision(
        target="OPS",
        confidence_score=0.6,
        reasoning="No strong functional-domain match found (keyword fallback).",
        normalized_message=stripped_message,
        active_agent=AGENT_IDS["OPS"],
    )


async def _llm_classify_route(
    stripped_message: str,
    history: list[dict[str, str]] | None = None,
) -> RouteDecision:
    from openai import AsyncOpenAI

    from src.prompts.loader import load_prompt

    system_prompt = load_prompt("router.md")
    model = os.getenv("OPENAI_ROUTER_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    llm_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if history:
        for msg in history[-6:]:
            role = msg.get("role", "user")
            if role not in ("user", "assistant"):
                role = "user"
            llm_messages.append({"role": role, "content": (msg.get("content") or "")[:800]})
    llm_messages.append({"role": "user", "content": stripped_message})

    resp = await client.chat.completions.create(
        model=model,
        temperature=0.0,
        max_tokens=200,
        response_format={"type": "json_object"},
        messages=llm_messages,
    )

    raw = (resp.choices[0].message.content or "").strip()
    if not raw:
        raise ValueError("empty router model response")

    data = json.loads(raw)
    parsed = _LLMRouteSchema.model_validate(data)
    target = parsed.target

    return RouteDecision(
        target=target,
        confidence_score=round(float(parsed.confidence), 4),
        reasoning=f"LLM router: {parsed.reasoning}",
        normalized_message=stripped_message,
        active_agent=AGENT_IDS[target],
    )


async def route_message(
    message: str,
    history: list[dict[str, str]] | None = None,
) -> RouteDecision:
    stripped_message = message.strip()
    slash_match = re.match(
        r"^/(?P<target>cfo|cro|cmo|social|ops)\b\s*(?P<body>.*)$", stripped_message, re.IGNORECASE
    )

    if slash_match:
        target = SLASH_TARGETS[slash_match.group("target").lower()]
        normalized_message = slash_match.group("body").strip() or stripped_message
        return RouteDecision(
            target=target,
            confidence_score=1.0,
            reasoning="Explicit slash command route.",
            normalized_message=normalized_message,
            active_agent=AGENT_IDS[target],
        )

    if _should_use_llm_router():
        try:
            return await _llm_classify_route(stripped_message, history=history)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM router failed; using keyword fallback: %s", exc)
            decision = _keyword_route(stripped_message)
            return RouteDecision(
                target=decision.target,
                confidence_score=decision.confidence_score,
                reasoning=f"{decision.reasoning} (LLM router unavailable; keyword fallback.)",
                normalized_message=decision.normalized_message,
                active_agent=decision.active_agent,
            )

    return _keyword_route(stripped_message)
