from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from macaronys_backend.schemas.ai import AiJobRead


class SourceChatCreate(BaseModel):
    title: str = Field(default="chat", min_length=1, max_length=255)
    raw_text: str = Field(min_length=1)


class SourceTextCreate(BaseModel):
    title: str = Field(default="text", min_length=1, max_length=255)
    raw_text: str = Field(min_length=1)


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_type: str
    title: str
    storage_path: str | None
    mime_type: str | None
    file_size: int | None
    raw_text: str
    status: str
    error_message: str | None
    created_at: datetime


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    title: str
    subject: str | None
    due_at: datetime | None
    submit_method: str | None
    source_quote: str | None
    confidence: float
    status: str
    created_at: datetime


class IngestResponse(BaseModel):
    source: SourceRead
    ai_job: AiJobRead
