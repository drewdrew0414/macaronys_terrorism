from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from macaronys_backend.database import Base
from macaronys_backend.enums import (
    AssignmentStatus,
    CandidateStatus,
    ClubMemberRole,
    CommandLogStatus,
    JobStatus,
    NotificationChannel,
    NotificationStatus,
    SourceStatus,
    TeamMemberStatus,
    TeamProjectStatus,
    UserRole,
)
from macaronys_backend.utils.time import new_id, utc_now


class SchoolClass(Base):
    __tablename__ = "school_classes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    class_key: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    room: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default=UserRole.student.value
    )
    is_graduated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    class_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SourceStatus.pending.value
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AssignmentCandidate(Base):
    __tablename__ = "assignment_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(120), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submit_method: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CandidateStatus.pending.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    class_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True
    )
    creator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(120), nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    submit_method: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submit_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_contest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_exam: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_ended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AssignmentStatus.pending.value
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_scope: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class AiJob(Base):
    __tablename__ = "ai_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=JobStatus.queued.value
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    result_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class NotificationRule(Base):
    __tablename__ = "notification_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NotificationChannel.app.value
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quiet_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=NotificationStatus.pending.value
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class DiscordGuild(Base):
    __tablename__ = "discord_guilds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guild_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    default_channel_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class DiscordUserLink(Base):
    __tablename__ = "discord_user_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guild_id: Mapped[str] = mapped_column(String(120), nullable=False)
    discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        UniqueConstraint("guild_id", "discord_user_id", name="uq_discord_user_links_account"),
        UniqueConstraint("guild_id", "user_id", name="uq_discord_user_links_user"),
    )


class DiscordChannelMapping(Base):
    __tablename__ = "discord_channel_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guild_id: Mapped[str] = mapped_column(String(120), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(120), nullable=False)
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False
    )
    channel_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        UniqueConstraint("guild_id", "channel_id", name="uq_discord_channel_mappings_channel"),
    )


class DiscordModerationLog(Base):
    __tablename__ = "discord_moderation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guild_id: Mapped[str] = mapped_column(String(120), nullable=False)
    channel_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actor_discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guild_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text_channel_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    voice_channel_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    admin_role_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    member_role_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        UniqueConstraint("guild_id", "name", name="uq_clubs_guild_name"),
    )


class ClubMember(Base):
    __tablename__ = "club_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
    )
    discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    member_role: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ClubMemberRole.member.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (
        UniqueConstraint("club_id", "discord_user_id", name="uq_club_members_account"),
    )


class VoiceRoom(Base):
    __tablename__ = "voice_rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guild_id: Mapped[str] = mapped_column(String(120), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    allowed_user_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommandLog(Base):
    __tablename__ = "command_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guild_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actor_discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    command: Mapped[str] = mapped_column(String(64), nullable=False)
    options: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CommandLogStatus.success.value
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guild_id: Mapped[str] = mapped_column(String(120), nullable=False)
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class TeamProject(Base):
    __tablename__ = "team_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    maker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assignment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True
    )
    class_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    max_members: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TeamProjectStatus.recruiting.value
    )
    text_channel_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    voice_channel_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    team_role_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    team_category_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    recruitment_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    recruit_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notification_scope: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("max_members > 0", name="ck_team_projects_max_members_positive"),
    )


class TeamProjectMember(Base):
    __tablename__ = "team_project_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("team_projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TeamMemberStatus.joined.value
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_team_project_members_user"),
    )


class PeerReview(Base):
    __tablename__ = "peer_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("team_projects.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    writer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_peer_reviews_rating"),
        CheckConstraint("target_id <> writer_id", name="ck_peer_reviews_no_self_review"),
        UniqueConstraint(
            "project_id",
            "target_id",
            "writer_id",
            name="uq_peer_reviews_once_per_target",
        ),
    )


class TeamJoinRequest(Base):
    __tablename__ = "team_join_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("team_projects.id", ondelete="CASCADE"), nullable=False)
    requester_discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    requester_display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending/approved/rejected
    reviewer_discord_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approval_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    __table_args__ = (UniqueConstraint("project_id", "requester_discord_user_id", name="uq_join_requests_once"),)


class Registration(Base):
    __tablename__ = "registrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guild_id: Mapped[str] = mapped_column(String(120), nullable=False)
    discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    birth_date_str: Mapped[str] = mapped_column(String(20), nullable=False)
    class_key: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    reviewer_discord_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approval_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("guild_id", "discord_user_id", name="uq_registrations_account"),
    )


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    guild_id: Mapped[str] = mapped_column(String(120), nullable=False)
    channel_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    creator_discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class VoteChoice(Base):
    __tablename__ = "vote_choices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vote_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("votes.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class VoteResponse(Base):
    __tablename__ = "vote_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    vote_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("votes.id", ondelete="CASCADE"), nullable=False
    )
    choice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vote_choices.id", ondelete="CASCADE"), nullable=False
    )
    discord_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("vote_id", "discord_user_id", name="uq_vote_responses_once"),
    )
