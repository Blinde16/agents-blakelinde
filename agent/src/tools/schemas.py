"""Pydantic input schemas for agent tools (validation before side effects)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


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


class QueryStagingMetricsInput(BaseModel):
    upload_id: UUID = Field(..., description="UUID returned when the spreadsheet was uploaded")
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class SummarizeSheetInput(BaseModel):
    upload_id: UUID = Field(..., description="UUID returned when the spreadsheet was uploaded")


class NotionListCalendarInput(BaseModel):
    limit: int = Field(20, ge=1, le=100)
    days_ahead: int = Field(30, ge=1, le=365)


class NotionCreateCalendarInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    scheduled_date: str | None = Field(None, description="ISO date YYYY-MM-DD")
    status: str | None = Field(None, max_length=120)
    database_id: str | None = Field(None, description="Override Notion database id")


class NotionUpdateCalendarInput(BaseModel):
    page_id: str = Field(..., min_length=8, max_length=64)
    title: str | None = Field(None, max_length=500)
    scheduled_date: str | None = None
    status: str | None = Field(None, max_length=120)


class NotionCredentialsPayload(BaseModel):
    token: str = Field(..., min_length=8, description="Notion integration secret_* token")
    content_database_id: str | None = Field(None, max_length=64)


class ListRecentThreadsInput(BaseModel):
    max_results: int = Field(10, ge=1, le=30)


class GetCalendarEventsInput(BaseModel):
    days_ahead: int = Field(7, ge=1, le=90)
    max_results: int = Field(20, ge=1, le=50)


class DraftEmailInput(BaseModel):
    to: str = Field(..., min_length=3, max_length=500)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=50000)
    cc: str | None = Field(None, max_length=1000)
    bcc: str | None = Field(None, max_length=1000)
    thread_id: str | None = Field(None, description="Gmail thread id when replying in-thread")
    reply_to_message_id: str | None = Field(None, description="RFC Message-ID header for replies")


class SendEmailInput(BaseModel):
    to: str = Field(..., min_length=3, max_length=500)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=50000)


class CreateCalendarEventInput(BaseModel):
    summary: str = Field(..., min_length=1, max_length=500)
    start_datetime: str = Field(..., min_length=10, max_length=40, description="RFC3339 e.g. 2025-03-24T15:00:00Z")
    end_datetime: str = Field(..., min_length=10, max_length=40)
    description: str | None = Field(None, max_length=10000)


class GoogleSearchEmailInput(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Gmail search query (same syntax as Gmail UI)")
    max_results: int = Field(20, ge=1, le=50)


class GoogleMessageIdInput(BaseModel):
    message_id: str = Field(..., min_length=5, max_length=128)


class GoogleThreadIdInput(BaseModel):
    thread_id: str = Field(..., min_length=5, max_length=128)


class GoogleModifyLabelsInput(BaseModel):
    message_id: str = Field(..., min_length=5, max_length=128)
    add_label_ids: list[str] = Field(default_factory=list, description="Gmail label ids e.g. STARRED")
    remove_label_ids: list[str] = Field(default_factory=list)


class UpdateCalendarEventInput(BaseModel):
    event_id: str = Field(..., min_length=5, max_length=256)
    start_datetime: str | None = Field(None, max_length=40)
    end_datetime: str | None = Field(None, max_length=40)
    summary: str | None = Field(None, max_length=500)
    description: str | None = Field(None, max_length=10000)

    @model_validator(mode="after")
    def _at_least_one_patch(self) -> "UpdateCalendarEventInput":
        if not any(
            [
                self.start_datetime,
                self.end_datetime,
                self.summary is not None,
                self.description is not None,
            ]
        ):
            raise ValueError("Provide at least one of start_datetime, end_datetime, summary, or description.")
        return self


class DeleteCalendarEventInput(BaseModel):
    event_id: str = Field(..., min_length=5, max_length=256)


class FreeBusyInput(BaseModel):
    days_ahead: int = Field(7, ge=1, le=90)


class GoogleCredentialsPayload(BaseModel):
    refresh_token: str = Field(..., min_length=10, description="Google OAuth refresh token")
    google_email: str | None = Field(None, max_length=320)


class GoogleOAuthExchangePayload(BaseModel):
    code: str = Field(..., min_length=8, max_length=4096)
    redirect_uri: str = Field(..., min_length=8, max_length=2048)


_SOCIAL_PLATFORMS = ("linkedin", "x", "meta", "instagram")


class SocialCreateDraftInput(BaseModel):
    platform: str = Field(..., min_length=3, max_length=32)
    body: str = Field(..., min_length=1, max_length=50000)
    scheduled_at: str | None = Field(None, description="ISO-8601 datetime in UTC for scheduling")

    @field_validator("platform")
    @classmethod
    def _norm_platform(cls, v: str) -> str:
        p = v.strip().lower()
        if p not in _SOCIAL_PLATFORMS:
            raise ValueError(f"platform must be one of: {', '.join(_SOCIAL_PLATFORMS)}")
        return p


class SocialListQueueInput(BaseModel):
    status: str | None = Field(None, description="draft | scheduled | published | cancelled")

    @field_validator("status")
    @classmethod
    def _norm_status(cls, v: str | None) -> str | None:
        if v is None:
            return None
        x = v.strip().lower()
        if x not in ("draft", "scheduled", "published", "cancelled"):
            raise ValueError("status must be draft, scheduled, published, or cancelled")
        return x


class SocialScheduleInput(BaseModel):
    post_id: UUID = Field(..., description="social_media_posts.id")
    scheduled_at: str = Field(..., min_length=10, description="ISO-8601 UTC")


class SocialPostIdInput(BaseModel):
    post_id: UUID = Field(..., description="social_media_posts.id")

