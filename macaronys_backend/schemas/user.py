from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from macaronys_backend.enums import UserRole


class SchoolClassCreate(BaseModel):
    class_key: str = Field(min_length=1, max_length=20)
    label: str = Field(min_length=1, max_length=60)
    grade: int | None = Field(default=None, ge=1, le=12)
    room: int | None = Field(default=None, ge=1, le=99)


class SchoolClassRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    class_key: str
    grade: int | None
    room: int | None
    label: str
    created_at: datetime


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    role: UserRole = UserRole.student
    is_graduated: bool = False
    birth_date: date
    class_id: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    role: str
    is_graduated: bool
    birth_date: date
    class_id: str | None
    created_at: datetime
    updated_at: datetime
