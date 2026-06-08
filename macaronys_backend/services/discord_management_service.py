from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.enums import ClubMemberRole, CommandLogStatus
from macaronys_backend.models import (
    Club, ClubMember, CommandLog,
    Registration, TeamJoinRequest, TeamProject,
    Vote, VoteChoice, VoteResponse, VoiceRoom,
)
from macaronys_backend.utils.time import utc_now

logger = logging.getLogger("macaronys.discord.management")

CONFIG_PATH = Path("config.json")
PLACEHOLDER_VALUES = {"", "CHANNEL_ID_HERE", "GUILD_ID_HERE", "ROLE_ID_HERE"}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_log_channel_id() -> str | None:
    config = load_config()
    cid = str(
        config.get("discord", {}).get("channels", {}).get("log", {}).get("channel_id") or ""
    ).strip()
    return cid if cid and cid not in PLACEHOLDER_VALUES else None


def update_config_channels(updates: dict[str, str]) -> None:
    """updates: {channel_key: channel_id}"""
    config = load_config()
    channels = config.setdefault("discord", {}).setdefault("channels", {})
    for key, cid in updates.items():
        if key not in channels:
            channels[key] = {"label": key, "channel_id": cid, "enabled": True, "notify": True}
        else:
            channels[key]["channel_id"] = cid
    save_config(config)


def update_config_console_channel(channel_id: str) -> None:
    config = load_config()
    config.setdefault("discord", {}).setdefault("admin", {})["console_channel_id"] = channel_id
    save_config(config)


# ─── Command log ──────────────────────────────────────────────────────────────

