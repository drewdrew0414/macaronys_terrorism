from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.enums import UserRole
from macaronys_backend.models import (
    DiscordChannelMapping,
    DiscordGuild,
    DiscordUserLink,
    SchoolClass,
    User,
)
from macaronys_backend.utils.time import utc_now


def parse_class_key(class_key: str) -> tuple[int | None, int | None]:
    parts = class_key.strip().split("-", 1)
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def default_class_label(class_key: str) -> str:
    grade, room = parse_class_key(class_key)
    if grade is None or room is None:
        return class_key
    return f"{grade}학년 {room}반"


async def ensure_discord_guild(
    session: AsyncSession,
    guild_id: str,
    default_channel_id: str | None = None,
) -> DiscordGuild:
    row = await session.execute(
        select(DiscordGuild).where(DiscordGuild.guild_id == guild_id)
    )
    guild = row.scalar_one_or_none()
    if guild is None:
        guild = DiscordGuild(
            guild_id=guild_id,
            default_channel_id=default_channel_id,
            enabled=True,
        )
        session.add(guild)
        await session.flush()
    elif default_channel_id:
        guild.default_channel_id = default_channel_id
    return guild


async def get_or_create_school_class_by_key(
    session: AsyncSession,
    class_key: str,
) -> SchoolClass:
    normalized = class_key.strip()
    row = await session.execute(
        select(SchoolClass).where(SchoolClass.class_key == normalized)
    )
    school_class = row.scalar_one_or_none()
    if school_class is not None:
        return school_class

    grade, room = parse_class_key(normalized)
    school_class = SchoolClass(
        class_key=normalized,
        grade=grade,
        room=room,
        label=default_class_label(normalized),
    )
    session.add(school_class)
    await session.flush()
    return school_class


async def link_discord_user(
    session: AsyncSession,
    guild_id: str,
    discord_user_id: str,
    display_name: str,
    name: str,
    birth_date: date,
    class_key: str,
    role: UserRole = UserRole.student,
) -> tuple[User, DiscordUserLink]:
    await ensure_discord_guild(session, guild_id)
    school_class = await get_or_create_school_class_by_key(session, class_key)

    row = await session.execute(
        select(DiscordUserLink)
        .where(DiscordUserLink.guild_id == guild_id)
        .where(DiscordUserLink.discord_user_id == discord_user_id)
    )
    link = row.scalar_one_or_none()

    if link is None:
        user = User(
            name=name,
            role=role.value,
            is_graduated=False,
            birth_date=birth_date,
            class_id=school_class.id,
        )
        session.add(user)
        await session.flush()
        link = DiscordUserLink(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            user_id=user.id,
            display_name=display_name,
        )
        session.add(link)
    else:
        user = await session.get(User, link.user_id)
        if user is None:
            user = User(
                name=name,
                role=role.value,
                is_graduated=False,
                birth_date=birth_date,
                class_id=school_class.id,
            )
            session.add(user)
            await session.flush()
            link.user_id = user.id
        else:
            user.name = name
            user.role = role.value
            user.birth_date = birth_date
            user.class_id = school_class.id
        link.display_name = display_name

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Discord user link already conflicts with another user",
        ) from exc

    await session.refresh(user)
    await session.refresh(link)
    return user, link


async def get_linked_user(
    session: AsyncSession,
    guild_id: str,
    discord_user_id: str,
) -> User | None:
    row = await session.execute(
        select(DiscordUserLink)
        .where(DiscordUserLink.guild_id == guild_id)
        .where(DiscordUserLink.discord_user_id == discord_user_id)
    )
    link = row.scalar_one_or_none()
    if link is None:
        return None
    return await session.get(User, link.user_id)


async def require_linked_user(
    session: AsyncSession,
    guild_id: str,
    discord_user_id: str,
) -> User:
    user = await get_linked_user(session, guild_id, discord_user_id)
    if user is None:
        raise HTTPException(
            status_code=403,
            detail="먼저 /가입 명령어로 Discord 계정과 사용자를 연결해야 합니다.",
        )
    return user


async def set_discord_channel_mapping(
    session: AsyncSession,
    guild_id: str,
    channel_id: str,
    class_key: str,
) -> DiscordChannelMapping:
    await ensure_discord_guild(session, guild_id, default_channel_id=channel_id)
    school_class = await get_or_create_school_class_by_key(session, class_key)

    row = await session.execute(
        select(DiscordChannelMapping)
        .where(DiscordChannelMapping.guild_id == guild_id)
        .where(DiscordChannelMapping.channel_id == channel_id)
    )
    mapping = row.scalar_one_or_none()
    if mapping is None:
        mapping = DiscordChannelMapping(
            guild_id=guild_id,
            channel_id=channel_id,
            class_id=school_class.id,
            channel_key=class_key,
            enabled=True,
        )
        session.add(mapping)
    else:
        mapping.class_id = school_class.id
        mapping.channel_key = class_key
        mapping.enabled = True
        mapping.updated_at = utc_now()

    await session.commit()
    await session.refresh(mapping)
    return mapping


async def get_channel_class_id(
    session: AsyncSession,
    guild_id: str,
    channel_id: str,
) -> str | None:
    row = await session.execute(
        select(DiscordChannelMapping)
        .where(DiscordChannelMapping.guild_id == guild_id)
        .where(DiscordChannelMapping.channel_id == channel_id)
        .where(DiscordChannelMapping.enabled.is_(True))
    )
    mapping = row.scalar_one_or_none()
    return mapping.class_id if mapping else None


async def resolve_context_class_id(
    session: AsyncSession,
    guild_id: str,
    channel_id: str,
    user: User,
) -> str | None:
    return await get_channel_class_id(session, guild_id, channel_id) or user.class_id
