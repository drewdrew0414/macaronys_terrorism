from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.enums import (
    AssignmentStatus,
    NotificationChannel,
    NotificationStatus,
)
from macaronys_backend.models import Assignment, Notification, NotificationRule
from macaronys_backend.schemas.notification import NotificationRuleWrite
from macaronys_backend.utils.time import ensure_aware, remaining_text, utc_now


DEFAULT_NOTIFICATION_RULES: tuple[tuple[int, NotificationChannel], ...] = (
    (3 * 24 * 60, NotificationChannel.discord),   # 3일 전
    (24 * 60, NotificationChannel.discord),         # 1일 전
    (12 * 60, NotificationChannel.discord),          # 12시간 전
    (6 * 60, NotificationChannel.discord),           # 6시간 전
    (3 * 60, NotificationChannel.discord),           # 3시간 전
    (60, NotificationChannel.discord),               # 1시간 전
    (30, NotificationChannel.discord),               # 30분 전
)


async def ensure_default_notification_rules(session: AsyncSession) -> None:
    """기본 알림 규칙 중 빠진 것을 추가한다(멱등). 기존 DB에도 신규 규칙이 반영된다."""
    rows = await session.execute(
        select(NotificationRule.offset_minutes, NotificationRule.channel)
    )
    existing = {(offset, channel) for offset, channel in rows.all()}

    for offset_minutes, channel in DEFAULT_NOTIFICATION_RULES:
        if (offset_minutes, channel.value) in existing:
            continue
        session.add(
            NotificationRule(
                offset_minutes=offset_minutes,
                channel=channel.value,
                enabled=True,
            )
        )
    await session.flush()


async def list_notification_rules(session: AsyncSession) -> list[NotificationRule]:
    await ensure_default_notification_rules(session)
    await session.commit()
    rows = await session.execute(
        select(NotificationRule).order_by(
            NotificationRule.channel.asc(),
            NotificationRule.offset_minutes.desc(),
        )
    )
    return list(rows.scalars().all())


async def replace_notification_rules(
    session: AsyncSession,
    payload: list[NotificationRuleWrite],
) -> list[NotificationRule]:
    await session.execute(delete(NotificationRule))
    for item in payload:
        session.add(
            NotificationRule(
                offset_minutes=item.offset_minutes,
                channel=item.channel.value,
                enabled=item.enabled,
                quiet_start=item.quiet_start,
                quiet_end=item.quiet_end,
            )
        )
    await session.commit()
    return await list_notification_rules(session)


async def list_notifications(
    session: AsyncSession,
    status: str | None = None,
) -> list[Notification]:
    query = select(Notification).order_by(Notification.scheduled_at.asc())
    if status:
        query = query.where(Notification.status == status)
    rows = await session.execute(query)
    return list(rows.scalars().all())


async def get_notification(session: AsyncSession, notification_id: str) -> Notification:
    notification = await session.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


async def retry_notification(
    session: AsyncSession,
    notification_id: str,
) -> Notification:
    notification = await get_notification(session, notification_id)
    notification.status = NotificationStatus.pending.value
    notification.sent_at = None
    notification.error_message = None
    await session.commit()
    await session.refresh(notification)
    return notification


async def rebuild_notifications_for_assignment(
    session: AsyncSession,
    assignment: Assignment,
) -> int:
    await session.execute(
        delete(Notification)
        .where(Notification.assignment_id == assignment.id)
        .where(Notification.status == NotificationStatus.pending.value)
    )

    if assignment.status == AssignmentStatus.done.value:
        await session.flush()
        return 0

    await ensure_default_notification_rules(session)
    rules = await session.execute(
        select(NotificationRule).where(NotificationRule.enabled.is_(True))
    )

    now = utc_now()
    created = 0
    due_at = ensure_aware(assignment.due_at)

    for rule in rules.scalars().all():
        scheduled_at = due_at - timedelta(minutes=rule.offset_minutes)
        if scheduled_at <= now:
            continue

        session.add(
            Notification(
                assignment_id=assignment.id,
                channel=rule.channel,
                scheduled_at=scheduled_at,
                status=NotificationStatus.pending.value,
                message=build_assignment_notification_message(assignment),
            )
        )
        created += 1

    await session.flush()
    return created


async def rebuild_notifications_by_assignment_id(
    session: AsyncSession,
    assignment_id: str,
) -> int:
    assignment = await session.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    count = await rebuild_notifications_for_assignment(session, assignment)
    await session.commit()
    return count


def build_assignment_notification_message(assignment: Assignment) -> str:
    _, remain = remaining_text(assignment.due_at)
    lines = [
        f"[과제 알림] {assignment.title}",
        f"마감: {ensure_aware(assignment.due_at).isoformat()}",
        f"남은 시간: {remain}",
    ]
    if assignment.subject:
        lines.append(f"과목: {assignment.subject}")
    if assignment.submit_method:
        lines.append(f"제출: {assignment.submit_method}")
    return "\n".join(lines)
