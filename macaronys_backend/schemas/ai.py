from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AiJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    job_type: str
    status: str
    result_text: str | None
    error_message: str | None
    attempts: int
    locked_by: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class LocalAiJobRead(BaseModel):
    id: str
    source_id: str
    job_type: str
    model: str
    prompt: str


class LocalAiJobResult(BaseModel):
    success: bool
    result_text: str | None = None
    error_message: str | None = None
