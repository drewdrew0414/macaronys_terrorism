from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.models import SchoolClass, User
from macaronys_backend.schemas.user import SchoolClassCreate, UserCreate


async def create_school_class(
    session: AsyncSession,
    payload: SchoolClassCreate,
) -> SchoolClass:
    existing = await session.execute(
        select(SchoolClass).where(SchoolClass.class_key == payload.class_key)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Class key already exists")

    school_class = SchoolClass(**payload.model_dump())
    session.add(school_class)
    await session.commit()
    await session.refresh(school_class)
    return school_class


async def list_school_classes(session: AsyncSession) -> list[SchoolClass]:
    rows = await session.execute(
        select(SchoolClass).order_by(SchoolClass.grade.asc(), SchoolClass.room.asc())
    )
    return list(rows.scalars().all())


async def get_user(session: AsyncSession, user_id: str) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def create_user(session: AsyncSession, payload: UserCreate) -> User:
    if payload.class_id is not None:
        school_class = await session.get(SchoolClass, payload.class_id)
        if school_class is None:
            raise HTTPException(status_code=404, detail="Class not found")

    user = User(
        name=payload.name,
        role=payload.role.value,
        is_graduated=payload.is_graduated,
        birth_date=payload.birth_date,
        class_id=payload.class_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def list_users(
    session: AsyncSession,
    class_id: str | None = None,
) -> list[User]:
    query = select(User).order_by(User.created_at.desc())
    if class_id:
        query = query.where(User.class_id == class_id)
    rows = await session.execute(query)
    return list(rows.scalars().all())
