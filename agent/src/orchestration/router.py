import re
from typing import Literal

from pydantic import BaseModel


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
    "ops": "OPS",
}

KEYWORD_TARGETS: dict[RouteTarget, tuple[str, ...]] = {
    "CFO": ("margin", "revenue", "cash", "financial", "finance", "profit", "invoice", "billing"),
    "CRO": ("deal", "hubspot", "pipeline", "crm", "stage", "sales", "prospect", "close"),
    "CMO": ("brand", "copy", "marketing", "messaging", "tone", "positioning", "campaign"),
}


class RouteDecision(BaseModel):
    target: RouteTarget
    confidence_score: float
    reasoning: str
    normalized_message: str
    active_agent: str


def route_message(message: str) -> RouteDecision:
    stripped_message = message.strip()
    slash_match = re.match(r"^/(?P<target>cfo|cro|cmo|ops)\b\s*(?P<body>.*)$", stripped_message, re.IGNORECASE)

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

    lowered = stripped_message.lower()
    matched_targets = [
        target for target, keywords in KEYWORD_TARGETS.items() if any(keyword in lowered for keyword in keywords)
    ]

    if len(matched_targets) == 1:
        target = matched_targets[0]
        return RouteDecision(
            target=target,
            confidence_score=0.92,
            reasoning=f"Matched {target} domain keywords.",
            normalized_message=stripped_message,
            active_agent=AGENT_IDS[target],
        )

    if len(set(matched_targets)) > 1:
        return RouteDecision(
            target="OPS",
            confidence_score=0.45,
            reasoning="Multiple functional domains matched; defaulting to Ops for clarification.",
            normalized_message=stripped_message,
            active_agent=AGENT_IDS["OPS"],
        )

    return RouteDecision(
        target="OPS",
        confidence_score=0.6,
        reasoning="No strong functional-domain match found.",
        normalized_message=stripped_message,
        active_agent=AGENT_IDS["OPS"],
    )
