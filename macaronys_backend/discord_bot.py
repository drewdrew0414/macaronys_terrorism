from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks
from fastapi import HTTPException
from sqlalchemy import or_, select

from macaronys_backend.config import settings
from macaronys_backend.database import SessionLocal, close_db, init_db
from macaronys_backend.enums import (
    AssignmentStatus,
    CandidateStatus,
    ClubMemberRole,
    CommandLogStatus,
    SourceType,
    TeamProjectStatus,
)
from macaronys_backend.models import TeamJoinRequest
from macaronys_backend.models import (
    Assignment,
    DiscordChannelMapping,
    DiscordModerationLog,
    DiscordUserLink,
    SchoolClass,
    TeamProject,
    User,
)
from macaronys_backend.schemas.assignment import AssignmentCreate
from macaronys_backend.schemas.team_project import (
    PeerReviewCreate,
    TeamProjectCreate,
)
from macaronys_backend.services.assignment_service import (
    create_assignment,
    list_assignments,
)
from macaronys_backend.schemas.ai import LocalAiJobResult
from macaronys_backend.services.ai_job_service import submit_ai_job_result
from macaronys_backend.services.document_parser import (
    detect_source_type,
    extract_text_from_file,
)
from macaronys_backend.services.file_storage import safe_filename
from macaronys_backend.services.ollama_client import OllamaGemmaClient
from macaronys_backend.services.source_service import (
    create_source_and_ai_job,
    list_candidates,
)
from macaronys_backend.models import Registration, Vote, VoteChoice, VoteResponse
from macaronys_backend.services.discord_management_service import (
    add_or_update_club_member,
    approve_join_request,
    approve_registration,
    close_voice_room,
    close_vote,
    create_club,
    create_join_request,
    create_voice_room,
    create_vote,
    delete_club,
    get_active_projects_with_channels,
    get_active_votes,
    get_all_pending_join_requests,
    get_all_pending_registrations,
    get_club_by_channel_id,
    get_club_by_name,
    get_club_member,
    get_join_request,
    get_join_request_by_id,
    get_log_channel_id,
    get_pending_registrations,
    get_registration_by_id,
    get_voice_room_by_channel,
    get_vote_by_id,
    get_vote_choices,
    get_vote_results,
    list_clubs,
    list_recent_notices,
    record_vote,
    reject_join_request,
    reject_registration,
    save_command_log,
    save_notice,
    transfer_club_admin,
    update_config_channels,
    update_config_console_channel,
    upsert_registration,
)
from macaronys_backend.services.discord_service import (
    get_channel_class_id,
    get_linked_user,
    get_or_create_school_class_by_key,
    link_discord_user,
    require_linked_user,
    resolve_context_class_id,
    set_discord_channel_mapping,
)
from macaronys_backend.services.notification_service import (
    rebuild_notifications_for_assignment,
)
from macaronys_backend.services.neis_service import (
    build_meal_embeds,
    build_timetable_embeds,
    fetch_meal,
    fetch_timetable,
    kst_now,
    kst_date_str,
    parse_class_for_neis,
)
from macaronys_backend.services.notification_dispatcher import dispatch_due_notifications
from macaronys_backend.services.team_project_service import (
    complete_team_project,
    create_team_project,
    join_team_project,
    list_project_review_summary,
    list_team_projects,
    list_user_reviews,
    submit_peer_review,
)
from macaronys_backend.utils.time import app_tz, ensure_aware, new_id, remaining_text, utc_now

logger = logging.getLogger("macaronys.discord")
PLACEHOLDER_VALUES = {"", "CHANNEL_ID_HERE", "GUILD_ID_HERE", "ROLE_ID_HERE"}
MENTION_ID_PATTERN = re.compile(r"\d{15,25}")
AUTOCOMPLETE_LIMIT = 25

# 학급 클래스 키 목록 (1-1 ~ 3-4)
CLASS_KEYS: list[str] = [f"{g}-{r}" for g in range(1, 4) for r in range(1, 5)]

# 카테고리/채널 이름 상수
CAT_CLASS = "📚 학급"
CAT_TEACHER = "👩‍🏫 교직원"
CAT_ADMIN = "🔒 관리"
CAT_CLUB = "🎯 동아리"
CAT_VOICE = "🎙️ 음성방"
CAT_TEAM = "🏃 팀 프로젝트"
TEACHER_ROLE_NAME = "선생님"
LOG_CHANNEL_NAME = "로그"
CONSOLE_CHANNEL_NAME = "콘솔"
TEACHER_CHANNEL_NAME = "선생님"
RECRUITMENT_CHANNEL_NAME = "팀원모집"

# 학생이 쓸 수 있는 명령어 (이외는 선생님/관리자만)
STUDENT_ALLOWED_COMMANDS = {
    "가입", "과제목록", "과제스캔", "공지목록", "팀원모집", "팀목록", "팀참여", "팀완료",
    "팀평가", "팀평가보기", "음성방생성", "반명단",
    "급식", "시간표",
    # 동아리 명령어 - 내부에서 권한 체크
    "동아리멤버추가", "동아리관리자양도", "동아리관리자추가", "동아리삭제", "동아리목록",
}

# 학년 → 반 목록 매핑
GRADE_CLASS_MAP: dict[str, list[str]] = {
    "1학년": [f"1-{r}" for r in range(1, 5)],
    "2학년": [f"2-{r}" for r in range(1, 5)],
    "3학년": [f"3-{r}" for r in range(1, 5)],
}


def resolve_class_targets(value: str) -> list[str]:
    """'all', '1학년', '1-1' 등을 class key 목록으로 변환."""
    v = value.strip()
    if v.lower() == "all":
        return CLASS_KEYS
    if v in GRADE_CLASS_MAP:
        return GRADE_CLASS_MAP[v]
    return [v]


async def resolve_target_class_ids(session, value: str) -> list[tuple[str, str]]:
    """대상 입력('all'/'1학년'/'1-1')을 [(class_key, class_id), ...]로 변환한다.

    선생님이 콘솔·선생님 채널처럼 반과 연결되지 않은 곳에서 명령을 쓸 때,
    대상 반/학년을 직접 지정할 수 있게 해 준다. 존재하지 않는 학급은 생성한다.
    유효한 학급 키(1-1~3-4)만 받아들이고, 하나도 없으면 빈 목록을 돌려준다.
    """
    keys = [k for k in resolve_class_targets(value) if k in CLASS_KEYS]
    pairs: list[tuple[str, str]] = []
    for class_key in keys:
        school_class = await get_or_create_school_class_by_key(session, class_key)
        pairs.append((class_key, school_class.id))
    return pairs


def class_target_choices(current: str) -> list[app_commands.Choice[str]]:
    """대상 반/학년 자동완성: 전체 / 1~3학년 / 1-1~3-4."""
    options: list[tuple[str, str]] = [
        ("전체 (all)", "all"),
        ("1학년 전체", "1학년"),
        ("2학년 전체", "2학년"),
        ("3학년 전체", "3학년"),
    ] + [(ck, ck) for ck in CLASS_KEYS]
    needle = current.strip().lower()
    return [
        app_commands.Choice(name=name, value=value)
        for name, value in options
        if not needle or needle in name.lower() or needle in value.lower()
    ][:AUTOCOMPLETE_LIMIT]


