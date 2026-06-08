from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.dependencies import get_session
from macaronys_backend.schemas.user import (
    SchoolClassCreate,
    SchoolClassRead,
    UserCreate,
    UserRead,
)
from macaronys_backend.services.user_service import (
    create_school_class,
    create_user,
    list_school_classes,
    list_users,
)

router = APIRouter(tags=["users"])


@router.post("/api/school-classes", response_model=SchoolClassRead, status_code=201)
async def create_school_class_route(
    payload: SchoolClassCreate,
    session: AsyncSession = Depends(get_session),
) -> SchoolClassRead:
    school_class = await create_school_class(session, payload)
    return SchoolClassRead.model_validate(school_class)


@router.get("/api/school-classes", response_model=list[SchoolClassRead])
async def list_school_classes_route(
    session: AsyncSession = Depends(get_session),
) -> list[SchoolClassRead]:
    classes = await list_school_classes(session)
    return [SchoolClassRead.model_validate(school_class) for school_class in classes]


@router.post("/api/users", response_model=UserRead, status_code=201)
async def create_user_route(
    payload: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    user = await create_user(session, payload)
    return UserRead.model_validate(user)


@router.get("/api/users", response_model=list[UserRead])
async def list_users_route(
    class_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[UserRead]:
    users = await list_users(session, class_id=class_id)
    return [UserRead.model_validate(user) for user in users]
