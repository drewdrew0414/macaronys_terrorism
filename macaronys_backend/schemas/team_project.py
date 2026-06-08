from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamProjectCreate(BaseModel):
    maker_id: str
    title: str = Field(min_length=1, max_length=255)
    context: str = Field(min_length=1)
    max_members: int = Field(ge=1, le=50)
    assignment_id: str | None = None
    class_id: str | None = None


class TeamProjectRead(BaseModel):
    id: str
    maker_id: str
    assignment_id: str | None
    class_id: str | None
    title: str
    context: str
    max_members: int
    current_member_count: int
    status: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    ended_at: datetime | None


class TeamProjectMemberJoin(BaseModel):
    user_id: str
    role: str | None = Field(default=None, max_length=40)


class TeamProjectMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    user_id: str
    role: str | None
    status: str
    joined_at: datetime


class TeamProjectComplete(BaseModel):
    actor_id: str


class PeerReviewCreate(BaseModel):
    writer_id: str
    target_id: str
    rating: int = Field(ge=1, le=5)
    reason: str | None = None
    position: str = Field(min_length=1, max_length=40)


class PeerReviewRead(BaseModel):
    id: str
    project_id: str
    target_id: str
    rating: int
    reason: str | None
    position: str
    created_at: datetime


class PeerReviewSummary(BaseModel):
    target_id: str
    target_name: str
    review_count: int
    average_rating: float