async def autocomplete_class_target(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return class_target_choices(current)


# ─── 모던 임베드 헬퍼 ────────────────────────────────────────────────────────

def build_log_embed(
    command: str,
    actor: discord.Member | discord.User,
    channel: discord.abc.GuildChannel | None,
    success: bool,
    detail: str | None = None,
    extra_fields: list[tuple[str, str, bool]] | None = None,
) -> discord.Embed:
    color = 0x57F287 if success else 0xED4245
    status_text = "✅ 성공" if success else "❌ 실패"
    embed = discord.Embed(
        title=f"{'📋'} 명령어 로그",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="명령어", value=f"`/{command}`", inline=True)
    embed.add_field(name="실행자", value=f"{actor.mention}\n`{actor.display_name}`", inline=True)
    embed.add_field(
        name="채널",
        value=channel.mention if channel else "알 수 없음",
        inline=True,
    )
    embed.add_field(name="결과", value=status_text, inline=True)
    if detail:
        embed.add_field(name="상세", value=detail[:1000], inline=False)
    if extra_fields:
        for name, value, inline in extra_fields:
            embed.add_field(name=name, value=value, inline=inline)
    embed.set_footer(text=f"Actor ID: {actor.id}")
    return embed


async def send_log(
    bot_instance: commands.Bot,
    embed: discord.Embed,
) -> None:
    log_cid = get_log_channel_id()
    if not log_cid:
        return
    try:
        ch = bot_instance.get_channel(int(log_cid))
        if ch is None:
            ch = await bot_instance.fetch_channel(int(log_cid))
        if isinstance(ch, discord.TextChannel):
            await ch.send(embed=embed)
    except Exception:
        logger.exception("Failed to send log embed to log channel")


async def log_interaction(
    interaction: discord.Interaction,
    command: str,
    options: str | None,
    success: bool,
    detail: str | None = None,
    extra_fields: list[tuple[str, str, bool]] | None = None,
) -> None:
    guild_id = str(interaction.guild_id) if interaction.guild_id else None
    channel_id = str(interaction.channel_id) if interaction.channel_id else None
    actor = interaction.user
    channel = interaction.channel if isinstance(interaction.channel, discord.abc.GuildChannel) else None

    status = CommandLogStatus.success if success else CommandLogStatus.failure
    try:
        async with SessionLocal() as session:
            await save_command_log(
                session,
                guild_id=guild_id,
                channel_id=channel_id,
                actor_discord_user_id=str(actor.id),
                actor_name=actor.display_name,
                command=command,
                options=options,
                status=status,
                detail=detail,
            )
    except Exception:
        logger.exception("Failed to save command log to DB")

    embed = build_log_embed(command, actor, channel, success, detail, extra_fields)
    await send_log(interaction.client, embed)


# ─── 역할/채널 유틸 ──────────────────────────────────────────────────────────

def has_teacher_discord_role(member: discord.Member) -> bool:
    return any(r.name == TEACHER_ROLE_NAME for r in member.roles)


def is_teacher_or_admin(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    if interaction.user.guild_permissions.administrator:
        return True
    return has_teacher_discord_role(interaction.user)


def require_teacher_or_admin_role(interaction: discord.Interaction) -> None:
    if not is_teacher_or_admin(interaction):
        raise HTTPException(
            status_code=403,
            detail="선생님 역할 또는 Discord 관리자만 사용할 수 있습니다.",
        )


async def get_or_create_role(
    guild: discord.Guild,
    name: str,
    *,
    color: discord.Color = discord.Color.default(),
    mentionable: bool = False,
    hoist: bool = False,
) -> discord.Role:
    existing = discord.utils.get(guild.roles, name=name)
    if existing:
        return existing
    return await guild.create_role(
        name=name, color=color, mentionable=mentionable, hoist=hoist
    )


async def get_or_create_category(
    guild: discord.Guild, name: str
) -> discord.CategoryChannel:
    existing = discord.utils.get(guild.categories, name=name)
    if existing:
        return existing
    return await guild.create_category(name=name)


def load_runtime_config() -> dict:
    path = Path("config.json")
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def configured_console_channel_id() -> str | None:
    config = load_runtime_config()
    discord_config = config.get("discord", {})
    admin_config = discord_config.get("admin", {})
    configured = str(admin_config.get("console_channel_id") or "").strip()
    if configured and configured not in PLACEHOLDER_VALUES:
        return configured

    console_channel = discord_config.get("channels", {}).get("console", {})
    configured = str(console_channel.get("channel_id") or "").strip()
    if configured and configured not in PLACEHOLDER_VALUES:
        return configured
    return None


def configured_teacher_channel_id() -> str | None:
    config = load_runtime_config()
    cid = str(
        config.get("discord", {}).get("channels", {}).get("teacher", {}).get("channel_id") or ""
    ).strip()
    return cid if cid and cid not in PLACEHOLDER_VALUES else None


def configured_recruitment_channel_id() -> str | None:
    config = load_runtime_config()
    cid = str(
        config.get("discord", {}).get("channels", {}).get("recruitment", {}).get("channel_id") or ""
    ).strip()
    return cid if cid and cid not in PLACEHOLDER_VALUES else None


def configured_class_key_for_channel(channel_id: str | None) -> str | None:
    if not channel_id:
        return None
    config = load_runtime_config()
    channels = config.get("discord", {}).get("channels", {})
    for class_key, item in channels.items():
        if class_key not in CLASS_KEYS or not isinstance(item, dict):
            continue
        cid = str(item.get("channel_id") or "").strip()
        if cid and cid not in PLACEHOLDER_VALUES and cid == channel_id:
            return class_key
    return None


def class_key_from_channel_name(channel: object | None) -> str | None:
    name = str(getattr(channel, "name", "") or "")
    match = re.search(r"([1-3])\s*(?:-|_|학년)\s*([1-4])", name)
    if not match:
        return None
    class_key = f"{match.group(1)}-{match.group(2)}"
    return class_key if class_key in CLASS_KEYS else None


async def resolve_timetable_class_key(interaction: discord.Interaction) -> str:
    class_key = configured_class_key_for_channel(channel_id_from(interaction))
    if class_key:
        return class_key

    class_key = class_key_from_channel_name(interaction.channel)
    if class_key:
        return class_key

    async with SessionLocal() as session:
        cid = await get_channel_class_id(
            session,
            guild_id_from(interaction),
            channel_id_from(interaction),
        )
        if cid:
            school_class = await session.get(SchoolClass, cid)
            if school_class is not None:
                return school_class.class_key

        try:
            user = await require_linked_user(
                session,
                guild_id_from(interaction),
                str(interaction.user.id),
            )
        except Exception:
            user = None
        if user is not None and user.class_id:
            school_class = await session.get(SchoolClass, user.class_id)
            if school_class is not None:
                return school_class.class_key

    raise HTTPException(
        status_code=422,
        detail="현재 채널의 반을 찾을 수 없습니다. config.json의 discord.channels에 채널 ID를 넣거나 /반채널연동을 먼저 실행하세요.",
    )


def is_staff_channel(interaction: discord.Interaction) -> bool:
    """콘솔 또는 선생님 채널인지 확인."""
    cid_str = str(interaction.channel_id) if interaction.channel_id else None
    console_id = configured_console_channel_id()
    teacher_id = configured_teacher_channel_id()

    if console_id and cid_str == console_id:
        return True
    if teacher_id and cid_str == teacher_id:
        return True

    # 채널 ID가 하나라도 설정돼 있으면 이름 폴백을 허용하지 않는다.
    # (학생이 채널 이름을 "콘솔"로 위장해 우회하는 것을 방지)
    if console_id or teacher_id:
        return False

    # 양쪽 모두 미설정 시에만 이름으로 폴백 (초기 설정 전용)
    ch = interaction.channel
    if ch:
        name = getattr(ch, "name", "")
        if name in (CONSOLE_CHANNEL_NAME, "console", "콘솔", TEACHER_CHANNEL_NAME):
            return True
    return False


def is_console_channel(interaction: discord.Interaction) -> bool:
    return is_staff_channel(interaction)


def require_console_channel(interaction: discord.Interaction) -> None:
    if not is_staff_channel(interaction):
        raise HTTPException(
            status_code=403,
            detail=f"이 명령어는 콘솔 또는 선생님 채널에서만 사용할 수 있습니다.",
        )


def require_guild(interaction: discord.Interaction) -> discord.Guild:
    if interaction.guild is None:
        raise HTTPException(status_code=400, detail="서버 안에서만 사용할 수 있습니다.")
    return interaction.guild


def require_discord_admin(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.user, discord.Member):
        raise HTTPException(status_code=403, detail="서버 멤버만 사용할 수 있습니다.")
    if not interaction.user.guild_permissions.administrator:
        raise HTTPException(status_code=403, detail="Discord 관리자 권한이 필요합니다.")


def parse_member_ids(value: str) -> list[int]:
    seen: set[int] = set()
    member_ids: list[int] = []
    for match in MENTION_ID_PATTERN.findall(value):
        member_id = int(match)
        if member_id not in seen:
            seen.add(member_id)
            member_ids.append(member_id)
    return member_ids


async def fetch_members_by_ids(
    guild: discord.Guild,
    raw_members: str,
) -> tuple[list[discord.Member], list[int]]:
    members: list[discord.Member] = []
    missing: list[int] = []
    for member_id in parse_member_ids(raw_members):
        member = guild.get_member(member_id)
        if member is None:
            try:
                member = await guild.fetch_member(member_id)
            except discord.NotFound:
                missing.append(member_id)
                continue
        members.append(member)
    return members, missing


def role_is_manageable(interaction: discord.Interaction, role: discord.Role) -> bool:
    bot_member = interaction.guild.me if interaction.guild else None
    return bool(bot_member and role < bot_member.top_role)


def assert_role_manageable(interaction: discord.Interaction, role: discord.Role) -> None:
    if role.is_default():
        raise HTTPException(status_code=422, detail="@everyone 역할은 수정할 수 없습니다.")
    if not role_is_manageable(interaction, role):
        raise HTTPException(
            status_code=403,
            detail=f"봇 역할이 `{role.name}`보다 위에 있어야 합니다.",
        )


def assert_confirmation(actual: str, expected: str) -> None:
    if actual.strip() != expected:
        raise HTTPException(
            status_code=422,
            detail=f"확인 문구가 필요합니다: `{expected}`",
        )


async def members_with_role(guild: discord.Guild, role: discord.Role) -> list[discord.Member]:
    members = list(role.members)
    if members:
        return members

    resolved: list[discord.Member] = []
    async for member in guild.fetch_members(limit=None):
        if role in member.roles:
            resolved.append(member)
    return resolved


async def report_bulk_result(
    interaction: discord.Interaction,
    action: str,
    success_count: int,
    failed: list[str],
    missing: list[int] | None = None,
) -> None:
    lines = [f"{action} 완료: 성공 {success_count}명, 실패 {len(failed)}명"]
    if missing:
        lines.append(f"찾지 못한 사용자 ID: {', '.join(str(item) for item in missing[:10])}")
    if failed:
        lines.append("실패 목록:")
        lines.extend(failed[:10])
    await interaction.followup.send("\n".join(lines), ephemeral=True)


def require_teacher_or_admin(interaction: discord.Interaction, user: User) -> None:
    if user.role == "teacher":
        return
    if isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator:
        return
    raise HTTPException(status_code=403, detail="선생님 또는 Discord 관리자만 사용할 수 있습니다.")


async def write_moderation_log(
    interaction: discord.Interaction,
    action: str,
    target: str | None,
    details: str | None,
    success_count: int,
    failure_count: int,
) -> None:
    try:
        async with SessionLocal() as session:
            session.add(
                DiscordModerationLog(
                    guild_id=guild_id_from(interaction),
                    channel_id=str(interaction.channel_id) if interaction.channel_id else None,
                    actor_discord_user_id=str(interaction.user.id),
                    action=action,
                    target=target,
                    details=details,
                    success_count=success_count,
                    failure_count=failure_count,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to write Discord moderation log")


def parse_birth_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("생년월일은 YYYY-MM-DD 형식이어야 합니다.") from exc


def parse_due_at(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return ensure_aware(datetime.fromisoformat(normalized))
    except ValueError as exc:
        raise ValueError("마감 시각은 YYYY-MM-DD HH:MM 또는 ISO 형식이어야 합니다.") from exc


def guild_id_from(interaction: discord.Interaction) -> str:
    if interaction.guild_id is None:
        raise HTTPException(status_code=400, detail="서버 안에서만 사용할 수 있습니다.")
    return str(interaction.guild_id)


def channel_id_from(interaction: discord.Interaction) -> str:
    if interaction.channel_id is None:
        raise HTTPException(status_code=400, detail="채널 안에서만 사용할 수 있습니다.")
    return str(interaction.channel_id)


async def send_error(interaction: discord.Interaction, error: Exception) -> None:
    inner = getattr(error, "original", error)
    detail = getattr(inner, "detail", None) or str(inner)
    embed = discord.Embed(title="⚠️ 오류", description=detail, color=0xED4245)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception:
        pass


def format_assignment(assignment: Assignment) -> str:
    _, remain = remaining_text(assignment.due_at)
    subject = f" [{assignment.subject}]" if assignment.subject else ""
    return f"- `{assignment.id[:8]}`{subject} {assignment.title} / {remain}"


def format_team_project(project) -> str:
    return (
        f"- `{project.id[:8]}` {project.title} "
        f"({project.current_member_count}/{project.max_members}, {project.status})"
    )


def autocomplete_choice_name(*parts: object, max_length: int = 100) -> str:
    text = " / ".join(str(part).strip() for part in parts if str(part).strip())
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def text_matches_current(current: str, *values: object) -> bool:
    needle = current.strip().lower()
    if not needle:
        return True
    return any(needle in str(value).lower() for value in values if value is not None)


def configured_class_choices(current: str) -> list[app_commands.Choice[str]]:
    config = load_runtime_config()
    classes = config.get("school", {}).get("classes", [])
    choices: list[app_commands.Choice[str]] = []
    for item in classes:
        class_key = str(item.get("key") or "").strip()
        label = str(item.get("label") or class_key).strip()
        if not class_key or not text_matches_current(current, class_key, label):
            continue
        choices.append(
            app_commands.Choice(
                name=autocomplete_choice_name(class_key, label),
                value=class_key,
            )
        )
    return choices[:AUTOCOMPLETE_LIMIT]


async def autocomplete_class_key(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    try:
        async with SessionLocal() as session:
            rows = await session.execute(
                select(SchoolClass).order_by(SchoolClass.class_key.asc())
            )
            classes = rows.scalars().all()
    except Exception:
        logger.exception("Failed to build class autocomplete choices")
        return configured_class_choices(current)

    if not classes:
        return configured_class_choices(current)

    return [
        app_commands.Choice(
            name=autocomplete_choice_name(item.class_key, item.label),
            value=item.class_key,
        )
        for item in classes
        if text_matches_current(current, item.class_key, item.label)
    ][:AUTOCOMPLETE_LIMIT]


async def autocomplete_assignment_id(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    try:
        async with SessionLocal() as session:
            query = (
                select(Assignment)
                .where(Assignment.is_deleted.is_(False))
                .where(Assignment.status != AssignmentStatus.done.value)
                .order_by(Assignment.due_at.asc())
                .limit(100)
            )
            if current.strip():
                keyword = f"%{current.strip()}%"
                query = query.where(
                    or_(
                        Assignment.id.ilike(keyword),
                        Assignment.title.ilike(keyword),
                        Assignment.subject.ilike(keyword),
                    )
                )
            rows = await session.execute(query)
            assignments = rows.scalars().all()
    except Exception:
        logger.exception("Failed to build assignment autocomplete choices")
        return []

    return [
        app_commands.Choice(
            name=autocomplete_choice_name(
                item.title,
                item.subject,
                item.due_at.strftime("%m-%d %H:%M"),
                item.id[:8],
            ),
            value=item.id,
        )
        for item in assignments
    ][:AUTOCOMPLETE_LIMIT]


async def autocomplete_team_project_id(
    interaction: discord.Interaction,
    current: str,
    statuses: set[str] | None = None,
) -> list[app_commands.Choice[str]]:
    try:
        async with SessionLocal() as session:
            query = (
                select(TeamProject)
                .where(TeamProject.is_deleted.is_(False))
                .order_by(TeamProject.created_at.desc())
                .limit(100)
            )
            if statuses:
                query = query.where(TeamProject.status.in_(statuses))
            if current.strip():
                keyword = f"%{current.strip()}%"
                query = query.where(
                    or_(
                        TeamProject.id.ilike(keyword),
                        TeamProject.title.ilike(keyword),
                    )
                )
            rows = await session.execute(query)
            projects = rows.scalars().all()
    except Exception:
        logger.exception("Failed to build team project autocomplete choices")
        return []

    return [
        app_commands.Choice(
            name=autocomplete_choice_name(
                item.title,
                item.status,
                f"{item.max_members}명",
                item.id[:8],
            ),
            value=item.id,
        )
        for item in projects
    ][:AUTOCOMPLETE_LIMIT]


# ─── 공용 페이지네이션 View ──────────────────────────────────────────────────

class PaginationView(discord.ui.View):
    """여러 embed를 이전/다음 버튼으로 넘기는 범용 뷰 (ephemeral 전용, 비영구적)."""

    def __init__(
        self,
        embeds: list[discord.Embed],
        page_labels: list[str],
        start: int = 0,
    ) -> None:
        super().__init__(timeout=180)
        self.embeds = embeds
        self.page_labels = page_labels
        self.current = start
        self._rebuild()

    def _rebuild(self) -> None:
        self.clear_items()
        if self.current > 0:
            prev = discord.ui.Button(
                label=f"◀ {self.page_labels[self.current - 1]}",
                style=discord.ButtonStyle.secondary,
                custom_id="page_prev",
            )
            prev.callback = self._prev
            self.add_item(prev)

        indicator = discord.ui.Button(
            label=f"{self.current + 1} / {len(self.embeds)}",
            style=discord.ButtonStyle.primary,
            disabled=True,
            custom_id="page_indicator",
        )
        self.add_item(indicator)

        if self.current < len(self.embeds) - 1:
            nxt = discord.ui.Button(
                label=f"{self.page_labels[self.current + 1]} ▶",
                style=discord.ButtonStyle.secondary,
                custom_id="page_next",
            )
            nxt.callback = self._next
            self.add_item(nxt)

    async def _prev(self, interaction: discord.Interaction) -> None:
        self.current -= 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.embeds[self.current], view=self)

    async def _next(self, interaction: discord.Interaction) -> None:
        self.current += 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.embeds[self.current], view=self)


# ─── 팀원 모집 UI (Persistent Views) ─────────────────────────────────────────

class JoinRequestModal(discord.ui.Modal, title="📝 팀 참가 신청"):
    reason = discord.ui.TextInput(
        label="신청 사유",
        placeholder="이 팀에 참가하고 싶은 이유를 적어주세요 (최대 300자)",
        style=discord.TextStyle.paragraph,
        min_length=5,
        max_length=300,
    )

    def __init__(self, project_id: str) -> None:
        super().__init__()
        self._project_id = project_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            if guild is None:
                await interaction.followup.send("서버 안에서만 사용할 수 있습니다.", ephemeral=True)
                return

            async with SessionLocal() as session:
                existing = await get_join_request(
                    session, self._project_id, str(interaction.user.id)
                )
                if existing and existing.status == "pending":
                    await interaction.followup.send("이미 참가 신청이 접수 중입니다.", ephemeral=True)
                    return
                if existing and existing.status == "approved":
                    await interaction.followup.send("이미 승인된 팀원입니다.", ephemeral=True)
                    return

                req = await create_join_request(
                    session,
                    project_id=self._project_id,
                    discord_user_id=str(interaction.user.id),
                    display_name=interaction.user.display_name,
                    reason=self.reason.value,
                )

                # 팀 채널에 승인 요청 전송
                from sqlalchemy import select as sa_select
                from macaronys_backend.models import TeamProject
                proj = await session.get(TeamProject, self._project_id)
                if proj and proj.text_channel_id:
                    ch = guild.get_channel(int(proj.text_channel_id))
                    if isinstance(ch, discord.TextChannel):
                        embed = discord.Embed(
                            title="📬 새 참가 신청",
                            color=0xFEE75C,
                            timestamp=datetime.now(timezone.utc),
                        )
                        embed.add_field(name="신청자", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
                        embed.add_field(name="팀", value=proj.title, inline=True)
                        embed.add_field(name="사유", value=self.reason.value, inline=False)
                        embed.set_footer(text=f"신청자 ID: {interaction.user.id}")
                        view = ApprovalView(req.id)
                        msg = await ch.send(embed=embed, view=view)
                        req.approval_message_id = str(msg.id)
                        await session.commit()

            await interaction.followup.send(
                "✅ 참가 신청이 접수됐습니다. 팀장의 승인을 기다려 주세요.", ephemeral=True
            )
        except Exception as exc:
            logger.exception("JoinRequestModal submit error")
            await interaction.followup.send(f"오류 발생: {exc}", ephemeral=True)


class RecruitmentView(discord.ui.View):
    def __init__(self, project_id: str) -> None:
        super().__init__(timeout=None)
        self._project_id = project_id
        btn = discord.ui.Button(
            label="✋ 참가 신청",
            style=discord.ButtonStyle.success,
            custom_id=f"recruit_join:{project_id}",
        )
        btn.callback = self._on_join
        self.add_item(btn)

    async def _on_join(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(JoinRequestModal(self._project_id))


class ApprovalView(discord.ui.View):
    def __init__(self, request_id: str) -> None:
        super().__init__(timeout=None)
        self._request_id = request_id

        approve_btn = discord.ui.Button(
            label="✅ 수락",
            style=discord.ButtonStyle.success,
            custom_id=f"join_approve:{request_id}",
        )
        approve_btn.callback = self._approve
        self.add_item(approve_btn)

        reject_btn = discord.ui.Button(
            label="❌ 거절",
            style=discord.ButtonStyle.danger,
            custom_id=f"join_reject:{request_id}",
        )
        reject_btn.callback = self._reject
        self.add_item(reject_btn)

    async def _check_authority(
        self,
        interaction: discord.Interaction,
        proj: "TeamProject",
        guild: discord.Guild,
        session,
    ) -> bool:
        """수락/거절 권한 확인: 팀장이거나 선생님/관리자여야 합니다."""
        actor = interaction.user
        if isinstance(actor, discord.Member):
            if actor.guild_permissions.administrator:
                return True
            if has_teacher_discord_role(actor):
                return True
        # 팀장 확인 (maker_id → DiscordUserLink → discord_user_id)
        link_row = await session.execute(
            select(DiscordUserLink)
            .where(DiscordUserLink.user_id == proj.maker_id)
            .where(DiscordUserLink.guild_id == str(guild.id))
        )
        maker_link = link_row.scalar_one_or_none()
        return bool(maker_link and maker_link.discord_user_id == str(actor.id))

    async def _approve(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            if guild is None:
                await interaction.followup.send("서버 안에서만 사용할 수 있습니다.", ephemeral=True)
                return
            async with SessionLocal() as session:
                req = await get_join_request_by_id(session, self._request_id)
                if req is None or req.status != "pending":
                    await interaction.followup.send("이미 처리된 신청입니다.", ephemeral=True)
                    return

                proj = await session.get(TeamProject, req.project_id)
                if proj is None:
                    return

                # ─── 권한 확인 ───────────────────────────────────────────────
                if not await self._check_authority(interaction, proj, guild, session):
                    await interaction.followup.send(
                        "팀장 또는 선생님/관리자만 참가 신청을 처리할 수 있습니다.", ephemeral=True
                    )
                    return

                # 팀원 추가
                from macaronys_backend.services.discord_service import get_linked_user
                requester_user = await get_linked_user(
                    session, str(guild.id), req.requester_discord_user_id
                )
                if requester_user:
                    try:
                        await join_team_project(session, proj.id, requester_user.id, role=None)
                    except Exception:
                        pass

                # Discord 역할 부여
                if proj.team_role_id:
                    role = guild.get_role(int(proj.team_role_id))
                    member = guild.get_member(int(req.requester_discord_user_id))
                    if role and member:
                        await member.add_roles(role, reason="팀 참가 승인")

                await approve_join_request(session, req, str(interaction.user.id))
                proj_title = proj.title

            # 메시지 업데이트
            embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else discord.Embed(title="참가 신청")
            embed.color = 0x57F287
            embed.title = "✅ 참가 신청 수락됨"
            for item in self.children:
                item.disabled = True  # type: ignore[attr-defined]
            await interaction.message.edit(embed=embed, view=self)

            # 신청자에게 DM 알림
            try:
                requester = guild.get_member(int(req.requester_discord_user_id))
                if requester:
                    await requester.send(f"🎉 **{proj_title}** 참가 신청이 **수락**됐습니다!")
            except Exception:
                pass
        except Exception as exc:
            logger.exception("ApprovalView approve error")
            await interaction.followup.send(f"오류: {exc}", ephemeral=True)

    async def _reject(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            if guild is None:
                await interaction.followup.send("서버 안에서만 사용할 수 있습니다.", ephemeral=True)
                return
            async with SessionLocal() as session:
                req = await get_join_request_by_id(session, self._request_id)
                if req is None or req.status != "pending":
                    await interaction.followup.send("이미 처리된 신청입니다.", ephemeral=True)
                    return
                proj = await session.get(TeamProject, req.project_id)
                if proj is None:
                    return

                # ─── 권한 확인 ───────────────────────────────────────────────
                if not await self._check_authority(interaction, proj, guild, session):
                    await interaction.followup.send(
                        "팀장 또는 선생님/관리자만 참가 신청을 처리할 수 있습니다.", ephemeral=True
                    )
                    return

                await reject_join_request(session, req, str(interaction.user.id))
                proj_title = proj.title

            embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else discord.Embed(title="참가 신청")
            embed.color = 0xED4245
            embed.title = "❌ 참가 신청 거절됨"
            for item in self.children:
                item.disabled = True  # type: ignore[attr-defined]
            await interaction.message.edit(embed=embed, view=self)

            try:
                requester = guild.get_member(int(req.requester_discord_user_id))
                if requester:
                    await requester.send(f"😔 **{proj_title}** 참가 신청이 **거절**됐습니다.")
            except Exception:
                pass
        except Exception as exc:
            logger.exception("ApprovalView reject error")
            await interaction.followup.send(f"오류: {exc}", ephemeral=True)


# ─── 가입 승인 View ───────────────────────────────────────────────────────────

def class_admin_role_name(class_key: str) -> str:
    return f"{class_key}-관리자"


def has_class_admin_role(member: discord.Member, class_key: str) -> bool:
    return any(r.name == class_admin_role_name(class_key) for r in member.roles)


class RegistrationApprovalView(discord.ui.View):
    def __init__(self, reg_id: str) -> None:
        super().__init__(timeout=None)
        self._reg_id = reg_id

        approve_btn = discord.ui.Button(
            label="✅ 승인",
            style=discord.ButtonStyle.success,
            custom_id=f"reg_approve:{reg_id}",
        )
        approve_btn.callback = self._approve
        self.add_item(approve_btn)

        reject_btn = discord.ui.Button(
            label="❌ 거절",
            style=discord.ButtonStyle.danger,
            custom_id=f"reg_reject:{reg_id}",
        )
        reject_btn.callback = self._reject
        self.add_item(reject_btn)

    def _can_approve(self, interaction: discord.Interaction, class_key: str) -> bool:
        actor = interaction.user
        if not isinstance(actor, discord.Member):
            return False
        if actor.guild_permissions.administrator:
            return True
        if has_teacher_discord_role(actor):
            return True
        if has_class_admin_role(actor, class_key):
            return True
        return False

    async def _approve(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            if guild is None:
                return
            async with SessionLocal() as session:
                reg = await get_registration_by_id(session, self._reg_id)
                if reg is None or reg.status != "pending":
                    await interaction.followup.send("이미 처리된 신청입니다.", ephemeral=True)
                    return
                if not self._can_approve(interaction, reg.class_key):
                    await interaction.followup.send(
                        f"승인 권한이 없습니다. 선생님, `{reg.class_key}-관리자` 역할 또는 Discord 관리자가 처리할 수 있습니다.",
                        ephemeral=True,
                    )
                    return

                # 유저 DB 연동
                from macaronys_backend.services.discord_service import link_discord_user
                from datetime import date as _date
                bd = _date.fromisoformat(reg.birth_date_str)
                user, _ = await link_discord_user(
                    session,
                    guild_id=reg.guild_id,
                    discord_user_id=reg.discord_user_id,
                    display_name=reg.display_name or reg.name,
                    name=reg.name,
                    birth_date=bd,
                    class_key=reg.class_key,
                )

                await approve_registration(session, reg, str(interaction.user.id))
                class_key = reg.class_key

            # Discord 역할 배정
            member = guild.get_member(int(reg.discord_user_id))
            if member:
                old = [r for r in member.roles if r.name in CLASS_KEYS]
                if old:
                    await member.remove_roles(*old, reason="가입 승인: 기존 반 역할 제거")
                new_role = discord.utils.get(guild.roles, name=class_key)
                if new_role:
                    await member.add_roles(new_role, reason=f"가입 승인: {class_key}")
                try:
                    await member.send(f"🎉 **{class_key}반** 가입이 **승인**됐습니다! 이제 반 채널에 접근할 수 있습니다.")
                except Exception:
                    pass

            # 메시지 업데이트
            if interaction.message:
                embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed(title="가입 신청")
                embed.color = 0x57F287
                embed.title = f"✅ 가입 승인됨 — {class_key}"
                for item in self.children:
                    item.disabled = True  # type: ignore[attr-defined]
                await interaction.message.edit(embed=embed, view=self)

            await interaction.followup.send("가입 승인 완료.", ephemeral=True)
        except Exception as exc:
            logger.exception("RegistrationApprovalView approve error")
            await interaction.followup.send(f"오류: {exc}", ephemeral=True)

    async def _reject(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(RegistrationRejectModal(self._reg_id, self))


class RegistrationRejectModal(discord.ui.Modal, title="거절 사유"):
    reason = discord.ui.TextInput(
        label="거절 사유 (선택)",
        placeholder="사유를 입력하세요 (생략 가능)",
        required=False,
        max_length=200,
    )

    def __init__(self, reg_id: str, view: RegistrationApprovalView) -> None:
        super().__init__()
        self._reg_id = reg_id
        self._view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            if guild is None:
                return
            async with SessionLocal() as session:
                reg = await get_registration_by_id(session, self._reg_id)
                if reg is None or reg.status != "pending":
                    await interaction.followup.send("이미 처리된 신청입니다.", ephemeral=True)
                    return
                if not self._view._can_approve(interaction, reg.class_key):
                    await interaction.followup.send("거절 권한이 없습니다.", ephemeral=True)
                    return
                await reject_registration(session, reg, str(interaction.user.id), self.reason.value or None)
                class_key = reg.class_key

            member = guild.get_member(int(reg.discord_user_id))
            if member:
                reason_txt = f": {self.reason.value}" if self.reason.value else ""
                try:
                    await member.send(f"😔 **{class_key}반** 가입이 **거절**됐습니다{reason_txt}. 담당 선생님께 문의하세요.")
                except Exception:
                    pass

            if interaction.message:
                embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed(title="가입 신청")
                embed.color = 0xED4245
                embed.title = f"❌ 가입 거절됨 — {class_key}"
                for item in self._view.children:
                    item.disabled = True  # type: ignore[attr-defined]
                await interaction.message.edit(embed=embed, view=self._view)

            await interaction.followup.send("가입 거절 처리 완료.", ephemeral=True)
        except Exception as exc:
            logger.exception("RegistrationRejectModal error")
            await interaction.followup.send(f"오류: {exc}", ephemeral=True)


# ─── 투표 View ────────────────────────────────────────────────────────────────

class VoteView(discord.ui.View):
    def __init__(self, vote_id: str, choices: list[tuple[str, str]]) -> None:
        # choices: [(choice_id, label), ...]
        super().__init__(timeout=None)
        self._vote_id = vote_id
        for choice_id, label in choices[:8]:
            btn = discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"vote:{vote_id}:{choice_id}",
            )
            btn.callback = self._make_callback(choice_id)
            self.add_item(btn)

    def _make_callback(self, choice_id: str):
        async def _cb(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                async with SessionLocal() as session:
                    vote = await get_vote_by_id(session, self._vote_id)
                    if vote is None or vote.is_closed:
                        await interaction.followup.send("투표가 종료됐습니다.", ephemeral=True)
                        return
                    changed, _ = await record_vote(
                        session, self._vote_id, choice_id, str(interaction.user.id)
                    )
                    results = await get_vote_results(session, self._vote_id)

                total = sum(cnt for _, _, cnt in results)
                lines = []
                for _, lbl, cnt in results:
                    bar = "█" * cnt + "░" * max(0, total - cnt)
                    pct = f"{cnt/total*100:.0f}%" if total > 0 else "0%"
                    lines.append(f"{lbl}: {cnt}표 ({pct}) {bar[:10]}")

                embed = discord.Embed(
                    title=f"📊 투표 중간 결과",
                    description="\n".join(lines) or "아직 투표 없음",
                    color=0x5865F2,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as exc:
                await interaction.followup.send(f"오류: {exc}", ephemeral=True)
        return _cb


def build_vote_results_embed(
    vote: Vote,
    results: list[tuple[str, str, int]],
    closed: bool = False,
) -> discord.Embed:
    total = sum(cnt for _, _, cnt in results)
    lines = []
    for _, lbl, cnt in results:
        pct = f"{cnt/total*100:.1f}%" if total > 0 else "0%"
        filled = round((cnt / total * 10)) if total > 0 else 0
        bar = "█" * filled + "░" * (10 - filled)
        lines.append(f"**{lbl}** — {cnt}표 ({pct})\n{bar}")
    embed = discord.Embed(
        title=f"{'🔒 투표 종료' if closed else '📊 투표 현황'}: {vote.question}",
        description="\n\n".join(lines) or "아직 투표가 없습니다.",
        color=0xED4245 if closed else 0x5865F2,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"총 {total}표 | 투표 ID: {vote.id[:8]}")
    return embed


# ─── 알림 자동 발송 (background task) ────────────────────────────────────────

@tasks.loop(minutes=1)
async def _notification_dispatch_task() -> None:
    try:
        async with SessionLocal() as session:
            summary = await dispatch_due_notifications(session)
            if summary.sent_count > 0:
                logger.info("자동 알림 발송: %d건", summary.sent_count)
    except Exception:
        logger.exception("자동 알림 발송 실패")


@_notification_dispatch_task.before_loop
async def _before_dispatch() -> None:
    await bot.wait_until_ready()


@tasks.loop(minutes=1)
async def _vote_close_task() -> None:
    """마감 시각이 지난 투표를 자동으로 종료하고 결과를 채널에 전송."""
    try:
        from macaronys_backend.utils.time import utc_now as _utc_now
        now = _utc_now()
        async with SessionLocal() as session:
            votes = await get_active_votes(session)
            for vote in votes:
                if vote.ends_at and vote.ends_at <= now:
                    await close_vote(session, vote)
                    choices = await get_vote_choices(session, vote.id)
                    results = await get_vote_results(session, vote.id)
                    embed = build_vote_results_embed(vote, results, closed=True)

                    if vote.channel_id:
                        try:
                            ch = bot.get_channel(int(vote.channel_id))
                            if isinstance(ch, discord.TextChannel):
                                # 원본 메시지 버튼 비활성화
                                if vote.message_id:
                                    try:
                                        msg = await ch.fetch_message(int(vote.message_id))
                                        closed_view = discord.ui.View()
                                        for btn in VoteView(vote.id, [(c.id, c.label) for c in choices]).children:
                                            btn.disabled = True  # type: ignore[attr-defined]
                                            closed_view.add_item(btn)
                                        await msg.edit(view=closed_view)
                                    except Exception:
                                        pass
                                await ch.send(embed=embed)
                        except Exception as e:
                            logger.warning("투표 결과 전송 실패 %s: %s", vote.id, e)
    except Exception:
        logger.exception("투표 자동 종료 실패")


@_vote_close_task.before_loop
async def _before_vote_close() -> None:
    await bot.wait_until_ready()


@tasks.loop(minutes=5)
async def _recruitment_expiry_task() -> None:
    """모집 마감(3일)이 지난 팀원모집을 만료 처리하고 팀장에게 DM으로 알린다."""
    try:
        now = utc_now()
        expired: list[dict] = []
        async with SessionLocal() as session:
            rows = await session.execute(
                select(TeamProject)
                .where(TeamProject.is_deleted.is_(False))
                .where(TeamProject.status == TeamProjectStatus.recruiting.value)
                .where(TeamProject.recruit_deadline.is_not(None))
                .where(TeamProject.recruit_deadline <= now)
            )
            for proj in rows.scalars().all():
                proj.status = TeamProjectStatus.cancelled.value
                link_row = await session.execute(
                    select(DiscordUserLink)
                    .where(DiscordUserLink.user_id == proj.maker_id)
                    .limit(1)
                )
                link = link_row.scalar_one_or_none()
                expired.append(
                    {
                        "id": proj.id,
                        "title": proj.title,
                        "message_id": proj.recruitment_message_id,
                        "maker_discord_id": link.discord_user_id if link else None,
                    }
                )
            if expired:
                await session.commit()

        if not expired:
            return

        recruit_cid = configured_recruitment_channel_id()
        for item in expired:
            # 1) 팀장에게 만료 DM
            maker_id = item["maker_discord_id"]
            if maker_id:
                try:
                    maker = bot.get_user(int(maker_id)) or await bot.fetch_user(int(maker_id))
                    await maker.send(
                        f"⏰ 팀 **{item['title']}** 의 팀원 모집이 3일이 지나 **만료**되었습니다. "
                        f"계속 모집하려면 `/팀원모집`으로 새로 열어 주세요."
                    )
                except Exception:
                    logger.warning("모집 만료 DM 실패: %s", item["id"])

            # 2) 모집 메시지 버튼 비활성화 + 만료 표시
            if recruit_cid and item["message_id"]:
                try:
                    ch = bot.get_channel(int(recruit_cid)) or await bot.fetch_channel(int(recruit_cid))
                    if isinstance(ch, discord.TextChannel):
                        msg = await ch.fetch_message(int(item["message_id"]))
                        embed = msg.embeds[0] if msg.embeds else discord.Embed(title="팀원 모집")
                        embed.title = f"⛔ 모집 만료: {item['title']}"
                        embed.color = 0x99AAB5
                        await msg.edit(embed=embed, view=None)
                except Exception:
                    logger.warning("모집 메시지 만료 처리 실패: %s", item["id"])

        logger.info("팀원모집 만료 처리: %d건", len(expired))
    except Exception:
        logger.exception("팀원모집 만료 처리 실패")


@_recruitment_expiry_task.before_loop
async def _before_recruitment_expiry() -> None:
    await bot.wait_until_ready()


# ─── AI 과제 추출 (순차 처리 큐) ──────────────────────────────────────────────
#
# Discord에서 들어온 공지/파일을 로컬 Ollama Gemma로 추출한다.
# 모델은 한 번에 하나만 돌리는 게 안정적이라, 단일 워커가 FIFO로 "순서대로"
# 처리한다. 요청이 몰리면 그냥 대기열에 쌓이고 차례가 오면 처리된다.

SCAN_MAX_CHARS = 24000          # 프롬프트에 넣을 본문 상한
SCAN_SUPPORTED_HINT = "PDF 또는 TXT 파일, 혹은 공지 텍스트를 보내주세요."


class _ScanTask:
    """추출 큐에 들어가는 단위 작업."""

    def __init__(
        self,
        *,
        job_id: str,
        source_id: str,
        prompt: str,
        title: str,
        requester_id: int,
        guild_id: str | None,
        channel: discord.abc.Messageable,
        target: str | None = None,
    ) -> None:
        self.job_id = job_id
        self.source_id = source_id
        self.prompt = prompt
        self.title = title
        self.requester_id = requester_id
        self.guild_id = guild_id
        self.channel = channel
        self.target = target  # 등록 대상 반/학년 (예: 1-1, 1학년, all). None이면 본인 반


class AiScanQueue:
    """단일 워커로 AI 추출 작업을 순차 처리하는 인-프로세스 큐."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[_ScanTask] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._client = OllamaGemmaClient(settings)
        self._processing = False

    def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run(), name="discord-ai-scan-worker")
            logger.info("AI 스캔 큐 워커 시작")

    async def submit(self, task: _ScanTask) -> int:
        """작업을 큐에 넣고, 이 작업 앞에 처리 대기 중인 건수를 돌려준다."""
        ahead = self._queue.qsize() + (1 if self._processing else 0)
        await self._queue.put(task)
        return ahead

    async def _run(self) -> None:
        while True:
            task = await self._queue.get()
            self._processing = True
            try:
                await self._process(task)
            except Exception:
                logger.exception("AI 스캔 처리 실패: job=%s", task.job_id)
                try:
                    await task.channel.send(
                        embed=discord.Embed(
                            title="⚠️ AI 추출 중 오류",
                            description="처리 중 문제가 발생했어요. 잠시 후 다시 시도해 주세요.",
                            color=0xED4245,
                        )
                    )
                except Exception:
                    pass
            finally:
                self._processing = False
                self._queue.task_done()

    async def _process(self, task: _ScanTask) -> None:
        # 1) 모델 호출 → 결과를 기존 파이프라인(submit_ai_job_result)으로 저장
        async with SessionLocal() as session:
            try:
                result_text = await self._client.generate(task.prompt)
            except Exception as exc:
                await submit_ai_job_result(
                    session,
                    task.job_id,
                    LocalAiJobResult(success=False, error_message=str(exc)),
                )
                await task.channel.send(
                    embed=discord.Embed(
                        title="⚠️ AI 추출 실패",
                        description=f"모델 호출에 실패했어요.\n`{str(exc)[:500]}`",
                        color=0xED4245,
                    )
                )
                return
            await submit_ai_job_result(
                session,
                task.job_id,
                LocalAiJobResult(success=True, result_text=result_text),
            )

        # 2) 저장된 후보를 불러와 사용자에게 결과 전송
        async with SessionLocal() as session:
            candidates = await list_candidates(session, task.source_id)
        await send_scan_results(task, candidates)


ai_scan_queue = AiScanQueue()


def _write_scan_temp(data: bytes, filename: str) -> Path:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / f"{new_id()}-{safe_filename(filename)}"
    path.write_bytes(data)
    return path


async def build_scan_text(
    content: str | None,
    attachments: list[discord.Attachment],
) -> tuple[str, str]:
    """텍스트와 첨부(PDF/TXT)에서 추출 대상 본문과 제목을 만든다."""
    parts: list[str] = []
    title: str | None = None

    if content and content.strip():
        parts.append(content.strip())

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    for att in attachments:
        filename = att.filename or "file"
        if att.size and att.size > max_bytes:
            parts.append(f"[{filename}: 파일이 너무 커서 건너뜀]")
            continue
        try:
            source_type = detect_source_type(filename, att.content_type)
        except HTTPException:
            continue  # 지원하지 않는 형식은 무시
        try:
            data = await att.read()
            path = _write_scan_temp(data, filename)
            text = await asyncio.to_thread(extract_text_from_file, path, source_type)
        except Exception:
            logger.exception("첨부 파싱 실패: %s", filename)
            continue
        if text.strip():
            parts.append(f"[{filename}]\n{text.strip()}")
            if title is None:
                title = filename

    raw = "\n\n".join(parts).strip()
    if len(raw) > SCAN_MAX_CHARS:
        raw = raw[:SCAN_MAX_CHARS]

    if title is None:
        snippet = (content or "").strip().splitlines()[0] if content and content.strip() else "chat"
        title = (snippet[:40] or "chat")
    return raw, title


async def enqueue_scan(
    *,
    raw_text: str,
    title: str,
    requester_id: int,
    guild_id: str | None,
    channel: discord.abc.Messageable,
    target: str | None = None,
) -> int:
    """자료/AI잡을 만들고(외부 워커가 못 가져가게 잠금) 순차 큐에 넣는다."""
    async with SessionLocal() as session:
        source, job = await create_source_and_ai_job(
            session,
            source_type=SourceType.discord,
            title=title[:255],
            raw_text=raw_text,
            claimed_by="discord-scan",
        )
    task = _ScanTask(
        job_id=job.id,
        source_id=source.id,
        prompt=job.prompt,
        title=title,
        requester_id=requester_id,
        guild_id=guild_id,
        channel=channel,
        target=target,
    )
    return await ai_scan_queue.submit(task)


def _format_candidate_field(candidate) -> tuple[str, str]:
    name = f"📌 {candidate.title[:230]}"
    lines: list[str] = []
    if candidate.subject:
        lines.append(f"과목: {candidate.subject}")
    if candidate.due_at:
        local = ensure_aware(candidate.due_at).astimezone(app_tz())
        _, remain = remaining_text(candidate.due_at)
        lines.append(f"마감: {local.strftime('%Y-%m-%d %H:%M')} ({remain})")
    else:
        lines.append("마감: 미상 — 등록하려면 /과제추가로 직접 입력하세요")
    if candidate.submit_method:
        lines.append(f"제출: {candidate.submit_method}")
    lines.append(f"신뢰도: {candidate.confidence * 100:.0f}%")
    return name, "\n".join(lines)


async def send_scan_results(task: _ScanTask, candidates: list) -> None:
    pending = [c for c in candidates if c.status == CandidateStatus.pending.value]
    mention = f"<@{task.requester_id}>" if task.guild_id else None

    if not pending:
        embed = discord.Embed(
            title="🔍 추출 결과 없음",
            description="이 내용에서는 과제·수행평가를 찾지 못했어요.",
            color=0x99AAB5,
        )
        await task.channel.send(content=mention, embed=embed)
        return

    embed = discord.Embed(
        title=f"🧠 AI 과제 추출 결과 — {len(pending)}건",
        description=f"자료: {task.title[:80]}",
        color=0x57F287,
        timestamp=datetime.now(timezone.utc),
    )
    for candidate in pending[:10]:
        name, value = _format_candidate_field(candidate)
        embed.add_field(name=name, value=value, inline=False)
    target_note = f" · 등록 대상: {task.target}" if task.target else ""
    if len(pending) > 10:
        embed.set_footer(text=f"외 {len(pending) - 10}건 더 있음 · 확인 후 아래 버튼으로 등록하세요{target_note}")
    else:
        embed.set_footer(text=f"확인 후 아래 버튼으로 등록하세요{target_note}")

    registerable = any(c.due_at is not None for c in pending)
    view = (
        ScanResultView(task.source_id, task.requester_id, task.guild_id, task.target)
        if registerable
        else None
    )
    await task.channel.send(content=mention, embed=embed, view=view)


async def register_scanned_candidates(
    source_id: str,
    requester_discord_id: str,
    guild_id: str | None,
    target: str | None = None,
    personal: bool = False,
) -> tuple[list[Assignment], int]:
    """마감일이 있는 추출 후보를 과제로 확정하고 알림을 예약한다.

    personal=True 면 개인 과제(소유자 DM에 매시간 알림)로 등록한다.
    아니면 반 과제: target(대상 반/학년)이 있으면 반별로, 없으면 등록자의 반으로 만든다.
    """
    async with SessionLocal() as session:
        candidates = await list_candidates(session, source_id)
        pending = [c for c in candidates if c.status == CandidateStatus.pending.value]
        registerable = [c for c in pending if c.due_at is not None]
        skipped = len(pending) - len(registerable)
        if not registerable:
            return [], skipped

        # 등록자(연동 사용자) 해석
        user = None
        if guild_id:
            user = await get_linked_user(session, guild_id, requester_discord_id)
        if user is None:
            row = await session.execute(
                select(DiscordUserLink)
                .where(DiscordUserLink.discord_user_id == requester_discord_id)
                .limit(1)
            )
            link = row.scalar_one_or_none()
            if link is not None:
                user = await session.get(User, link.user_id)
        creator_id = user.id if user else None

        created: list[Assignment] = []

        if personal:
            # 개인 과제: 반 없음, 소유자(요청자) DM으로 매시간 알림
            for candidate in registerable:
                assignment = Assignment(
                    title=candidate.title,
                    subject=candidate.subject,
                    due_at=candidate.due_at,
                    submit_method=candidate.submit_method,
                    source_id=candidate.source_id,
                    source_quote=candidate.source_quote,
                    class_id=None,
                    creator_id=creator_id,
                    is_personal=True,
                    owner_discord_user_id=requester_discord_id,
                )
                session.add(assignment)
                await session.flush()
                await rebuild_notifications_for_assignment(session, assignment)
                created.append(assignment)
                candidate.status = CandidateStatus.accepted.value
                await session.commit()
            return created, skipped

        # 반 과제: 대상 반/학년 → class_id 목록 (없으면 등록자 반 1개)
        if target and target.strip():
            target_pairs = await resolve_target_class_ids(session, target.strip())
            if not target_pairs:
                raise HTTPException(
                    status_code=422,
                    detail="대상 반/학년을 인식하지 못했습니다. 예: 1-1, 1학년, all",
                )
            class_ids = [class_id for _, class_id in target_pairs]
        else:
            class_ids = [user.class_id if user else None]

        for candidate in registerable:
            for class_id in class_ids:
                assignment = Assignment(
                    title=candidate.title,
                    subject=candidate.subject,
                    due_at=candidate.due_at,
                    submit_method=candidate.submit_method,
                    source_id=candidate.source_id,
                    source_quote=candidate.source_quote,
                    class_id=class_id,
                    creator_id=creator_id,
                )
                session.add(assignment)
                await session.flush()
                await rebuild_notifications_for_assignment(session, assignment)
                created.append(assignment)
            candidate.status = CandidateStatus.accepted.value
            await session.commit()
    return created, skipped


class ScanResultView(discord.ui.View):
    """추출 결과를 과제로 등록하는 버튼.

    개인 과제(소유자 DM 매시간 알림)와 반 과제(반 채널 알림)를 나눠서 등록한다.
    개인 DM에서는 반 컨텍스트가 없으므로 개인 과제 버튼만 노출한다.
    """

    def __init__(
        self,
        source_id: str,
        requester_id: int,
        guild_id: str | None,
        target: str | None = None,
    ) -> None:
        super().__init__(timeout=600)
        self._source_id = source_id
        self._requester_id = requester_id
        self._guild_id = guild_id
        self._target = target

        personal_btn = discord.ui.Button(
            label="🧑 개인 과제로 등록", style=discord.ButtonStyle.primary
        )
        personal_btn.callback = self._register_personal
        self.add_item(personal_btn)

        # 반 과제는 서버 채널에서만 (DM은 반 컨텍스트 없음)
        if guild_id:
            class_btn = discord.ui.Button(
                label="📚 반 과제로 등록", style=discord.ButtonStyle.success
            )
            class_btn.callback = self._register_class
            self.add_item(class_btn)

    async def _register_personal(self, interaction: discord.Interaction) -> None:
        await self._do_register(interaction, personal=True)

    async def _register_class(self, interaction: discord.Interaction) -> None:
        await self._do_register(interaction, personal=False)

    async def _do_register(self, interaction: discord.Interaction, *, personal: bool) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != self._requester_id and not is_teacher_or_admin(interaction):
            await interaction.followup.send(
                "등록은 요청자 본인 또는 선생님/관리자만 할 수 있어요.", ephemeral=True
            )
            return
        try:
            created, skipped = await register_scanned_candidates(
                self._source_id,
                str(interaction.user.id),
                self._guild_id,
                target=self._target,
                personal=personal,
            )
        except Exception as exc:
            await interaction.followup.send(f"등록 실패: {exc}", ephemeral=True)
            return

        if not created:
            await interaction.followup.send(
                "등록할 과제가 없어요. (이미 등록됐거나, 마감일이 있는 후보가 없습니다.)",
                ephemeral=True,
            )
            return

        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

        # 반 과제만 반 채널에 즉시 알림 (개인 과제는 DM으로 매시간)
        announced = 0
        if not personal:
            for assignment in created:
                if await announce_assignment_created(interaction.guild, assignment):
                    announced += 1

        kind = "개인 과제" if personal else "반 과제"
        lines = "\n".join(f"- `{a.id[:8]}` {a.title}" for a in created[:10])
        if len(created) > 10:
            lines += f"\n…외 {len(created) - 10}개"
        if personal:
            extra = " · 마감까지 매시간 DM으로 알림이 갑니다"
        elif announced:
            extra = f" · 반 채널 알림 {announced}건 전송"
        else:
            extra = ""
        target_note = f" (대상: {self._target})" if (not personal and self._target) else ""
        note = (
            f"\n\n⚠️ 마감일이 없어 제외된 {skipped}건은 /과제추가로 직접 등록하세요."
            if skipped
            else ""
        )
        await interaction.followup.send(
            f"✅ {kind} {len(created)}개 등록 완료{target_note}{extra}.\n{lines}{note}",
            ephemeral=True,
        )


class MacaronysDiscordBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True          # Privileged: Server Members Intent 필요
        intents.message_content = True  # Privileged: Message Content Intent 필요
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        if settings.discord_sync_commands:
            synced = await self.tree.sync()
            logger.info("Synced %s Discord app commands", len(synced))

        # Persistent view 복원 (재시작 후에도 버튼 동작 유지)
        try:
            async with SessionLocal() as session:
                projects = await get_active_projects_with_channels(session)
                for proj in projects:
                    self.add_view(RecruitmentView(proj.id))
                pending_joins = await get_all_pending_join_requests(session)
                for req in pending_joins:
                    self.add_view(ApprovalView(req.id))
                pending_regs = await get_all_pending_registrations(session)
                for reg in pending_regs:
                    self.add_view(RegistrationApprovalView(reg.id))
                active_votes = await get_active_votes(session)
                for vote in active_votes:
                    choices = await get_vote_choices(session, vote.id)
                    self.add_view(VoteView(vote.id, [(c.id, c.label) for c in choices]))
            logger.info(
                "Persistent views 복원: 팀 %d개, 참가요청 %d개, 가입신청 %d개, 투표 %d개",
                len(projects), len(pending_joins), len(pending_regs), len(active_votes),
            )
        except Exception:
            logger.exception("Persistent view 복원 실패")

        _notification_dispatch_task.start()
        _vote_close_task.start()
        _recruitment_expiry_task.start()
        ai_scan_queue.start()


bot = MacaronysDiscordBot()


@bot.event
async def on_message(message: discord.Message) -> None:
    """개인 DM으로 공지/파일을 보내면 AI 과제 추출을 실행한다."""
    if message.author.bot:
        return

    # 개인 채팅(DM)에서만 자동 추출. 서버 채널은 /과제스캔 명령을 쓴다.
    if message.guild is None and isinstance(message.channel, discord.DMChannel):
        content = message.content or ""
        attachments = list(message.attachments)
        if not content.strip() and not attachments:
            return
        try:
            raw_text, title = await build_scan_text(content, attachments)
            if not raw_text:
                await message.channel.send(
                    f"추출할 내용을 찾지 못했어요. {SCAN_SUPPORTED_HINT}"
                )
                return
            ahead = await enqueue_scan(
                raw_text=raw_text,
                title=title,
                requester_id=message.author.id,
                guild_id=None,
                channel=message.channel,
            )
            if ahead > 0:
                await message.channel.send(
                    f"🧠 추출 대기열에 추가했어요. 앞에 **{ahead}건**이 있어 순서대로 처리해요. 끝나면 알려드릴게요."
                )
            else:
                await message.channel.send("🧠 AI가 과제를 추출하는 중이에요... 잠시만요!")
        except Exception:
            logger.exception("DM 스캔 처리 실패")
            await message.channel.send("처리 중 오류가 발생했어요. 잠시 후 다시 시도해 주세요.")
        return

    await bot.process_commands(message)


_KO_ERRORS: dict[type, str] = {
    app_commands.MissingPermissions: "권한이 부족합니다. 해당 명령어에 필요한 Discord 권한이 없습니다.",
    app_commands.BotMissingPermissions: "봇의 권한이 부족합니다. 봇 역할을 확인해 주세요.",
    app_commands.CommandOnCooldown: "명령어 쿨다운 중입니다. 잠시 후 다시 시도해 주세요.",
    app_commands.CheckFailure: "명령어 사용 조건을 만족하지 못합니다.",
    app_commands.CommandNotFound: "알 수 없는 명령어입니다.",
    app_commands.MissingRole: "필요한 역할이 없습니다.",
    app_commands.NoPrivateMessage: "서버 안에서만 사용할 수 있습니다.",
}


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    cmd_name = interaction.command.name if interaction.command else "unknown"
    try:
        await log_interaction(interaction, cmd_name, None, False, detail=str(error))
    except Exception:
        logger.exception("log_interaction failed in error handler for /%s", cmd_name)

    # 한국어 에러 메시지 매핑
    ko_msg = None
    for err_type, msg in _KO_ERRORS.items():
        if isinstance(error, err_type):
            ko_msg = msg
            break
    if ko_msg is None:
        inner = getattr(error, "original", error)
        ko_msg = getattr(inner, "detail", None) or str(inner)

    embed = discord.Embed(
        title="⚠️ 오류",
        description=ko_msg,
        color=0xED4245,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"명령어: /{cmd_name}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception:
        pass




@bot.tree.command(name="가입", description="서버 가입을 신청합니다. 담당 선생님 또는 반 관리자의 승인이 필요합니다.")
@app_commands.describe(이름="실명", 생년월일="YYYY-MM-DD", 반="예: 1-1")
async def register_user(
    interaction: discord.Interaction,
    이름: str,
    생년월일: str,
    반: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)
        class_key = 반.strip()
        if class_key not in CLASS_KEYS:
            raise HTTPException(status_code=422, detail=f"'{class_key}'은(는) 올바른 반이 아닙니다. 예: 1-1")

        # 생년월일 형식 검증
        parse_birth_date(생년월일)

        async with SessionLocal() as session:
            reg = await upsert_registration(
                session,
                guild_id=str(guild.id),
                discord_user_id=str(interaction.user.id),
                display_name=interaction.user.display_name,
                name=이름.strip(),
                birth_date_str=생년월일.strip(),
                class_key=class_key,
            )

            # 선생님 채널에 승인 요청 발송
            teacher_cid = configured_teacher_channel_id() or configured_console_channel_id()
            if teacher_cid:
                ch = guild.get_channel(int(teacher_cid))
                if isinstance(ch, discord.TextChannel):
                    embed = discord.Embed(
                        title="📋 가입 승인 요청",
                        color=0xFEE75C,
                        timestamp=datetime.now(timezone.utc),
                    )
                    embed.add_field(name="이름", value=이름, inline=True)
                    embed.add_field(name="반", value=class_key, inline=True)
                    embed.add_field(name="생년월일", value=생년월일, inline=True)
                    embed.add_field(name="Discord", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=False)
                    embed.set_footer(text=f"신청자 ID: {interaction.user.id}")
                    view = RegistrationApprovalView(reg.id)
                    msg = await ch.send(embed=embed, view=view)
                    reg.approval_message_id = str(msg.id)
                    await session.commit()

        embed_result = discord.Embed(
            title="⏳ 가입 신청 완료",
            description=f"**{class_key}반** 가입 신청이 접수됐습니다.\n담당 선생님 또는 `{class_key}-관리자`의 승인을 기다려주세요.",
            color=0xFEE75C,
            timestamp=datetime.now(timezone.utc),
        )
        embed_result.add_field(name="이름", value=이름, inline=True)
        embed_result.add_field(name="반", value=class_key, inline=True)
        await interaction.followup.send(embed=embed_result, ephemeral=True)
    except Exception as exc:
        await send_error(interaction, exc)


@register_user.autocomplete("반")
async def register_user_class_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return await autocomplete_class_key(interaction, current)


@bot.tree.command(name="반채널연동", description="현재 Discord 채널을 반과 연결합니다.")
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.describe(반="예: 2-3")
async def map_class_channel(interaction: discord.Interaction, 반: str) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_console_channel(interaction)
        async with SessionLocal() as session:
            await set_discord_channel_mapping(
                session,
                guild_id=guild_id_from(interaction),
                channel_id=channel_id_from(interaction),
                class_key=반,
            )
        await interaction.followup.send(
            f"현재 채널을 `{반}` 반과 연결했습니다.",
            ephemeral=True,
        )
    except Exception as exc:
        await send_error(interaction, exc)


@map_class_channel.autocomplete("반")
async def map_class_channel_class_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return await autocomplete_class_key(interaction, current)


@bot.tree.command(name="역할이동", description="특정 역할 멤버들을 다른 역할로 옮기고 기존 역할을 제거합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.describe(
    기존역할="제거할 기존 역할",
    새역할="추가할 새 역할",
    확인="정확히 역할이동 입력",
)
async def move_role_members(
    interaction: discord.Interaction,
    기존역할: discord.Role,
    새역할: discord.Role,
    확인: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_console_channel(interaction)
        require_discord_admin(interaction)
        assert_confirmation(확인, "역할이동")
        assert_role_manageable(interaction, 기존역할)
        assert_role_manageable(interaction, 새역할)
        guild = require_guild(interaction)
        targets = await members_with_role(guild, 기존역할)

        success = 0
        failed: list[str] = []
        for member in targets:
            try:
                await member.add_roles(새역할, reason=f"Requested by {interaction.user}")
                await member.remove_roles(기존역할, reason=f"Requested by {interaction.user}")
                success += 1
            except discord.DiscordException as exc:
                failed.append(f"{member.display_name}: {exc}")
        await write_moderation_log(
            interaction,
            action="role_move",
            target=f"{기존역할.id}->{새역할.id}",
            details=f"{기존역할.name} -> {새역할.name}",
            success_count=success,
            failure_count=len(failed),
        )
        await report_bulk_result(interaction, "역할 이동", success, failed)
    except Exception as exc:
        await send_error(interaction, exc)


@bot.tree.command(name="역할일괄추가", description="여러 사용자에게 한 번에 역할을 추가합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.describe(
    역할="추가할 역할",
    사용자들="멘션 또는 사용자 ID 목록. 공백/쉼표/줄바꿈 구분",
    확인="정확히 역할추가 입력",
)
async def bulk_add_role(
    interaction: discord.Interaction,
    역할: discord.Role,
    사용자들: str,
    확인: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_console_channel(interaction)
        require_discord_admin(interaction)
        assert_confirmation(확인, "역할추가")
        assert_role_manageable(interaction, 역할)
        members, missing = await fetch_members_by_ids(require_guild(interaction), 사용자들)

        success = 0
        failed: list[str] = []
        for member in members:
            try:
                await member.add_roles(역할, reason=f"Requested by {interaction.user}")
                success += 1
            except discord.DiscordException as exc:
                failed.append(f"{member.display_name}: {exc}")
        await write_moderation_log(
            interaction,
            action="role_bulk_add",
            target=str(역할.id),
            details=역할.name,
            success_count=success,
            failure_count=len(failed) + len(missing),
        )
        await report_bulk_result(interaction, "역할 일괄 추가", success, failed, missing)
    except Exception as exc:
        await send_error(interaction, exc)


@bot.tree.command(name="역할일괄제거", description="여러 사용자에게서 한 번에 역할을 제거합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@app_commands.describe(
    역할="제거할 역할",
    사용자들="멘션 또는 사용자 ID 목록. 공백/쉼표/줄바꿈 구분",
    확인="정확히 역할제거 입력",
)
async def bulk_remove_role(
    interaction: discord.Interaction,
    역할: discord.Role,
    사용자들: str,
    확인: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_console_channel(interaction)
        require_discord_admin(interaction)
        assert_confirmation(확인, "역할제거")
        assert_role_manageable(interaction, 역할)
        members, missing = await fetch_members_by_ids(require_guild(interaction), 사용자들)

        success = 0
        failed: list[str] = []
        for member in members:
            try:
                await member.remove_roles(역할, reason=f"Requested by {interaction.user}")
                success += 1
            except discord.DiscordException as exc:
                failed.append(f"{member.display_name}: {exc}")
        await write_moderation_log(
            interaction,
            action="role_bulk_remove",
            target=str(역할.id),
            details=역할.name,
            success_count=success,
            failure_count=len(failed) + len(missing),
        )
        await report_bulk_result(interaction, "역할 일괄 제거", success, failed, missing)
    except Exception as exc:
        await send_error(interaction, exc)


@bot.tree.command(name="일괄추방", description="여러 사용자를 한 번에 추방합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(kick_members=True)
@app_commands.describe(
    사용자들="멘션 또는 사용자 ID 목록. 공백/쉼표/줄바꿈 구분",
    사유="감사 로그에 남길 사유",
    확인="정확히 추방 입력",
)
async def bulk_kick_members(
    interaction: discord.Interaction,
    사용자들: str,
    사유: str,
    확인: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_console_channel(interaction)
        require_discord_admin(interaction)
        assert_confirmation(확인, "추방")
        guild = require_guild(interaction)
        members, missing = await fetch_members_by_ids(guild, 사용자들)

        success = 0
        failed: list[str] = []
        for member in members:
            try:
                if member.guild_permissions.administrator:
                    failed.append(f"{member.display_name}: 관리자 계정은 추방하지 않았습니다.")
                    continue
                await member.kick(reason=f"{사유} / Requested by {interaction.user}")
                success += 1
            except discord.DiscordException as exc:
                failed.append(f"{member.display_name}: {exc}")
        await write_moderation_log(
            interaction,
            action="bulk_kick",
            target="members",
            details=사유,
            success_count=success,
            failure_count=len(failed) + len(missing),
        )
        await report_bulk_result(interaction, "일괄 추방", success, failed, missing)
    except Exception as exc:
        await send_error(interaction, exc)


@bot.tree.command(name="채널기록삭제", description="대상 채널의 기록을 삭제합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.checks.bot_has_permissions(manage_channels=True, manage_messages=True)
@app_commands.describe(
    대상채널="기록을 삭제할 채널. 비우면 현재 채널",
    방식="최근 메시지 삭제 또는 채널 재생성 전체 삭제",
    개수="최근 메시지 삭제 방식에서 지울 최대 개수",
    확인="최근 삭제는 삭제, 전체 삭제는 전체삭제 입력",
)
@app_commands.choices(
    방식=[
        app_commands.Choice(name="최근 메시지 삭제", value="purge"),
        app_commands.Choice(name="채널 재생성 전체 삭제", value="recreate"),
    ]
)
async def clear_channel_history(
    interaction: discord.Interaction,
    방식: app_commands.Choice[str],
    대상채널: discord.TextChannel | None = None,
    개수: app_commands.Range[int, 1, 1000] = 1000,
    확인: str = "",
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_console_channel(interaction)
        require_discord_admin(interaction)
        target = 대상채널 or interaction.channel
        if not isinstance(target, discord.TextChannel):
            raise HTTPException(status_code=422, detail="텍스트 채널만 처리할 수 있습니다.")

        if 방식.value == "purge":
            assert_confirmation(확인, "삭제")
            deleted = await target.purge(limit=개수, reason=f"Requested by {interaction.user}")
            await write_moderation_log(
                interaction,
                action="channel_purge",
                target=str(target.id),
                details=f"{target.name}, limit={개수}",
                success_count=len(deleted),
                failure_count=0,
            )
            await interaction.followup.send(
                f"`{target.name}` 채널에서 최근 메시지 {len(deleted)}개를 삭제했습니다.",
                ephemeral=True,
            )
            return

        assert_confirmation(확인, "전체삭제")
        console_id = configured_console_channel_id()
        if console_id and str(target.id) == console_id:
            raise HTTPException(
                status_code=422,
                detail="console 채널 자체는 전체 삭제할 수 없습니다. 다른 채널을 지정하세요.",
            )
        if target.id == interaction.channel_id:
            raise HTTPException(
                status_code=422,
                detail="명령을 실행한 console 채널은 전체 삭제할 수 없습니다. 다른 채널을 지정하세요.",
            )
        # 로그 채널은 재생성 불가
        log_cid = get_log_channel_id()
        if log_cid and str(target.id) == log_cid:
            raise HTTPException(
                status_code=422,
                detail="로그 채널은 전체 삭제할 수 없습니다.",
            )

        clone = await target.clone(reason=f"Full history clear requested by {interaction.user}")
        await clone.edit(position=target.position, sync_permissions=False)
        await target.delete(reason=f"Full history clear requested by {interaction.user}")
        await write_moderation_log(
            interaction,
            action="channel_recreate_clear",
            target=str(target.id),
            details=f"{target.name} -> {clone.id}",
            success_count=1,
            failure_count=0,
        )
        await interaction.followup.send(
            f"`{target.name}` 채널을 재생성해서 전체 기록을 삭제했습니다. 새 채널: {clone.mention}",
            ephemeral=True,
        )
    except Exception as exc:
        await send_error(interaction, exc)


def configured_channel_id_for_class(class_key: str) -> str | None:
    """config.json의 discord.channels에서 class_key의 채널 ID를 찾는다."""
    config = load_runtime_config()
    item = config.get("discord", {}).get("channels", {}).get(class_key, {})
    if not isinstance(item, dict):
        return None
    cid = str(item.get("channel_id") or "").strip()
    return cid if cid and cid not in PLACEHOLDER_VALUES else None


async def resolve_class_channel_id(guild: discord.Guild, class_id: str, class_key: str) -> str | None:
    """반 채널 ID 해석: config.json → DB 채널매핑 → 이름이 class_key인 채널."""
    cid = configured_channel_id_for_class(class_key)
    if cid:
        return cid
    async with SessionLocal() as session:
        row = await session.execute(
            select(DiscordChannelMapping)
            .where(DiscordChannelMapping.class_id == class_id)
            .where(DiscordChannelMapping.enabled.is_(True))
            .limit(1)
        )
        mapping = row.scalar_one_or_none()
        if mapping is not None:
            return mapping.channel_id
    ch = discord.utils.get(guild.text_channels, name=class_key)
    return str(ch.id) if ch else None


async def announce_assignment_created(
    guild: discord.Guild | None,
    assignment: Assignment,
) -> bool:
    """과제가 등록되면 해당 반 채널에 새 과제 알림 메시지를 즉시 보낸다."""
    if guild is None or not assignment.class_id:
        return False
    async with SessionLocal() as session:
        school_class = await session.get(SchoolClass, assignment.class_id)
    if school_class is None:
        return False
    class_key = school_class.class_key

    channel_id = await resolve_class_channel_id(guild, assignment.class_id, class_key)
    if not channel_id:
        return False
    try:
        channel = guild.get_channel(int(channel_id)) or await guild.fetch_channel(int(channel_id))
    except Exception:
        return False
    if not isinstance(channel, discord.TextChannel):
        return False

    local = ensure_aware(assignment.due_at).astimezone(app_tz())
    _, remain = remaining_text(assignment.due_at)
    embed = discord.Embed(
        title="📚 새 과제 등록",
        color=0x5865F2,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="제목", value=assignment.title[:250], inline=False)
    if assignment.subject:
        embed.add_field(name="과목", value=assignment.subject, inline=True)
    embed.add_field(name="마감", value=f"{local.strftime('%Y-%m-%d %H:%M')} ({remain})", inline=True)
    if assignment.submit_method:
        embed.add_field(name="제출", value=assignment.submit_method[:200], inline=True)
    if assignment.context:
        embed.add_field(name="설명", value=assignment.context[:1000], inline=False)
    embed.set_footer(text=f"{class_key} · 과제 ID: {assignment.id[:8]}")

    role = discord.utils.get(guild.roles, name=class_key)
    try:
        await channel.send(content=role.mention if role else None, embed=embed)
        return True
    except Exception:
        logger.exception("새 과제 알림 전송 실패: class=%s channel=%s", class_key, channel_id)
        return False


@bot.tree.command(name="과제추가", description="과제를 등록합니다. 대상 반/학년을 지정하거나, 비우면 현재 채널/본인 반 기준입니다.")
@app_commands.describe(
    제목="과제명",
    마감="YYYY-MM-DD HH:MM 또는 2026-06-14T23:59:00+09:00",
    과목="과목명",
    제출="제출 방식",
    설명="상세 설명",
    대상="대상 반/학년 (예: 1-1, 1학년, all). 비우면 현재 채널/본인 반",
)
@app_commands.autocomplete(대상=autocomplete_class_target)
async def add_assignment(
    interaction: discord.Interaction,
    제목: str,
    마감: str,
    과목: str | None = None,
    제출: str | None = None,
    설명: str | None = None,
    대상: str | None = None,
) -> None:
    await interaction.response.defer()
    try:
        require_console_channel(interaction)
        due_at = parse_due_at(마감)
        async with SessionLocal() as session:
            user = await require_linked_user(
                session,
                guild_id_from(interaction),
                str(interaction.user.id),
            )
            require_teacher_or_admin(interaction, user)

            # 대상 지정 시 반별로 과제를 하나씩 만든다(학년/전체면 여러 개).
            if 대상 and 대상.strip():
                targets = await resolve_target_class_ids(session, 대상.strip())
                if not targets:
                    raise HTTPException(
                        status_code=422,
                        detail="대상 반/학년을 인식하지 못했습니다. 예: 1-1, 1학년, all",
                    )
            else:
                class_id = await resolve_context_class_id(
                    session,
                    guild_id_from(interaction),
                    channel_id_from(interaction),
                    user,
                )
                targets = [(None, class_id)]

            created: list[tuple[str | None, object]] = []
            for class_key, class_id in targets:
                assignment = await create_assignment(
                    session,
                    AssignmentCreate(
                        title=제목,
                        due_at=due_at,
                        creator_id=user.id,
                        class_id=class_id,
                        subject=과목,
                        submit_method=제출,
                        context=설명,
                        status=AssignmentStatus.pending,
                    ),
                )
                await rebuild_notifications_for_assignment(session, assignment)
                created.append((class_key, assignment))
            await session.commit()

        # 등록된 대상 반 채널에 새 과제 알림 즉시 전송
        announced = 0
        for _, assignment in created:
            if await announce_assignment_created(interaction.guild, assignment):
                announced += 1

        if len(created) == 1:
            class_key, assignment = created[0]
            label = f" [{class_key}]" if class_key else ""
            sent = " · 반 채널 알림 전송됨" if announced else ""
            await interaction.followup.send(
                f"과제 등록 완료{label}: `{assignment.id[:8]}` {제목}{sent}"
            )
        else:
            keys = ", ".join(class_key for class_key, _ in created if class_key)
            await interaction.followup.send(
                f"과제 {len(created)}개 등록 완료 — 대상: {keys}\n제목: {제목}\n반 채널 알림 {announced}건 전송"
            )
    except Exception as exc:
        await send_error(interaction, exc)


@bot.tree.command(name="과제목록", description="남은 시간순 과제 목록을 보여줍니다.")
async def show_assignments(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        async with SessionLocal() as session:
            assignments = [
                item
                for item in await list_assignments(session)
                if not item.is_deleted and item.status != AssignmentStatus.done.value
            ][:10]
        body = "\n".join(format_assignment(item) for item in assignments)
        await interaction.followup.send(body or "등록된 과제가 없습니다.", ephemeral=True)
    except Exception as exc:
        await send_error(interaction, exc)


@bot.tree.command(
    name="과제스캔",
    description="공지 텍스트나 PDF/TXT에서 과제·수행평가를 AI로 추출합니다. (개인 DM에서도 사용 가능)",
)
@app_commands.describe(
    내용="공지 텍스트 (선택)",
    파일="PDF 또는 TXT 파일 (선택)",
    대상="등록 대상 반/학년 (예: 1-1, 1학년, all). 비우면 본인 반",
)
@app_commands.autocomplete(대상=autocomplete_class_target)
async def scan_assignments(
    interaction: discord.Interaction,
    내용: str | None = None,
    파일: discord.Attachment | None = None,
    대상: str | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        attachments = [파일] if 파일 is not None else []
        raw_text, title = await build_scan_text(내용, attachments)
        if not raw_text:
            await interaction.followup.send(
                f"스캔할 내용이 없어요. {SCAN_SUPPORTED_HINT}", ephemeral=True
            )
            return

        guild_id = str(interaction.guild_id) if interaction.guild_id else None
        ahead = await enqueue_scan(
            raw_text=raw_text,
            title=title,
            requester_id=interaction.user.id,
            guild_id=guild_id,
            channel=interaction.channel,
            target=(대상.strip() if 대상 and 대상.strip() else None),
        )
        if ahead > 0:
            await interaction.followup.send(
                f"🧠 추출 대기열에 추가했어요. 앞에 **{ahead}건**이 있어 순서대로 처리합니다. 완료되면 이 채널에 결과를 보낼게요.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "🧠 AI가 과제를 추출하는 중이에요... 완료되면 이 채널에 결과를 보낼게요.",
                ephemeral=True,
            )
    except Exception as exc:
        await send_error(interaction, exc)


@bot.tree.command(name="팀원모집", description="팀을 만들고 팀채팅·팀음성 채널을 생성합니다.")
@app_commands.describe(
    제목="팀 이름/모집 제목",
    설명="프로젝트 설명",
    최대인원="최대 팀원 수",
    과제id="연결할 과제 ID (선택)",
)
async def create_team_recruitment(
    interaction: discord.Interaction,
    제목: str,
    설명: str,
    최대인원: app_commands.Range[int, 2, 50],
    과제id: str | None = None,
) -> None:
    await interaction.response.defer()
    try:
        guild = require_guild(interaction)
        everyone = guild.default_role
        teacher_role = discord.utils.get(guild.roles, name=TEACHER_ROLE_NAME)

        async with SessionLocal() as session:
            user = await require_linked_user(
                session, guild_id_from(interaction), str(interaction.user.id)
            )
            class_id = await resolve_context_class_id(
                session, guild_id_from(interaction), channel_id_from(interaction), user
            )
            project = await create_team_project(
                session,
                TeamProjectCreate(
                    maker_id=user.id,
                    assignment_id=과제id,
                    class_id=class_id,
                    title=제목,
                    context=설명,
                    max_members=최대인원,
                ),
            )

        # 팀 역할 생성
        team_role = await guild.create_role(
            name=f"팀-{제목[:20]}", mentionable=True, reason="팀원모집"
        )
        if isinstance(interaction.user, discord.Member):
            await interaction.user.add_roles(team_role, reason="팀장")

        # 팀 카테고리 + 채널 생성
        team_overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            team_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if teacher_role:
            team_overwrites[teacher_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        cat_team = await get_or_create_category(guild, CAT_TEAM)
        text_ch = await guild.create_text_channel(f"{제목[:20]}-채팅", category=cat_team, overwrites=team_overwrites)
        voice_ch = await guild.create_voice_channel(f"{제목[:20]}-음성", category=cat_team, overwrites=team_overwrites)

        # 모집 마감(3일 유효)
        recruit_deadline = utc_now() + timedelta(days=3)

        # DB에 채널 정보 저장
        async with SessionLocal() as session:
            from macaronys_backend.models import TeamProject
            proj_obj = await session.get(TeamProject, project.id)
            if proj_obj:
                proj_obj.text_channel_id = str(text_ch.id)
                proj_obj.voice_channel_id = str(voice_ch.id)
                proj_obj.team_role_id = str(team_role.id)
                proj_obj.team_category_id = str(cat_team.id)
                proj_obj.recruit_deadline = recruit_deadline
                await session.commit()

        # 팀원모집 채널에 포스팅
        deadline_local = recruit_deadline.astimezone(app_tz())
        recruit_embed = discord.Embed(
            title=f"🏃 팀원 모집: {제목}",
            description=설명,
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        recruit_embed.add_field(name="팀장", value=interaction.user.mention, inline=True)
        recruit_embed.add_field(name="최대 인원", value=f"{최대인원}명", inline=True)
        recruit_embed.add_field(name="팀 채널", value=text_ch.mention, inline=True)
        recruit_embed.add_field(
            name="모집 마감",
            value=f"{deadline_local.strftime('%Y-%m-%d %H:%M')} (3일 후)",
            inline=False,
        )
        recruit_embed.set_footer(text=f"팀 ID: {project.id[:8]} · 모집 기간 3일")

        recruit_cid = configured_recruitment_channel_id()
        if recruit_cid:
            try:
                recruit_ch = guild.get_channel(int(recruit_cid))
                if isinstance(recruit_ch, discord.TextChannel):
                    view = RecruitmentView(project.id)
                    msg = await recruit_ch.send(embed=recruit_embed, view=view)
                    async with SessionLocal() as session:
                        from macaronys_backend.models import TeamProject
                        proj_obj = await session.get(TeamProject, project.id)
                        if proj_obj:
                            proj_obj.recruitment_message_id = str(msg.id)
                            await session.commit()
            except Exception as e:
                logger.warning("팀원모집 채널 포스팅 실패: %s", e)

        result_embed = discord.Embed(
            title=f"✅ 팀 생성 완료: {제목}",
            color=0x57F287,
            timestamp=datetime.now(timezone.utc),
        )
        result_embed.add_field(name="채팅 채널", value=text_ch.mention, inline=True)
        result_embed.add_field(name="음성 채널", value=voice_ch.mention, inline=True)
        result_embed.add_field(name="팀 역할", value=team_role.mention, inline=True)
        await interaction.followup.send(embed=result_embed)
        await log_interaction(interaction, "팀원모집", f"제목={제목}", True,
                              detail=f"채팅: {text_ch.name}, 음성: {voice_ch.name}")
    except Exception as exc:
        await log_interaction(interaction, "팀원모집", f"제목={제목}", False, detail=str(exc))
        await send_error(interaction, exc)


@create_team_recruitment.autocomplete("과제id")
async def create_team_recruitment_assignment_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return await autocomplete_assignment_id(interaction, current)


@bot.tree.command(name="팀목록", description="모집 중인 팀프로젝트 목록을 보여줍니다.")
async def show_team_projects(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        async with SessionLocal() as session:
            projects = await list_team_projects(session, status_filter="recruiting")
        if not projects:
            await interaction.followup.send("모집 중인 팀프로젝트가 없습니다.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🏃 모집 중인 팀 목록",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        for proj in projects[:10]:
            embed.add_field(
                name=f"{proj.title} ({proj.current_member_count}/{proj.max_members}명)",
                value=f"`{proj.id[:8]}`",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as exc:
        await send_error(interaction, exc)


@bot.tree.command(name="팀참여", description="팀원모집 채널의 '참가 신청' 버튼을 이용해 신청하세요.")
async def join_team_info(interaction: discord.Interaction) -> None:
    recruit_cid = configured_recruitment_channel_id()
    ch_mention = f"<#{recruit_cid}>" if recruit_cid else "`팀원모집` 채널"
    embed = discord.Embed(
        title="ℹ️ 팀 참가 방법",
        description=f"{ch_mention} 채널에서 팀 모집 글의 **✋ 참가 신청** 버튼을 눌러 신청하세요.\n팀장이 수락하면 자동으로 팀 채널에 입장됩니다.",
        color=0x5865F2,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="팀완료", description="팀프로젝트를 완료 처리하고 익명 평가를 열어둡니다.")
@app_commands.describe(프로젝트id="팀프로젝트 ID")
async def complete_team(interaction: discord.Interaction, 프로젝트id: str) -> None:
    await interaction.response.defer()
    try:
        async with SessionLocal() as session:
            user = await require_linked_user(
                session,
                guild_id_from(interaction),
                str(interaction.user.id),
            )
            project = await complete_team_project(session, 프로젝트id, user.id)
        await interaction.followup.send(
            f"프로젝트 완료 처리: `{project.id[:8]}` 이제 /팀평가를 받을 수 있습니다."
        )
    except Exception as exc:
        await send_error(interaction, exc)


@complete_team.autocomplete("프로젝트id")
async def complete_team_project_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return await autocomplete_team_project_id(
        interaction,
        current,
        {TeamProjectStatus.recruiting.value, TeamProjectStatus.in_progress.value},
    )


@bot.tree.command(name="팀평가", description="프로젝트 완료 후 팀원을 익명 평가합니다.")
@app_commands.describe(
    프로젝트id="팀프로젝트 ID",
    대상="평가할 Discord 멤버",
    점수="1-5",
    역할="대상이 맡은 역할",
    이유="평가 이유",
)
async def review_teammate(
    interaction: discord.Interaction,
    프로젝트id: str,
    대상: discord.Member,
    점수: app_commands.Range[int, 1, 5],
    역할: str,
    이유: str | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        async with SessionLocal() as session:
            writer = await require_linked_user(
                session,
                guild_id_from(interaction),
                str(interaction.user.id),
            )
            target = await require_linked_user(
                session,
                guild_id_from(interaction),
                str(대상.id),
            )
            review = await submit_peer_review(
                session,
                프로젝트id,
                PeerReviewCreate(
                    writer_id=writer.id,
                    target_id=target.id,
                    rating=점수,
                    reason=이유,
                    position=역할,
                ),
            )
        await interaction.followup.send(
            f"익명 평가 제출 완료: `{review.id[:8]}`",
            ephemeral=True,
        )
    except Exception as exc:
        await send_error(interaction, exc)


@review_teammate.autocomplete("프로젝트id")
async def review_teammate_project_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return await autocomplete_team_project_id(
        interaction,
        current,
        {TeamProjectStatus.completed.value},
    )


@bot.tree.command(name="팀평가보기", description="특정 팀원의 익명 평가 결과를 봅니다.")
@app_commands.describe(대상="평가를 조회할 팀원")
async def view_reviews(
    interaction: discord.Interaction,
    대상: discord.Member,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        # 본인 조회는 누구나 가능, 타인 조회는 선생님/관리자만
        if str(대상.id) != str(interaction.user.id) and not is_teacher_or_admin(interaction):
            raise HTTPException(
                status_code=403,
                detail="본인의 평가만 조회할 수 있습니다. 선생님/관리자만 타인의 평가를 볼 수 있습니다.",
            )

        async with SessionLocal() as session:
            target_user = await require_linked_user(
                session, guild_id_from(interaction), str(대상.id)
            )
            summaries = await list_user_reviews(session, user_id=target_user.id)

        if not summaries:
            await interaction.followup.send(f"{대상.mention}에 대한 평가가 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📊 {대상.display_name}의 평가",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        for item in summaries[:10]:
            stars = "⭐" * round(item.average_rating)
            embed.add_field(
                name=f"🏃 {item.project_title or '팀 프로젝트'}",
                value=f"{stars} **{item.average_rating:.1f}점** ({item.review_count}개 평가)",
                inline=False,
            )
        embed.set_footer(text="작성자 정보는 익명으로 처리됩니다.")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as exc:
        await send_error(interaction, exc)


# ─── 학급채널생성 ─────────────────────────────────────────────────────────────

@bot.tree.command(name="학급채널생성", description="학급 채널·역할·로그채널 전체를 자동으로 생성하고 config를 갱신합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def create_rooms(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_discord_admin(interaction)
        guild = require_guild(interaction)

        # 1. 선생님 역할 생성
        teacher_role = await get_or_create_role(
            guild, TEACHER_ROLE_NAME, color=discord.Color.gold(), hoist=True, mentionable=True
        )

        # 2. 학급 역할 + 학급 관리자 역할 생성 (1-1 ~ 3-4), 기존 멤버 모두 제거
        class_roles: dict[str, discord.Role] = {}
        cleared_total = 0
        for ck in CLASS_KEYS:
            role = await get_or_create_role(guild, ck, mentionable=True)
            class_roles[ck] = role
            # <class>-관리자 역할 생성
            await get_or_create_role(
                guild, class_admin_role_name(ck),
                color=discord.Color.purple(), mentionable=True,
            )
            # 역할 내 모든 유저 제거
            for member in list(role.members):
                try:
                    await member.remove_roles(role, reason="학급채널생성 초기화")
                    cleared_total += 1
                except discord.DiscordException:
                    pass

        # 3. 카테고리 생성
        everyone = guild.default_role
        teacher_only_overwrites = {
            everyone: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            teacher_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        cat_class = await get_or_create_category(guild, CAT_CLASS)
        cat_teacher = await get_or_create_category(guild, CAT_TEACHER)
        cat_admin = await get_or_create_category(guild, CAT_ADMIN)

        config_updates: dict[str, str] = {}

        # 4. 학급 채널 생성 (카테고리 아래)
        for ck in CLASS_KEYS:
            role = class_roles[ck]
            overwrites = {
                everyone: discord.PermissionOverwrite(read_messages=False, send_messages=False),
                role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                teacher_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            existing_ch = discord.utils.get(cat_class.text_channels, name=ck)
            if existing_ch is None:
                ch = await guild.create_text_channel(ck, category=cat_class, overwrites=overwrites)
            else:
                ch = existing_ch
                await ch.edit(overwrites=overwrites)
            config_updates[ck] = str(ch.id)

            # DB에 채널 매핑 등록
            try:
                async with SessionLocal() as session:
                    await set_discord_channel_mapping(
                        session,
                        guild_id=str(guild.id),
                        channel_id=str(ch.id),
                        class_key=ck,
                    )
            except Exception:
                logger.exception("Failed to save class channel mapping for %s", ck)

        # 5. 선생님 채널
        existing_teacher_ch = discord.utils.get(cat_teacher.text_channels, name=TEACHER_CHANNEL_NAME)
        if existing_teacher_ch is None:
            teacher_ch = await guild.create_text_channel(
                TEACHER_CHANNEL_NAME, category=cat_teacher, overwrites=teacher_only_overwrites
            )
        else:
            teacher_ch = existing_teacher_ch
            await teacher_ch.edit(overwrites=teacher_only_overwrites)
        config_updates["teacher"] = str(teacher_ch.id)

        # 6. 콘솔 채널
        existing_console = discord.utils.get(cat_admin.text_channels, name=CONSOLE_CHANNEL_NAME)
        if existing_console is None:
            console_ch = await guild.create_text_channel(
                CONSOLE_CHANNEL_NAME, category=cat_admin, overwrites=teacher_only_overwrites
            )
        else:
            console_ch = existing_console
            await console_ch.edit(overwrites=teacher_only_overwrites)
        config_updates["console"] = str(console_ch.id)
        update_config_console_channel(str(console_ch.id))

        # 7. 로그 채널 (재생성 불가, 선생님 읽기전용, 봇만 쓰기)
        log_overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False, send_messages=False),
            teacher_role: discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                send_messages=False,      # 선생님도 쓰기 불가
                add_reactions=False,
                manage_messages=False,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,       # 봇만 쓰기 가능
            ),
        }
        existing_log = discord.utils.get(cat_admin.text_channels, name=LOG_CHANNEL_NAME)
        if existing_log is None:
            log_ch = await guild.create_text_channel(
                LOG_CHANNEL_NAME, category=cat_admin, overwrites=log_overwrites
            )
        else:
            log_ch = existing_log
            await log_ch.edit(overwrites=log_overwrites)
        config_updates["log"] = str(log_ch.id)

        # 8. 팀원모집 채널 (누구나 읽기, 봇만 쓰기)
        recruit_overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            teacher_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        existing_recruit = discord.utils.get(cat_class.text_channels, name=RECRUITMENT_CHANNEL_NAME)
        if existing_recruit is None:
            recruit_ch = await guild.create_text_channel(
                RECRUITMENT_CHANNEL_NAME, category=cat_class, overwrites=recruit_overwrites,
                topic="팀 모집 글이 자동으로 올라오는 채널입니다. 버튼을 눌러 참가 신청하세요.",
            )
        else:
            recruit_ch = existing_recruit
            await recruit_ch.edit(overwrites=recruit_overwrites)
        config_updates["recruitment"] = str(recruit_ch.id)

        # 9. config.json 채널 ID 갱신
        update_config_channels(config_updates)

        summary = (
            f"채널 {len(CLASS_KEYS) + 3}개, 역할 {len(CLASS_KEYS) + 1}개 생성/확인 완료\n"
            f"역할에서 학생 {cleared_total}명 초기화\n"
            f"로그 채널: {log_ch.mention}\n"
            f"콘솔 채널: {console_ch.mention}"
        )
        await interaction.followup.send(summary, ephemeral=True)
        await log_interaction(
            interaction, "학급채널생성", None, True,
            detail=f"채널 {len(CLASS_KEYS)+3}개 생성, 학생 {cleared_total}명 초기화",
        )
    except Exception as exc:
        await log_interaction(interaction, "학급채널생성", None, False, detail=str(exc))
        await send_error(interaction, exc)


# ─── 공지 ─────────────────────────────────────────────────────────────────────

@bot.tree.command(name="공지", description="특정 반·학년·전체에 공지를 보냅니다. 해당 반 역할을 멘션합니다.")
@app_commands.describe(
    내용="공지 내용",
    범위="all / 1학년 / 2학년 / 3학년 / 특정 반(예: 1-1)",
    제목="공지 제목 (선택)",
)
async def announce(
    interaction: discord.Interaction,
    내용: str,
    범위: str = "all",
    제목: str | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_teacher_or_admin_role(interaction)
        guild = require_guild(interaction)

        from macaronys_backend.services.discord_management_service import load_config
        config = load_config()
        channels_cfg = config.get("discord", {}).get("channels", {})

        target_keys = resolve_class_targets(범위)

        embed = discord.Embed(
            title=제목 or "📢 공지사항",
            description=내용,
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"발신: {interaction.user.display_name}")

        sent, failed = 0, 0
        for ck in target_keys:
            cid = str(channels_cfg.get(ck, {}).get("channel_id") or "").strip()
            if not cid or cid in PLACEHOLDER_VALUES:
                failed += 1
                continue
            try:
                ch = guild.get_channel(int(cid))
                if ch is None:
                    ch = await guild.fetch_channel(int(cid))
                if isinstance(ch, discord.TextChannel):
                    # 해당 반 역할 멘션 (알림 트리거)
                    class_role = discord.utils.get(guild.roles, name=ck)
                    mention = class_role.mention if class_role else f"`{ck}`"
                    await ch.send(content=mention, embed=embed)
                    sent += 1
            except Exception as e:
                logger.warning("Failed to announce to %s: %s", ck, e)
                failed += 1

        # 공지 기록 저장 (최신순 조회용)
        try:
            async with SessionLocal() as session:
                await save_notice(
                    session,
                    guild_id=str(guild.id),
                    scope=범위,
                    title=제목,
                    content=내용,
                    author_discord_user_id=str(interaction.user.id),
                    author_name=interaction.user.display_name,
                    sent_count=sent,
                )
        except Exception:
            logger.exception("공지 기록 저장 실패")

        await interaction.followup.send(
            f"공지 완료: {sent}개 채널 전송, {failed}개 실패", ephemeral=True
        )
        await log_interaction(
            interaction, "공지",
            f"범위={범위} 제목={제목}",
            True,
            detail=f"{sent}개 채널 전송",
        )
    except Exception as exc:
        await log_interaction(interaction, "공지", f"범위={범위}", False, detail=str(exc))
        await send_error(interaction, exc)


@bot.tree.command(name="공지목록", description="최근 공지를 최신순으로 보여줍니다.")
async def list_notices(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)
        async with SessionLocal() as session:
            notices = await list_recent_notices(session, str(guild.id), limit=10)

        if not notices:
            await interaction.followup.send("등록된 공지가 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📢 최근 공지 (최신순)",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        for notice in notices:
            local = ensure_aware(notice.created_at).astimezone(app_tz())
            title = notice.title or "공지사항"
            body = notice.content.strip().replace("\n", " ")
            if len(body) > 80:
                body = body[:77] + "..."
            embed.add_field(
                name=f"[{notice.scope}] {title}"[:250],
                value=(
                    f"{body}\n"
                    f"🕒 {local.strftime('%Y-%m-%d %H:%M')} · "
                    f"{notice.author_name or '알 수 없음'} · {notice.sent_count}개 채널"
                ),
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as exc:
        await send_error(interaction, exc)


@announce.autocomplete("범위")
async def announce_class_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    options = [
        ("전체 (all)", "all"),
        ("1학년 전체", "1학년"),
        ("2학년 전체", "2학년"),
        ("3학년 전체", "3학년"),
    ] + [(ck, ck) for ck in CLASS_KEYS]
    return [
        app_commands.Choice(name=name, value=value)
        for name, value in options
        if current.strip().lower() in name.lower() or current.strip() in value
    ][:AUTOCOMPLETE_LIMIT]


# ─── 동아리 생성 ─────────────────────────────────────────────────────────────

@bot.tree.command(name="동아리생성", description="동아리를 생성합니다. 선생님만 가능합니다.")
@app_commands.describe(이름="동아리 이름", 설명="동아리 소개 (선택)")
async def create_club_cmd(
    interaction: discord.Interaction,
    이름: str,
    설명: str | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_teacher_or_admin_role(interaction)
        guild = require_guild(interaction)
        club_name = 이름.strip()

        async with SessionLocal() as session:
            existing = await get_club_by_name(session, str(guild.id), club_name)
            if existing:
                raise HTTPException(status_code=409, detail=f"이미 `{club_name}` 동아리가 존재합니다.")

        # 동아리 카테고리 생성
        cat_clubs = await get_or_create_category(guild, CAT_CLUB)
        club_cat_name = f"🎯 {club_name}"
        existing_club_cat = discord.utils.get(guild.categories, name=club_cat_name)

        teacher_role = discord.utils.get(guild.roles, name=TEACHER_ROLE_NAME)

        # 역할 생성
        admin_role = await get_or_create_role(
            guild, f"{club_name}-관리자", color=discord.Color.orange(), mentionable=True
        )
        member_role = await get_or_create_role(
            guild, f"{club_name}-멤버", color=discord.Color.blue(), mentionable=True
        )

        # 채널 권한 설정
        everyone = guild.default_role
        club_overwrites = {
            everyone: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            member_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if teacher_role:
            club_overwrites[teacher_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True
            )

        # 동아리 전용 카테고리 아래 채널 생성
        if existing_club_cat is None:
            club_cat = await guild.create_category(club_cat_name, overwrites={
                everyone: discord.PermissionOverwrite(read_messages=False),
            })
        else:
            club_cat = existing_club_cat

        text_ch = await guild.create_text_channel(
            f"{club_name}-일반", category=club_cat, overwrites=club_overwrites
        )
        notice_ch = await guild.create_text_channel(
            f"{club_name}-공지", category=club_cat, overwrites={
                **club_overwrites,
                admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                member_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            }
        )

        # 생성자에게 관리자 역할 부여
        if isinstance(interaction.user, discord.Member):
            await interaction.user.add_roles(admin_role, reason=f"동아리 {club_name} 생성")

        # DB 저장
        async with SessionLocal() as session:
            club = await create_club(
                session,
                guild_id=str(guild.id),
                name=club_name,
                description=설명,
                owner_discord_user_id=str(interaction.user.id),
                owner_display_name=interaction.user.display_name,
                category_id=str(club_cat.id),
                text_channel_id=str(text_ch.id),
                voice_channel_id=None,
                admin_role_id=str(admin_role.id),
                member_role_id=str(member_role.id),
            )

        await interaction.followup.send(
            f"동아리 `{club_name}` 생성 완료!\n"
            f"채널: {text_ch.mention}, {notice_ch.mention}\n"
            f"역할: {admin_role.mention}, {member_role.mention}",
            ephemeral=True,
        )
        await log_interaction(
            interaction, "동아리생성", f"이름={club_name}", True,
            detail=f"관리자역할: {admin_role.name}, 멤버역할: {member_role.name}",
            extra_fields=[("동아리 ID", club.id[:8], True)],
        )
    except Exception as exc:
        await log_interaction(interaction, "동아리생성", f"이름={이름}", False, detail=str(exc))
        await send_error(interaction, exc)


# ─── 동아리 삭제 ─────────────────────────────────────────────────────────────

@bot.tree.command(name="동아리삭제", description="동아리를 삭제합니다. 동아리 관리자 또는 선생님만 가능합니다.")
@app_commands.describe(이름="동아리 이름 (동아리 채널에서 실행 시 생략 가능)")
async def delete_club_cmd(
    interaction: discord.Interaction,
    이름: str | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)

        async with SessionLocal() as session:
            club_name = await resolve_club_name(interaction, 이름, session)
            club = await get_club_by_name(session, str(guild.id), club_name)
            if not club:
                raise HTTPException(status_code=404, detail=f"`{club_name}` 동아리를 찾을 수 없습니다.")

            # 권한 확인: 선생님/관리자 or 동아리 관리자
            is_ta = is_teacher_or_admin(interaction)
            cm = await get_club_member(session, club.id, str(interaction.user.id))
            is_club_admin = cm and cm.member_role == ClubMemberRole.admin.value
            if not is_ta and not is_club_admin:
                raise HTTPException(status_code=403, detail="선생님 또는 동아리 관리자만 삭제할 수 있습니다.")

            # Discord 채널/역할/카테고리 삭제
            for ch_id in [club.text_channel_id, club.voice_channel_id]:
                if ch_id:
                    try:
                        ch = guild.get_channel(int(ch_id)) or await guild.fetch_channel(int(ch_id))
                        # 공지 채널도 같은 카테고리이므로 카테고리 전체 삭제로 처리
                    except Exception:
                        pass

            if club.category_id:
                try:
                    cat = guild.get_channel(int(club.category_id))
                    if isinstance(cat, discord.CategoryChannel):
                        for ch in cat.channels:
                            await ch.delete(reason=f"동아리 {club_name} 삭제")
                        await cat.delete(reason=f"동아리 {club_name} 삭제")
                except Exception as e:
                    logger.warning("Failed to delete club category: %s", e)

            for role_id in [club.admin_role_id, club.member_role_id]:
                if role_id:
                    try:
                        role = guild.get_role(int(role_id))
                        if role:
                            await role.delete(reason=f"동아리 {club_name} 삭제")
                    except Exception as e:
                        logger.warning("Failed to delete club role: %s", e)

            await delete_club(session, club)

        await interaction.followup.send(f"동아리 `{club_name}` 삭제 완료.", ephemeral=True)
        await log_interaction(
            interaction, "동아리삭제", f"이름={club_name}", True,
            detail=f"동아리 {club_name} 및 관련 채널/역할 삭제됨",
        )
    except Exception as exc:
        await log_interaction(interaction, "동아리삭제", f"이름={이름}", False, detail=str(exc))
        await send_error(interaction, exc)


# ─── 동아리 관리자 양도 ───────────────────────────────────────────────────────

@bot.tree.command(name="동아리관리자양도", description="동아리 관리자를 다른 멤버에게 양도합니다.")
@app_commands.describe(새관리자="새 관리자로 지정할 멤버", 이름="동아리 이름 (동아리 채널에서 생략 가능)")
async def transfer_club_admin_cmd(
    interaction: discord.Interaction,
    새관리자: discord.Member,
    이름: str | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)

        async with SessionLocal() as session:
            club_name = await resolve_club_name(interaction, 이름, session)
            club = await get_club_by_name(session, str(guild.id), club_name)
            if not club:
                raise HTTPException(status_code=404, detail=f"`{club_name}` 동아리를 찾을 수 없습니다.")

            is_ta = is_teacher_or_admin(interaction)
            cm = await get_club_member(session, club.id, str(interaction.user.id))
            is_club_admin = cm and cm.member_role == ClubMemberRole.admin.value
            if not is_ta and not is_club_admin:
                raise HTTPException(status_code=403, detail="선생님 또는 동아리 관리자만 양도할 수 있습니다.")

            await transfer_club_admin(
                session, club,
                old_admin_id=str(interaction.user.id),
                new_admin_id=str(새관리자.id),
                new_admin_name=새관리자.display_name,
            )

        # Discord 역할 업데이트
        if club.admin_role_id:
            admin_role = guild.get_role(int(club.admin_role_id))
            if admin_role:
                if isinstance(interaction.user, discord.Member):
                    try:
                        await interaction.user.remove_roles(admin_role, reason="동아리 관리자 양도")
                    except Exception:
                        pass
                await 새관리자.add_roles(admin_role, reason="동아리 관리자 양도")

        await interaction.followup.send(
            f"동아리 `{club_name}` 관리자를 {새관리자.mention}에게 양도했습니다.", ephemeral=True
        )
        await log_interaction(
            interaction, "동아리관리자양도", f"이름={club_name}",  True,
            detail=f"새 관리자: {새관리자.display_name} ({새관리자.id})",
        )
    except Exception as exc:
        await log_interaction(interaction, "동아리관리자양도", f"이름={이름}", False, detail=str(exc))
        await send_error(interaction, exc)


# ─── 동아리 관리자 추가 ───────────────────────────────────────────────────────

@bot.tree.command(name="동아리관리자추가", description="동아리에 관리자를 추가합니다.")
@app_commands.describe(멤버="관리자로 추가할 멤버", 이름="동아리 이름 (동아리 채널에서 생략 가능)")
async def add_club_admin_cmd(
    interaction: discord.Interaction,
    멤버: discord.Member,
    이름: str | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)

        async with SessionLocal() as session:
            club_name = await resolve_club_name(interaction, 이름, session)
            club = await get_club_by_name(session, str(guild.id), club_name)
            if not club:
                raise HTTPException(status_code=404, detail=f"`{club_name}` 동아리를 찾을 수 없습니다.")

            is_ta = is_teacher_or_admin(interaction)
            cm = await get_club_member(session, club.id, str(interaction.user.id))
            is_club_admin = cm and cm.member_role == ClubMemberRole.admin.value
            if not is_ta and not is_club_admin:
                raise HTTPException(status_code=403, detail="선생님 또는 동아리 관리자만 추가할 수 있습니다.")

            await add_or_update_club_member(
                session, club.id, str(멤버.id), 멤버.display_name, ClubMemberRole.admin
            )

        if club.admin_role_id:
            admin_role = guild.get_role(int(club.admin_role_id))
            if admin_role:
                await 멤버.add_roles(admin_role, reason="동아리 관리자 추가")

        await interaction.followup.send(
            f"{멤버.mention}을(를) `{club_name}` 동아리 관리자로 추가했습니다.", ephemeral=True
        )
        await log_interaction(
            interaction, "동아리관리자추가", f"이름={club_name}", True,
            detail=f"추가된 관리자: {멤버.display_name} ({멤버.id})",
        )
    except Exception as exc:
        await log_interaction(interaction, "동아리관리자추가", f"이름={이름}", False, detail=str(exc))
        await send_error(interaction, exc)


# ─── 동아리 멤버 추가 ────────────────────────────────────────────────────────

@bot.tree.command(name="동아리멤버추가", description="동아리에 멤버를 추가합니다. 동아리 관리자 또는 선생님만 가능합니다.")
@app_commands.describe(멤버="추가할 멤버", 이름="동아리 이름 (동아리 채널에서 생략 가능)")
async def add_club_member_cmd(
    interaction: discord.Interaction,
    멤버: discord.Member,
    이름: str | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)

        async with SessionLocal() as session:
            club_name = await resolve_club_name(interaction, 이름, session)
            club = await get_club_by_name(session, str(guild.id), club_name)
            if not club:
                raise HTTPException(status_code=404, detail=f"`{club_name}` 동아리를 찾을 수 없습니다.")

            is_ta = is_teacher_or_admin(interaction)
            cm = await get_club_member(session, club.id, str(interaction.user.id))
            is_club_admin = cm and cm.member_role == ClubMemberRole.admin.value
            if not is_ta and not is_club_admin:
                raise HTTPException(status_code=403, detail="선생님 또는 동아리 관리자만 멤버를 추가할 수 있습니다.")

            await add_or_update_club_member(
                session, club.id, str(멤버.id), 멤버.display_name, ClubMemberRole.member
            )

        if club.member_role_id:
            member_role = guild.get_role(int(club.member_role_id))
            if member_role:
                await 멤버.add_roles(member_role, reason=f"동아리 {club_name} 멤버 추가")

        await interaction.followup.send(
            f"{멤버.mention}을(를) `{club_name}` 동아리 멤버로 추가했습니다.", ephemeral=True
        )
        await log_interaction(
            interaction, "동아리멤버추가", f"이름={club_name}", True,
            detail=f"추가된 멤버: {멤버.display_name} ({멤버.id})",
        )
    except Exception as exc:
        await log_interaction(interaction, "동아리멤버추가", f"이름={이름}", False, detail=str(exc))
        await send_error(interaction, exc)


# ─── 동아리 목록 ─────────────────────────────────────────────────────────────

@bot.tree.command(name="동아리목록", description="현재 서버의 동아리 목록을 보여줍니다.")
async def list_clubs_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)
        async with SessionLocal() as session:
            clubs = await list_clubs(session, str(guild.id))

        if not clubs:
            await interaction.followup.send("등록된 동아리가 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(title="🎯 동아리 목록", color=0x5865F2, timestamp=datetime.now(timezone.utc))
        for c in clubs[:20]:
            embed.add_field(
                name=c.name,
                value=c.description or "설명 없음",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as exc:
        await send_error(interaction, exc)


# ─── 음성방 생성 ─────────────────────────────────────────────────────────────

@bot.tree.command(name="음성방생성", description="초대한 멤버만 입장 가능한 음성방을 만듭니다.")
@app_commands.describe(
    이름="음성방 이름",
    멤버1="초대할 멤버 1",
    멤버2="초대할 멤버 2 (선택)",
    멤버3="초대할 멤버 3 (선택)",
    멤버4="초대할 멤버 4 (선택)",
    멤버5="초대할 멤버 5 (선택)",
)
async def create_voice_room_cmd(
    interaction: discord.Interaction,
    이름: str,
    멤버1: discord.Member,
    멤버2: discord.Member | None = None,
    멤버3: discord.Member | None = None,
    멤버4: discord.Member | None = None,
    멤버5: discord.Member | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)
        if not isinstance(interaction.user, discord.Member):
            raise HTTPException(status_code=400, detail="서버 멤버만 사용할 수 있습니다.")

        invited = [m for m in [멤버1, 멤버2, 멤버3, 멤버4, 멤버5] if m is not None]
        owner = interaction.user
        teacher_role = discord.utils.get(guild.roles, name=TEACHER_ROLE_NAME)
        everyone = guild.default_role

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            everyone: discord.PermissionOverwrite(connect=False, view_channel=False),
            guild.me: discord.PermissionOverwrite(connect=True, view_channel=True, manage_channels=True),
            owner: discord.PermissionOverwrite(connect=True, view_channel=True),
        }
        if teacher_role:
            overwrites[teacher_role] = discord.PermissionOverwrite(connect=True, view_channel=True)
        for m in invited:
            overwrites[m] = discord.PermissionOverwrite(connect=True, view_channel=True)

        cat_voice = await get_or_create_category(guild, CAT_VOICE)
        vc = await guild.create_voice_channel(이름.strip(), category=cat_voice, overwrites=overwrites)

        allowed_ids = [str(owner.id)] + [str(m.id) for m in invited]
        async with SessionLocal() as session:
            await create_voice_room(
                session,
                guild_id=str(guild.id),
                channel_id=str(vc.id),
                name=이름.strip(),
                owner_discord_user_id=str(owner.id),
                allowed_user_ids=allowed_ids,
            )

        mentions = ", ".join(m.mention for m in invited)
        await interaction.followup.send(
            f"음성방 {vc.mention} 생성 완료!\n초대된 멤버: {mentions}", ephemeral=True
        )
        await log_interaction(
            interaction, "음성방생성", f"이름={이름}", True,
            detail=f"초대: {', '.join(m.display_name for m in invited)}",
        )
    except Exception as exc:
        await log_interaction(interaction, "음성방생성", f"이름={이름}", False, detail=str(exc))
        await send_error(interaction, exc)


# ─── 음성방 자동 삭제 이벤트 ─────────────────────────────────────────────────

@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
) -> None:
    # 나간 채널이 있을 때만 확인
    if before.channel is None:
        return
    ch = before.channel
    if not isinstance(ch, discord.VoiceChannel):
        return

    # 아직 남은 멤버가 있으면 삭제 안 함
    if len(ch.members) > 0:
        return

    # DB에서 임시 음성방인지 확인
    try:
        async with SessionLocal() as session:
            room = await get_voice_room_by_channel(session, str(ch.id))
            if room is None:
                return
            await close_voice_room(session, room)

        await ch.delete(reason="음성방 자동 삭제: 모든 멤버 퇴장")
        logger.info("Auto-deleted empty voice room: %s (%s)", ch.name, ch.id)
    except Exception:
        logger.exception("Failed to auto-delete voice room %s", ch.id)


# ─── 학급채널삭제 ────────────────────────────────────────────────────────────

@bot.tree.command(name="학급채널삭제", description="📚 학급 카테고리의 모든 채널을 삭제합니다. 관리자만 가능합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(확인="정확히 '학급채널삭제' 입력")
async def delete_class_channels_cmd(
    interaction: discord.Interaction,
    확인: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_discord_admin(interaction)
        assert_confirmation(확인, "학급채널삭제")
        guild = require_guild(interaction)

        cat = discord.utils.get(guild.categories, name=CAT_CLASS)
        if cat is None:
            await interaction.followup.send("학급 카테고리가 없습니다.", ephemeral=True)
            return

        deleted = 0
        for ch in list(cat.channels):
            try:
                await ch.delete(reason=f"학급채널삭제 by {interaction.user}")
                deleted += 1
            except discord.DiscordException as e:
                logger.warning("Failed to delete channel %s: %s", ch.name, e)

        # config.json에서 채널 ID 초기화
        from macaronys_backend.services.discord_management_service import load_config, save_config
        config = load_config()
        channels = config.get("discord", {}).get("channels", {})
        for ck in CLASS_KEYS:
            if ck in channels:
                channels[ck]["channel_id"] = "CHANNEL_ID_HERE"
        save_config(config)

        await interaction.followup.send(
            f"학급 채널 {deleted}개 삭제 완료.", ephemeral=True
        )
        await log_interaction(
            interaction, "학급채널삭제", None, True,
            detail=f"채널 {deleted}개 삭제",
        )
    except Exception as exc:
        await log_interaction(interaction, "학급채널삭제", None, False, detail=str(exc))
        await send_error(interaction, exc)


# ─── 반배정 시스템 ────────────────────────────────────────────────────────────

@bot.tree.command(name="반배정", description="학생에게 반 역할을 배정합니다. 선생님/관리자만 가능합니다.")
@app_commands.describe(멤버="배정할 학생", 반="배정할 반 (예: 1-1)")
async def assign_class_role(
    interaction: discord.Interaction,
    멤버: discord.Member,
    반: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_teacher_or_admin_role(interaction)
        guild = require_guild(interaction)
        class_key = 반.strip()

        if class_key not in CLASS_KEYS:
            raise HTTPException(status_code=422, detail=f"'{class_key}'는 유효한 반이 아닙니다.")

        # 기존 학급 역할 모두 제거
        existing = [r for r in 멤버.roles if r.name in CLASS_KEYS]
        if existing:
            await 멤버.remove_roles(*existing, reason=f"반배정: {class_key}으로 변경")

        # 새 학급 역할 부여
        new_role = discord.utils.get(guild.roles, name=class_key)
        if new_role is None:
            raise HTTPException(
                status_code=404,
                detail=f"`{class_key}` 역할이 없습니다. /학급채널생성을 먼저 실행하세요.",
            )
        await 멤버.add_roles(new_role, reason=f"반배정: {class_key}")

        await interaction.followup.send(
            f"{멤버.mention}을(를) `{class_key}` 반으로 배정했습니다.", ephemeral=True
        )
        await log_interaction(
            interaction, "반배정", f"멤버={멤버.display_name} 반={class_key}", True,
            extra_fields=[("학생", 멤버.mention, True), ("배정 반", class_key, True)],
        )
    except Exception as exc:
        await log_interaction(interaction, "반배정", f"멤버={멤버.display_name} 반={반}", False, detail=str(exc))
        await send_error(interaction, exc)


@assign_class_role.autocomplete("반")
async def assign_class_role_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=ck, value=ck)
        for ck in CLASS_KEYS
        if current.strip() in ck
    ][:AUTOCOMPLETE_LIMIT]


@bot.tree.command(name="반배정취소", description="학생의 반 배정을 취소합니다. 선생님/관리자만 가능합니다.")
@app_commands.describe(멤버="배정을 취소할 학생")
async def unassign_class_role(
    interaction: discord.Interaction,
    멤버: discord.Member,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_teacher_or_admin_role(interaction)
        existing = [r for r in 멤버.roles if r.name in CLASS_KEYS]
        if not existing:
            await interaction.followup.send(
                f"{멤버.mention}에게 배정된 반 역할이 없습니다.", ephemeral=True
            )
            return

        removed_names = [r.name for r in existing]
        await 멤버.remove_roles(*existing, reason="반배정취소")
        await interaction.followup.send(
            f"{멤버.mention}의 반 배정(`{'`, `'.join(removed_names)}`) 취소 완료.", ephemeral=True
        )
        await log_interaction(
            interaction, "반배정취소", f"멤버={멤버.display_name}", True,
            detail=f"제거된 역할: {', '.join(removed_names)}",
        )
    except Exception as exc:
        await log_interaction(interaction, "반배정취소", f"멤버={멤버.display_name}", False, detail=str(exc))
        await send_error(interaction, exc)


@bot.tree.command(name="반명단", description="특정 반의 학생 목록을 보여줍니다.")
@app_commands.describe(반="조회할 반 (예: 1-1)")
async def class_roster(
    interaction: discord.Interaction,
    반: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)
        class_key = 반.strip()

        role = discord.utils.get(guild.roles, name=class_key)
        if role is None:
            raise HTTPException(status_code=404, detail=f"`{class_key}` 역할이 없습니다.")

        members = role.members
        if not members:
            await interaction.followup.send(f"`{class_key}` 반에 배정된 학생이 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 {class_key} 반 명단 ({len(members)}명)",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.description = "\n".join(
            f"`{i+1}.` {m.mention} (`{m.display_name}`)"
            for i, m in enumerate(sorted(members, key=lambda m: m.display_name))
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as exc:
        await send_error(interaction, exc)


@class_roster.autocomplete("반")
async def class_roster_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=ck, value=ck)
        for ck in CLASS_KEYS
        if current.strip() in ck
    ][:AUTOCOMPLETE_LIMIT]


# ─── 동아리 채널 자동 감지 헬퍼 ──────────────────────────────────────────────

async def resolve_club_name(
    interaction: discord.Interaction,
    이름: str | None,
    session,
) -> str:
    """이름이 없으면 현재 채널에서 동아리 자동 감지."""
    if 이름 and 이름.strip():
        return 이름.strip()
    if interaction.channel_id:
        club = await get_club_by_channel_id(session, str(interaction.channel_id))
        if club:
            return club.name
    raise HTTPException(
        status_code=422,
        detail="동아리 이름을 입력하거나 동아리 채널에서 명령어를 실행하세요.",
    )


# ─── 과제 삭제 ───────────────────────────────────────────────────────────────

@bot.tree.command(name="과제삭제", description="등록된 과제를 삭제합니다. 선생님/관리자만 가능합니다.")
@app_commands.describe(과제id="삭제할 과제 ID")
async def delete_assignment_cmd(
    interaction: discord.Interaction,
    과제id: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_teacher_or_admin_role(interaction)
        async with SessionLocal() as session:
            assignment = await session.get(Assignment, 과제id)
            if assignment is None or assignment.is_deleted:
                raise HTTPException(status_code=404, detail="과제를 찾을 수 없습니다.")
            assignment.is_deleted = True
            assignment.status = AssignmentStatus.done.value
            from macaronys_backend.enums import NotificationStatus
            from macaronys_backend.models import Notification
            from sqlalchemy import update as sa_update
            await session.execute(
                sa_update(Notification)
                .where(Notification.assignment_id == 과제id)
                .where(Notification.status == NotificationStatus.pending.value)
                .values(status=NotificationStatus.skipped.value)
            )
            await session.commit()

        embed = discord.Embed(
            title="🗑️ 과제 삭제 완료",
            color=0xED4245,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="과제 ID", value=f"`{과제id[:8]}`", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await log_interaction(interaction, "과제삭제", f"id={과제id[:8]}", True)
    except Exception as exc:
        await log_interaction(interaction, "과제삭제", f"id={과제id[:8]}", False, detail=str(exc))
        await send_error(interaction, exc)


@delete_assignment_cmd.autocomplete("과제id")
async def delete_assignment_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    return await autocomplete_assignment_id(interaction, current)


# ─── 반관리자 지정 ───────────────────────────────────────────────────────────

@bot.tree.command(name="반관리자지정", description="특정 반의 관리자를 지정합니다. Discord 관리자만 가능합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(반="관리 반 (예: 1-1)", 멤버="관리자로 지정할 멤버")
async def assign_class_admin(
    interaction: discord.Interaction,
    반: str,
    멤버: discord.Member,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        require_discord_admin(interaction)
        guild = require_guild(interaction)
        class_key = 반.strip()
        if class_key not in CLASS_KEYS:
            raise HTTPException(status_code=422, detail=f"'{class_key}'은(는) 올바른 반이 아닙니다.")

        role_name = class_admin_role_name(class_key)
        role = await get_or_create_role(guild, role_name, color=discord.Color.purple(), mentionable=True)
        await 멤버.add_roles(role, reason=f"반관리자 지정: {class_key}")

        embed = discord.Embed(
            title="✅ 반 관리자 지정",
            color=0x57F287,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="반", value=class_key, inline=True)
        embed.add_field(name="관리자", value=멤버.mention, inline=True)
        embed.add_field(name="역할", value=role.mention, inline=True)
        embed.description = f"`{role_name}` 역할이 부여됐습니다. 이제 해당 반 가입 신청을 승인할 수 있습니다."
        await interaction.followup.send(embed=embed, ephemeral=True)
        await log_interaction(interaction, "반관리자지정", f"반={class_key} 멤버={멤버.display_name}", True)
    except Exception as exc:
        await log_interaction(interaction, "반관리자지정", f"반={반}", False, detail=str(exc))
        await send_error(interaction, exc)


@assign_class_admin.autocomplete("반")
async def assign_class_admin_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=ck, value=ck) for ck in CLASS_KEYS if current in ck][:AUTOCOMPLETE_LIMIT]


# ─── 투표 ────────────────────────────────────────────────────────────────────

@bot.tree.command(name="투표", description="투표를 생성합니다. 선택지는 '|' 로 구분합니다.")
@app_commands.describe(
    질문="투표 질문",
    선택지="선택지 (예: 좋아요|보통이에요|별로예요), 최대 8개",
    마감="종료 시각 YYYY-MM-DD HH:MM (선택, 생략 시 수동 종료)",
    익명="익명 투표 여부 (기본: 예)",
)
async def create_vote_cmd(
    interaction: discord.Interaction,
    질문: str,
    선택지: str,
    마감: str | None = None,
    익명: bool = True,
) -> None:
    await interaction.response.defer()
    try:
        guild = require_guild(interaction)
        labels = [s.strip() for s in 선택지.split("|") if s.strip()]
        if len(labels) < 2:
            raise HTTPException(status_code=422, detail="선택지는 최소 2개, '|'로 구분해 입력하세요. 예: 좋아요|보통이에요|별로예요")
        if len(labels) > 8:
            raise HTTPException(status_code=422, detail="선택지는 최대 8개까지 가능합니다.")

        ends_at = None
        if 마감:
            ends_at = parse_due_at(마감)

        async with SessionLocal() as session:
            vote, choices = await create_vote(
                session,
                guild_id=str(guild.id),
                channel_id=str(interaction.channel_id) if interaction.channel_id else None,
                creator_discord_user_id=str(interaction.user.id),
                question=질문,
                choice_labels=labels,
                is_anonymous=익명,
                ends_at=ends_at,
            )

        embed = discord.Embed(
            title=f"🗳️ 투표: {질문}",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="익명 여부", value="익명" if 익명 else "기명", inline=True)
        if ends_at:
            embed.add_field(name="마감", value=f"<t:{int(ends_at.timestamp())}:F>", inline=True)
        embed.add_field(name="선택지", value="\n".join(f"• {lbl}" for lbl in labels), inline=False)
        embed.set_footer(text=f"투표 ID: {vote.id[:8]} | 생성: {interaction.user.display_name}")

        view = VoteView(vote.id, [(c.id, c.label) for c in choices])
        msg = await interaction.followup.send(embed=embed, view=view)

        # message_id 저장
        async with SessionLocal() as session:
            v = await get_vote_by_id(session, vote.id)
            if v:
                v.message_id = str(msg.id)
                await session.commit()

        bot.add_view(view)
        await log_interaction(interaction, "투표", f"질문={질문}", True, detail=f"선택지 {len(labels)}개")
    except Exception as exc:
        await log_interaction(interaction, "투표", f"질문={질문}", False, detail=str(exc))
        await send_error(interaction, exc)


@bot.tree.command(name="투표종료", description="진행 중인 투표를 수동으로 종료합니다.")
@app_commands.describe(투표id="종료할 투표 ID (앞 8자리 또는 전체)")
async def close_vote_cmd(
    interaction: discord.Interaction,
    투표id: str,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)
        async with SessionLocal() as session:
            # 8자리 prefix 지원
            from sqlalchemy import select as _sel
            row = await session.execute(
                _sel(Vote)
                .where(Vote.guild_id == str(guild.id))
                .where(Vote.id.startswith(투표id) if len(투표id) < 36 else Vote.id == 투표id)
                .where(Vote.is_closed.is_(False))
            )
            vote = row.scalar_one_or_none()
            if vote is None:
                raise HTTPException(status_code=404, detail="진행 중인 투표를 찾을 수 없습니다.")

            # 생성자 또는 선생님/관리자만 종료 가능
            if str(interaction.user.id) != vote.creator_discord_user_id and not is_teacher_or_admin(interaction):
                raise HTTPException(status_code=403, detail="투표 생성자 또는 선생님/관리자만 종료할 수 있습니다.")

            choices = await get_vote_choices(session, vote.id)
            results = await get_vote_results(session, vote.id)
            await close_vote(session, vote)

        embed = build_vote_results_embed(vote, results, closed=True)
        await interaction.followup.send(embed=embed)
        await log_interaction(interaction, "투표종료", f"id={투표id[:8]}", True)
    except Exception as exc:
        await log_interaction(interaction, "투표종료", f"id={투표id[:8]}", False, detail=str(exc))
        await send_error(interaction, exc)


# ─── 시간표 ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="시간표", description="오늘 시간표를 보여줍니다. 반을 지정하거나, 비우면 현재 채널 기준입니다.")
@app_commands.describe(반="조회할 반 (예: 1-1). 비우면 현재 채널 기준")
@app_commands.autocomplete(반=autocomplete_class_key)
async def timetable_cmd(
    interaction: discord.Interaction,
    반: str | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        if 반 and 반.strip():
            class_key = 반.strip()
        else:
            class_key = await resolve_timetable_class_key(interaction)
        grade, class_nm = parse_class_for_neis(class_key)
        now = kst_now()
        date_str_val = kst_date_str(now)
        rows = await fetch_timetable(
            settings.neis_api_key,
            settings.neis_atpt_code,
            settings.neis_school_code,
            grade,
            class_nm,
            date_str_val,
        )

        raw_embed = build_timetable_embeds([("오늘", rows)], grade, class_nm)[0]
        embed = discord.Embed(
            title=raw_embed["title"],
            description=raw_embed["description"],
            color=raw_embed["color"],
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"경북SW마이스터고 · {now.strftime('%Y년 %m월 %d일')} 기준")
        await interaction.followup.send(embed=embed, ephemeral=True)

        if not settings.neis_api_key:
            await interaction.followup.send(
                "⚠️ NEIS API KEY가 설정되지 않아 실제 데이터를 가져올 수 없습니다. `.env`에 `NEIS_API_KEY=...`를 추가하세요.",
                ephemeral=True,
            )
    except Exception as exc:
        await send_error(interaction, exc)


# ─── 급식 ─────────────────────────────────────────────────────────────────────

@bot.tree.command(name="급식", description="오늘의 아침·점심·저녁 급식 메뉴를 페이지로 보여줍니다.")
async def meal_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        now = kst_now()
        date_str_val = kst_date_str(now)
        date_label = now.strftime("%Y년 %m월 %d일")

        rows = await fetch_meal(
            settings.neis_api_key,
            settings.neis_atpt_code,
            settings.neis_school_code,
            date_str_val,
        )

        raw_embeds = build_meal_embeds(rows, date_label)
        meal_labels = ["조식", "중식", "석식"]

        embeds = []
        for i, re_ in enumerate(raw_embeds):
            e = discord.Embed(
                title=re_["title"],
                description=re_["description"],
                color=re_["color"],
                timestamp=datetime.now(timezone.utc),
            )
            e.set_footer(text="경북SW마이스터고 · NEIS 교육정보 개방포털")
            embeds.append(e)

        # 중식(인덱스 1)을 기본 페이지로
        default_page = 1
        view = PaginationView(embeds, meal_labels, start=default_page)
        await interaction.followup.send(embed=embeds[default_page], view=view, ephemeral=True)

        if not settings.neis_api_key:
            await interaction.followup.send(
                "⚠️ NEIS API KEY가 설정되지 않았습니다. `.env`에 `NEIS_API_KEY=...`를 추가하세요.",
                ephemeral=True,
            )
    except Exception as exc:
        await send_error(interaction, exc)


# ─── 서버 현황 ────────────────────────────────────────────────────────────────

@bot.tree.command(name="서버현황", description="서버 가입 인원, 팀, 과제, 동아리 통계를 보여줍니다.")
async def server_stats(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        guild = require_guild(interaction)

        async with SessionLocal() as session:
            from sqlalchemy import select as _sel, func as _func
            from macaronys_backend.models import (
                DiscordUserLink, TeamProject, Assignment, Club,
            )
            from macaronys_backend.enums import AssignmentStatus, TeamProjectStatus

            # 가입 인원 (DiscordUserLink 기준)
            total_members = (await session.execute(
                _sel(_func.count(DiscordUserLink.id))
                .where(DiscordUserLink.guild_id == str(guild.id))
            )).scalar() or 0

            # 반별 인원
            class_counts: dict[str, int] = {}
            for ck in CLASS_KEYS:
                role = discord.utils.get(guild.roles, name=ck)
                if role:
                    class_counts[ck] = len(role.members)

            # 진행 중 팀
            active_teams = (await session.execute(
                _sel(_func.count(TeamProject.id))
                .where(TeamProject.is_deleted.is_(False))
                .where(TeamProject.status == TeamProjectStatus.recruiting.value)
            )).scalar() or 0

            # 마감 임박 과제 (7일 내)
            from macaronys_backend.utils.time import utc_now as _utc
            from datetime import timedelta
            now = _utc()
            upcoming = (await session.execute(
                _sel(_func.count(Assignment.id))
                .where(Assignment.is_deleted.is_(False))
                .where(Assignment.status != AssignmentStatus.done.value)
                .where(Assignment.due_at > now)
                .where(Assignment.due_at <= now + timedelta(days=7))
            )).scalar() or 0

            # 동아리 수
            club_count = (await session.execute(
                _sel(_func.count(Club.id))
                .where(Club.guild_id == str(guild.id))
                .where(Club.is_deleted.is_(False))
            )).scalar() or 0

            # 대기 중 가입 신청
            pending_regs = (await session.execute(
                _sel(_func.count(Registration.id))
                .where(Registration.guild_id == str(guild.id))
                .where(Registration.status == "pending")
            )).scalar() or 0

        embed = discord.Embed(
            title=f"📊 {guild.name} 서버 현황",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="👥 전체 가입 인원", value=f"**{total_members}명**", inline=True)
        embed.add_field(name="🏃 모집 중 팀", value=f"**{active_teams}개**", inline=True)
        embed.add_field(name="🎯 동아리", value=f"**{club_count}개**", inline=True)
        embed.add_field(name="📚 마감 임박 과제 (7일 내)", value=f"**{upcoming}개**", inline=True)
        embed.add_field(name="⏳ 가입 대기", value=f"**{pending_regs}명**", inline=True)

        # 반별 인원 (inline)
        if class_counts:
            class_lines = []
            for grade in range(1, 4):
                row_parts = []
                for room in range(1, 5):
                    ck = f"{grade}-{room}"
                    cnt = class_counts.get(ck, 0)
                    row_parts.append(f"`{ck}` {cnt}명")
                class_lines.append("  ".join(row_parts))
            embed.add_field(name="🏫 반별 인원", value="\n".join(class_lines), inline=False)

        embed.set_footer(text=f"조회: {interaction.user.display_name}")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as exc:
        await send_error(interaction, exc)


# ─── 채널기록삭제 로그채널 보호 오버라이드 ───────────────────────────────────

async def run_discord_bot() -> None:
    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required in .env")

    if settings.auto_create_tables:
        await init_db()

    try:
        await bot.start(settings.discord_bot_token)
    finally:
        await close_db()
