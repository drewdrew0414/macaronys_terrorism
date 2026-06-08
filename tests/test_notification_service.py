from __future__ import annotations

from datetime import datetime, timezone

from macaronys_backend.models import Assignment
from macaronys_backend.enums import NotificationChannel
from macaronys_backend.services.notification_service import (
    DEFAULT_NOTIFICATION_RULES,
    build_assignment_notification_message,
)


def test_build_assignment_notification_message_contains_key_fields() -> None:
    assignment = Assignment(
        title="역사 수행평가 보고서",
        subject="역사",
        due_at=datetime(2026, 6, 14, 23, 59, tzinfo=timezone.utc),
        submit_method="클래스룸",
    )

    message = build_assignment_notification_message(assignment)

    assert "역사 수행평가 보고서" in message
    assert "역사" in message
    assert "클래스룸" in message


def test_default_notification_rules_are_discord_only() -> None:
    assert DEFAULT_NOTIFICATION_RULES
    assert {channel for _, channel in DEFAULT_NOTIFICATION_RULES} == {
        NotificationChannel.discord
    }
