"""HubSpot CRM tools (async httpx). Reads require token; mutations run only after approval."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from src.tools.schemas import HubSpotReadDealInput, HubSpotUpdateDealStageInput

_HUBSPOT_BASE = "https://api.hubapi.com"


def _token() -> str | None:
    return os.getenv("HUBSPOT_PRIVATE_APP_TOKEN") or os.getenv("HUBSPOT_ACCESS_TOKEN")


async def hubspot_read_deal(deal_name: str) -> str:
    """Search HubSpot deals by name fragment; returns stage, amount, and id when token is set."""
    try:
        HubSpotReadDealInput(deal_name=deal_name)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = _token()
    if not token:
        return json.dumps(
            {
                "error": "hubspot_not_configured",
                "detail": "Set HUBSPOT_PRIVATE_APP_TOKEN to enable live CRM reads.",
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


async def execute_hubspot_update_deal_stage(deal_id: str, new_stage: str) -> str:
    """PATCH deal stage (runs after human approval). Use HubSpot internal stage ids when required."""
    try:
        HubSpotUpdateDealStageInput(deal_id=deal_id, new_stage=new_stage)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "validation_error", "detail": str(exc)})

    token = _token()
    if not token:
        return json.dumps(
            {"error": "hubspot_not_configured", "detail": "Set HUBSPOT_PRIVATE_APP_TOKEN."}
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


cro_tools = [hubspot_read_deal]
