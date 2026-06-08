from __future__ import annotations

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field

from macaronys_backend.enums import NotificationChannel


class NotificationRuleWrite(BaseModel):
    offset_minutes: int = Field(ge=0)
    channel: NotificationChannel = NotificationChannel.app
    enabled: bool = True
    quiet_start: time | None = None
    quiet_end: time | None = None


class NotificationRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    offset_minutes: int
    channel: str
    enabled: bool
    quiet_start: time | None
    quiet_end: time | None
    created_at: datetime
    updated_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    assignment_id: str
    channel: str
    scheduled_at: datetime
    sent_at: datetime | None
    status: str
    message: str
    error_message: str | None
    created_at: datetime


class RebuildNotificationsResponse(BaseModel):
    assignment_id: str
    created_count: int


class DispatchNotificationsResponse(BaseModel):
    claimed_count: int
    sent_count: int
    failed_count: int
