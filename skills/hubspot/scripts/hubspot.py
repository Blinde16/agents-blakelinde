"""HubSpot CRM tools (async httpx). Reads require token; mutations run only after approval."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

import json
import os
from typing import Any
import asyncio
import httpx
import fire

_HUBSPOT_BASE = "https://api.hubapi.com"


def _token() -> str | None:
    return (
        os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
        or os.getenv("HUBSPOT_ACCESS_TOKEN")
        or os.getenv("HUBSPOT_API_KEY")
    )


async def _hubspot_read_deal_async(deal_name: str) -> str:
    """Search HubSpot deals by name fragment; returns stage, amount, and id when token is set."""
    # removed pydantic validation for simple CLI execution

    token = _token()
    if not token:
        return json.dumps(
            {
                "error": "hubspot_not_configured",
                "detail": "Set HUBSPOT_PRIVATE_APP_TOKEN (or HUBSPOT_ACCESS_TOKEN / HUBSPOT_API_KEY) for live CRM reads.",
            }
        )

    body: dict[str, Any] = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "dealname",
                        "operator": "CONTAINS_TOKEN",
                        "value": deal_name.strip(),
                    }
                ]
            }
        ],
        "properties": ["dealname", "amount", "dealstage", "pipeline", "hs_object_id"],
        "limit": 5,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{_HUBSPOT_BASE}/crm/v3/objects/deals/search",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )

    if resp.status_code >= 400:
        return json.dumps(
            {"error": "hubspot_api_error", "status": resp.status_code, "body": resp.text[:2000]}
        )

    data = resp.json()
    results = data.get("results") or []
    if not results:
        return json.dumps({"detail": f"No deals found matching {deal_name!r}."})

    out: list[dict[str, Any]] = []
    for r in results:
        pid = r.get("id")
        props = r.get("properties") or {}
        out.append(
            {
                "deal_id": str(pid),
                "deal_name": props.get("dealname"),
                "amount": props.get("amount"),
                "dealstage": props.get("dealstage"),
                "pipeline": props.get("pipeline"),
            }
        )
    return json.dumps({"deals": out}, indent=2)


def read_deal(deal_name: str) -> str:
    return asyncio.run(_hubspot_read_deal_async(deal_name))


async def execute_hubspot_update_deal_stage(deal_id: str, new_stage: str) -> str:
    """PATCH deal stage (runs after human approval). Use HubSpot internal stage ids when required."""
    # removed pydantic validation

    token = _token()
    if not token:
        return json.dumps(
            {
                "error": "hubspot_not_configured",
                "detail": "Set HUBSPOT_PRIVATE_APP_TOKEN (or HUBSPOT_ACCESS_TOKEN / HUBSPOT_API_KEY).",
            }
        )

    # HubSpot expects numeric object id for v3 path
    clean_id = deal_id.strip()
    payload = {"properties": {"dealstage": new_stage.strip()}}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(
            f"{_HUBSPOT_BASE}/crm/v3/objects/deals/{clean_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code >= 400:
        return json.dumps(
            {
                "error": "hubspot_update_failed",
                "status": resp.status_code,
                "body": resp.text[:2000],
            }
        )

    data = resp.json()
    props = data.get("properties") or {}
    return json.dumps(
        {
            "status": "success",
            "deal_id": clean_id,
            "dealstage": props.get("dealstage"),
            "message": "Deal stage updated.",
        }
    )


def update_deal_stage(deal_id: str, new_stage: str) -> str:
    return asyncio.run(execute_hubspot_update_deal_stage(deal_id, new_stage))

if __name__ == "__main__":
    fire.Fire({
        "read_deal": read_deal,
        "update_deal_stage": update_deal_stage
    })
