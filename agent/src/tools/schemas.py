"""Pydantic input schemas for agent tools (validation before side effects)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HubSpotReadDealInput(BaseModel):
    deal_name: str = Field(..., min_length=1, description="Deal or company name to search")


class HubSpotUpdateDealStageInput(BaseModel):
    deal_id: str = Field(..., min_length=1, description="HubSpot deal object id")
    new_stage: str = Field(..., min_length=1, description="Target pipeline stage id or label per HubSpot")


class ClientMarginInput(BaseModel):
    client_name: str = Field(..., min_length=1, description="Client name or key")


class RevenueSummaryInput(BaseModel):
    timeframe: str = Field(..., min_length=2, description="YTD, Q1, LAST_MONTH, etc.")


class BrandKnowledgeInput(BaseModel):
    query: str = Field(..., min_length=1, description="Semantic search query for brand guidelines")


class CurrentTimeInput(BaseModel):
    pass