async def save_command_log(
    session: AsyncSession,
    guild_id: str | None,
    channel_id: str | None,
    actor_discord_user_id: str,
    actor_name: str | None,
    command: str,
    options: str | None,
    status: CommandLogStatus,
    detail: str | None,
) -> CommandLog:
    log = CommandLog(
        guild_id=guild_id,
        channel_id=channel_id,
        actor_discord_user_id=actor_discord_user_id,
        actor_name=actor_name,
        command=command,
        options=options,
        status=status.value,
        detail=detail,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


# ─── Club ─────────────────────────────────────────────────────────────────────

async def get_club_by_name(
    session: AsyncSession, guild_id: str, name: str
) -> Club | None:
    row = await session.execute(
        select(Club)
        .where(Club.guild_id == guild_id)
        .where(Club.name == name)
        .where(Club.is_deleted.is_(False))
    )
    return row.scalar_one_or_none()


async def get_club_by_id(session: AsyncSession, club_id: str) -> Club | None:
    return await session.get(Club, club_id)


async def get_club_by_channel_id(session: AsyncSession, channel_id: str) -> Club | None:
    """현재 채널 ID로 동아리를 자동 감지."""
    from sqlalchemy import or_
    row = await session.execute(
        select(Club)
        .where(or_(Club.text_channel_id == channel_id, Club.voice_channel_id == channel_id))
        .where(Club.is_deleted.is_(False))
    )
    return row.scalar_one_or_none()


async def list_clubs(session: AsyncSession, guild_id: str) -> list[Club]:
    rows = await session.execute(
        select(Club)
        .where(Club.guild_id == guild_id)
        .where(Club.is_deleted.is_(False))
        .order_by(Club.created_at.asc())
    )
    return list(rows.scalars().all())


async def get_club_member(
    session: AsyncSession, club_id: str, discord_user_id: str
) -> ClubMember | None:
    row = await session.execute(
        select(ClubMember)
        .where(ClubMember.club_id == club_id)
        .where(ClubMember.discord_user_id == discord_user_id)
    )
    return row.scalar_one_or_none()


async def create_club(
    session: AsyncSession,
    guild_id: str,
    name: str,
    description: str | None,
    owner_discord_user_id: str,
    owner_display_name: str | None,
    category_id: str | None,
    text_channel_id: str | None,
    voice_channel_id: str | None,
    admin_role_id: str | None,
    member_role_id: str | None,
) -> Club:
    club = Club(
        guild_id=guild_id,
        name=name,
        description=description,
        owner_discord_user_id=owner_discord_user_id,
        category_id=category_id,
        text_channel_id=text_channel_id,
        voice_channel_id=voice_channel_id,
        admin_role_id=admin_role_id,
        member_role_id=member_role_id,
    )
    session.add(club)
    await session.flush()

    owner_member = ClubMember(
        club_id=club.id,
        discord_user_id=owner_discord_user_id,
        display_name=owner_display_name,
        member_role=ClubMemberRole.admin.value,
    )
    session.add(owner_member)
    await session.commit()
    await session.refresh(club)
    return club


async def delete_club(session: AsyncSession, club: Club) -> None:
    club.is_deleted = True
    club.updated_at = utc_now()
    await session.commit()


async def add_or_update_club_member(
    session: AsyncSession,
    club_id: str,
    discord_user_id: str,
    display_name: str | None,
    role: ClubMemberRole = ClubMemberRole.member,
) -> ClubMember:
    existing = await get_club_member(session, club_id, discord_user_id)
    if existing:
        existing.member_role = role.value
        await session.commit()
        return existing
    member = ClubMember(
        club_id=club_id,
        discord_user_id=discord_user_id,
        display_name=display_name,
        member_role=role.value,
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def transfer_club_admin(
    session: AsyncSession,
    club: Club,
    old_admin_id: str,
    new_admin_id: str,
    new_admin_name: str | None,
) -> None:
    old = await get_club_member(session, club.id, old_admin_id)
    if old:
        old.member_role = ClubMemberRole.member.value

    new = await get_club_member(session, club.id, new_admin_id)
    if new:
        new.member_role = ClubMemberRole.admin.value
    else:
        session.add(ClubMember(
            club_id=club.id,
            discord_user_id=new_admin_id,
            display_name=new_admin_name,
            member_role=ClubMemberRole.admin.value,
        ))

    club.owner_discord_user_id = new_admin_id
    club.updated_at = utc_now()
    await session.commit()


# ─── Voice room ───────────────────────────────────────────────────────────────

async def create_voice_room(
    session: AsyncSession,
    guild_id: str,
    channel_id: str,
    name: str,
    owner_discord_user_id: str,
    allowed_user_ids: list[str],
) -> VoiceRoom:
    room = VoiceRoom(
        guild_id=guild_id,
        channel_id=channel_id,
        name=name,
        owner_discord_user_id=owner_discord_user_id,
        allowed_user_ids=",".join(allowed_user_ids),
    )
    session.add(room)
    await session.commit()
    await session.refresh(room)
    return room


async def get_voice_room_by_channel(
    session: AsyncSession, channel_id: str
) -> VoiceRoom | None:
    row = await session.execute(
        select(VoiceRoom)
        .where(VoiceRoom.channel_id == channel_id)
        .where(VoiceRoom.is_closed.is_(False))
    )
    return row.scalar_one_or_none()


async def close_voice_room(session: AsyncSession, room: VoiceRoom) -> None:
    room.is_closed = True
    room.closed_at = utc_now()
    await session.commit()


# ─── Team join requests ───────────────────────────────────────────────────────

async def get_join_request(
    session: AsyncSession, project_id: str, discord_user_id: str
) -> TeamJoinRequest | None:
    row = await session.execute(
        select(TeamJoinRequest)
        .where(TeamJoinRequest.project_id == project_id)
        .where(TeamJoinRequest.requester_discord_user_id == discord_user_id)
    )
    return row.scalar_one_or_none()


async def get_join_request_by_id(
    session: AsyncSession, request_id: str
) -> TeamJoinRequest | None:
    return await session.get(TeamJoinRequest, request_id)


async def create_join_request(
    session: AsyncSession,
    project_id: str,
    discord_user_id: str,
    display_name: str | None,
    reason: str | None,
) -> TeamJoinRequest:
    existing = await get_join_request(session, project_id, discord_user_id)
    if existing:
        if existing.status == "rejected":
            existing.status = "pending"
            existing.reason = reason
            existing.updated_at = utc_now()
            await session.commit()
            return existing
        return existing
    req = TeamJoinRequest(
        project_id=project_id,
        requester_discord_user_id=discord_user_id,
        requester_display_name=display_name,
        reason=reason,
        status="pending",
    )
    session.add(req)
    await session.commit()
    await session.refresh(req)
    return req


async def approve_join_request(
    session: AsyncSession, request: TeamJoinRequest, reviewer_discord_user_id: str
) -> None:
    request.status = "approved"
    request.reviewer_discord_user_id = reviewer_discord_user_id
    request.updated_at = utc_now()
    await session.commit()


async def reject_join_request(
    session: AsyncSession, request: TeamJoinRequest, reviewer_discord_user_id: str
) -> None:
    request.status = "rejected"
    request.reviewer_discord_user_id = reviewer_discord_user_id
    request.updated_at = utc_now()
    await session.commit()


async def get_all_pending_join_requests(session: AsyncSession) -> list[TeamJoinRequest]:
    rows = await session.execute(
        select(TeamJoinRequest).where(TeamJoinRequest.status == "pending")
    )
    return list(rows.scalars().all())


async def get_active_projects_with_channels(session: AsyncSession) -> list[TeamProject]:
    rows = await session.execute(
        select(TeamProject)
        .where(TeamProject.is_deleted.is_(False))
        .where(TeamProject.text_channel_id.isnot(None))
    )
    return list(rows.scalars().all())


# ─── Registration (가입 승인) ──────────────────────────────────────────────────

async def get_registration(
    session: AsyncSession, guild_id: str, discord_user_id: str
) -> Registration | None:
    row = await session.execute(
        select(Registration)
        .where(Registration.guild_id == guild_id)
        .where(Registration.discord_user_id == discord_user_id)
        .order_by(Registration.created_at.desc())
    )
    return row.scalars().first()


async def get_registration_by_id(
    session: AsyncSession, reg_id: str
) -> Registration | None:
    return await session.get(Registration, reg_id)


async def upsert_registration(
    session: AsyncSession,
    guild_id: str,
    discord_user_id: str,
    display_name: str | None,
    name: str,
    birth_date_str: str,
    class_key: str,
) -> Registration:
    existing = await get_registration(session, guild_id, discord_user_id)
    if existing:
        existing.display_name = display_name
        existing.name = name
        existing.birth_date_str = birth_date_str
        existing.class_key = class_key
        existing.status = "pending"
        existing.reviewer_discord_user_id = None
        existing.approval_message_id = None
        existing.reject_reason = None
        existing.updated_at = utc_now()
        await session.commit()
        return existing
    reg = Registration(
        guild_id=guild_id,
        discord_user_id=discord_user_id,
        display_name=display_name,
        name=name,
        birth_date_str=birth_date_str,
        class_key=class_key,
        status="pending",
    )
    session.add(reg)
    await session.commit()
    await session.refresh(reg)
    return reg


async def approve_registration(
    session: AsyncSession, reg: Registration, reviewer_id: str
) -> None:
    reg.status = "approved"
    reg.reviewer_discord_user_id = reviewer_id
    reg.updated_at = utc_now()
    await session.commit()


async def reject_registration(
    session: AsyncSession, reg: Registration, reviewer_id: str, reason: str | None
) -> None:
    reg.status = "rejected"
    reg.reviewer_discord_user_id = reviewer_id
    reg.reject_reason = reason
    reg.updated_at = utc_now()
    await session.commit()


async def get_pending_registrations(
    session: AsyncSession, guild_id: str
) -> list[Registration]:
    rows = await session.execute(
        select(Registration)
        .where(Registration.guild_id == guild_id)
        .where(Registration.status == "pending")
        .order_by(Registration.created_at.asc())
    )
    return list(rows.scalars().all())


async def get_all_pending_registrations(session: AsyncSession) -> list[Registration]:
    rows = await session.execute(
        select(Registration).where(Registration.status == "pending")
    )
    return list(rows.scalars().all())


# ─── Vote ─────────────────────────────────────────────────────────────────────

async def create_vote(
    session: AsyncSession,
    guild_id: str,
    channel_id: str | None,
    creator_discord_user_id: str,
    question: str,
    choice_labels: list[str],
    is_anonymous: bool,
    ends_at,
) -> tuple[Vote, list[VoteChoice]]:
    vote = Vote(
        guild_id=guild_id,
        channel_id=channel_id,
        creator_discord_user_id=creator_discord_user_id,
        question=question,
        is_anonymous=is_anonymous,
        ends_at=ends_at,
    )
    session.add(vote)
    await session.flush()
    choices = [
        VoteChoice(vote_id=vote.id, label=label.strip(), position=i)
        for i, label in enumerate(choice_labels)
    ]
    session.add_all(choices)
    await session.commit()
    await session.refresh(vote)
    return vote, choices


async def get_vote_by_id(session: AsyncSession, vote_id: str) -> Vote | None:
    return await session.get(Vote, vote_id)


async def get_vote_choices(
    session: AsyncSession, vote_id: str
) -> list[VoteChoice]:
    rows = await session.execute(
        select(VoteChoice)
        .where(VoteChoice.vote_id == vote_id)
        .order_by(VoteChoice.position.asc())
    )
    return list(rows.scalars().all())


async def record_vote(
    session: AsyncSession, vote_id: str, choice_id: str, discord_user_id: str
) -> tuple[bool, str | None]:
    """Return (success, previous_choice_id_or_None)."""
    existing = await session.execute(
        select(VoteResponse)
        .where(VoteResponse.vote_id == vote_id)
        .where(VoteResponse.discord_user_id == discord_user_id)
    )
    prev = existing.scalar_one_or_none()
    if prev:
        if prev.choice_id == choice_id:
            return False, prev.choice_id
        prev.choice_id = choice_id
        await session.commit()
        return True, prev.choice_id
    resp = VoteResponse(vote_id=vote_id, choice_id=choice_id, discord_user_id=discord_user_id)
    session.add(resp)
    await session.commit()
    return True, None


async def get_vote_results(
    session: AsyncSession, vote_id: str
) -> list[tuple[str, int]]:
    """Returns [(choice_id, count), ...] ordered by position."""
    choices = await get_vote_choices(session, vote_id)
    results = []
    for ch in choices:
        row = await session.execute(
            select(VoteResponse).where(VoteResponse.choice_id == ch.id)
        )
        count = len(row.scalars().all())
        results.append((ch.id, ch.label, count))
    return results


async def close_vote(session: AsyncSession, vote: Vote) -> None:
    vote.is_closed = True
    await session.commit()


async def get_active_votes(session: AsyncSession) -> list[Vote]:
    rows = await session.execute(
        select(Vote).where(Vote.is_closed.is_(False))
    )
    return list(rows.scalars().all())
