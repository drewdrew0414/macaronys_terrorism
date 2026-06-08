from __future__ import annotations

from enum import Enum


class SourceType(str, Enum):
    chat = "chat"
    txt = "txt"
    pdf = "pdf"
    audio = "audio"
    discord = "discord"


class SourceStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class CandidateStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    merged = "merged"


class AssignmentStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    paused = "paused"


class UserRole(str, Enum):
    student = "student"
    teacher = "teacher"


class TeamProjectStatus(str, Enum):
    recruiting = "recruiting"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class TeamMemberStatus(str, Enum):
    joined = "joined"
    cancelled = "cancelled"
    removed = "removed"


class JobStatus(str, Enum):
    queued = "queued"
    claimed = "claimed"
    running = "running"
    completed = "completed"
    failed = "failed"


class NotificationChannel(str, Enum):
    app = "app"
    discord = "discord"


class NotificationStatus(str, Enum):
    pending = "pending"
    sending = "sending"
    sent = "sent"
    failed = "failed"
    skipped = "skipped"


class ClubMemberRole(str, Enum):
    admin = "admin"
    member = "member"


class CommandLogStatus(str, Enum):
    success = "success"
    failure = "failure"
