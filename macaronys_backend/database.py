from __future__ import annotations

import ssl
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from macaronys_backend.config import settings


class Base(DeclarativeBase):
    pass


def build_async_engine_options(database_url: str) -> dict[str, object]:
    """Normalize common hosted PostgreSQL URLs for SQLAlchemy's asyncpg driver."""

    normalized_url = database_url
    if normalized_url.startswith("postgres://"):
        normalized_url = "postgresql+asyncpg://" + normalized_url[len("postgres://") :]
    elif normalized_url.startswith("postgresql://"):
        normalized_url = (
            "postgresql+asyncpg://" + normalized_url[len("postgresql://") :]
        )

    connect_args: dict[str, object] = {}
    parsed = urlsplit(normalized_url)
    if parsed.scheme == "postgresql+asyncpg":
        query_items = parse_qsl(parsed.query, keep_blank_values=True)
        filtered_query: list[tuple[str, str]] = []
        for key, value in query_items:
            if key == "sslmode":
                ssl_context = ssl_context_from_sslmode(value)
                if ssl_context is not None:
                    connect_args["ssl"] = ssl_context
                continue
            # libpq 전용 파라미터로, asyncpg 드라이버는 인식하지 못해 그대로 두면
            # connect()가 TypeError를 낸다(Neon 풀러 URL의 channel_binding 등).
            if key in {"channel_binding", "gssencmode", "target_session_attrs"}:
                continue
            filtered_query.append((key, value))
        normalized_url = urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(filtered_query),
                parsed.fragment,
            )
        )

    return {
        "url": normalized_url,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }


def ssl_context_from_sslmode(sslmode: str) -> ssl.SSLContext | None:
    if sslmode in {"", "disable"}:
        return None
    if sslmode in {"allow", "prefer", "require"}:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    if sslmode == "verify-ca":
        context = ssl.create_default_context()
        context.check_hostname = False
        return context
    return ssl.create_default_context()


engine = create_async_engine(**build_async_engine_options(settings.database_url))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from macaronys_backend import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE sources ADD COLUMN IF NOT EXISTS storage_path TEXT"))
        await conn.execute(text("ALTER TABLE sources ADD COLUMN IF NOT EXISTS mime_type VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE sources ADD COLUMN IF NOT EXISTS file_size INTEGER"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS class_id VARCHAR(36)"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS creator_id VARCHAR(36)"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS context TEXT"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS submit_link TEXT"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS reference_link TEXT"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS is_contest BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS is_exam BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS is_ended BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS end_at TIMESTAMPTZ"))
        await conn.execute(text("ALTER TABLE team_projects ADD COLUMN IF NOT EXISTS text_channel_id VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE team_projects ADD COLUMN IF NOT EXISTS voice_channel_id VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE team_projects ADD COLUMN IF NOT EXISTS team_role_id VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE team_projects ADD COLUMN IF NOT EXISTS team_category_id VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE team_projects ADD COLUMN IF NOT EXISTS recruitment_message_id VARCHAR(120)"))
        await conn.execute(text("ALTER TABLE team_projects ADD COLUMN IF NOT EXISTS recruit_deadline TIMESTAMPTZ"))
        await conn.execute(text("ALTER TABLE team_projects ADD COLUMN IF NOT EXISTS notification_scope VARCHAR(40)"))
        await conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS notification_scope VARCHAR(40)"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS team_join_requests (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                project_id TEXT NOT NULL REFERENCES team_projects(id) ON DELETE CASCADE,
                requester_discord_user_id TEXT NOT NULL,
                requester_display_name VARCHAR(120),
                reason TEXT,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                reviewer_discord_user_id TEXT,
                approval_message_id VARCHAR(120),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_join_requests_once ON team_join_requests(project_id, requester_discord_user_id)"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS clubs (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                guild_id TEXT NOT NULL,
                name VARCHAR(80) NOT NULL,
                description TEXT,
                owner_discord_user_id TEXT NOT NULL,
                category_id TEXT,
                text_channel_id TEXT,
                voice_channel_id TEXT,
                admin_role_id TEXT,
                member_role_id TEXT,
                is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_clubs_guild_name ON clubs(guild_id, name)
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS club_members (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                club_id TEXT NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
                discord_user_id TEXT NOT NULL,
                display_name VARCHAR(120),
                member_role VARCHAR(16) NOT NULL DEFAULT 'member',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_club_members_account ON club_members(club_id, discord_user_id)
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS voice_rooms (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL UNIQUE,
                name VARCHAR(120) NOT NULL,
                owner_discord_user_id TEXT NOT NULL,
                allowed_user_ids TEXT,
                is_closed BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                closed_at TIMESTAMPTZ
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS command_logs (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                guild_id TEXT,
                channel_id TEXT,
                actor_discord_user_id TEXT NOT NULL,
                actor_name VARCHAR(120),
                command VARCHAR(64) NOT NULL,
                options TEXT,
                status VARCHAR(16) NOT NULL DEFAULT 'success',
                detail TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_command_logs_created_at ON command_logs(created_at DESC)
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS notices (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                guild_id TEXT NOT NULL,
                scope VARCHAR(40) NOT NULL,
                title VARCHAR(255),
                content TEXT NOT NULL,
                author_discord_user_id TEXT NOT NULL,
                author_name VARCHAR(120),
                sent_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_notices_guild_created
            ON notices(guild_id, created_at DESC)
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS registrations (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                guild_id TEXT NOT NULL,
                discord_user_id TEXT NOT NULL,
                display_name VARCHAR(120),
                name VARCHAR(40) NOT NULL,
                birth_date_str VARCHAR(20) NOT NULL,
                class_key VARCHAR(20) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                reviewer_discord_user_id TEXT,
                approval_message_id VARCHAR(120),
                reject_reason TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_registrations_account
            ON registrations(guild_id, discord_user_id)
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS votes (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                guild_id TEXT NOT NULL,
                channel_id TEXT,
                creator_discord_user_id TEXT NOT NULL,
                question TEXT NOT NULL,
                is_anonymous BOOLEAN NOT NULL DEFAULT TRUE,
                ends_at TIMESTAMPTZ,
                is_closed BOOLEAN NOT NULL DEFAULT FALSE,
                message_id TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vote_choices (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
                label VARCHAR(80) NOT NULL,
                position INTEGER NOT NULL DEFAULT 0
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vote_responses (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
                choice_id TEXT NOT NULL REFERENCES vote_choices(id) ON DELETE CASCADE,
                discord_user_id TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_vote_responses_once
            ON vote_responses(vote_id, discord_user_id)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_registrations_guild ON registrations(guild_id, status)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_votes_guild ON votes(guild_id, is_closed)
        """))


async def close_db() -> None:
    await engine.dispose()
