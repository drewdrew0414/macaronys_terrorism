from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from macaronys_backend.enums import AssignmentStatus


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    due_at: datetime
    creator_id: str | None = None
    class_id: str | None = None
    subject: str | None = Field(default=None, max_length=120)
    context: str | None = None
    submit_method: str | None = Field(default=None, max_length=255)
    submit_link: str | None = None
    reference_link: str | None = None
    is_contest: bool = False
    is_exam: bool = False
    priority: str = Field(default="normal", max_length=32)
    status: AssignmentStatus = AssignmentStatus.pending
    source_id: str | None = None
    source_quote: str | None = None
    started_at: datetime | None = None
    end_at: datetime | None = None


class AssignmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    due_at: datetime | None = None
    creator_id: str | None = None
    class_id: str | None = None
    subject: str | None = Field(default=None, max_length=120)
    context: str | None = None
    submit_method: str | None = Field(default=None, max_length=255)
    submit_link: str | None = None
    reference_link: str | None = None
    is_contest: bool | None = None
    is_exam: bool | None = None
    is_deleted: bool | None = None
    is_ended: bool | None = None
    priority: str | None = Field(default=None, max_length=32)
    status: AssignmentStatus | None = None
    source_quote: str | None = None
    started_at: datetime | None = None
    end_at: datetime | None = None


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    creator_id: str | None
    class_id: str | None
    title: str
    subject: str | None
    due_at: datetime
    context: str | None
    submit_method: str | None
    submit_link: str | None
    reference_link: str | None
    is_contest: bool
    is_exam: bool
    is_deleted: bool
    is_ended: bool
    priority: str
    status: str
    source_id: str | None
    source_quote: str | None
    remaining_seconds: int
    remaining_text: str
    created_at: datetime
    started_at: datetime
    end_at: datetime | None
    updated_at: datetime
