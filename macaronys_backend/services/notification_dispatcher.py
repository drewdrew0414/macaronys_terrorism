from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.config import settings
from macaronys_backend.enums import NotificationChannel, NotificationStatus
from macaronys_backend.models import Assignment, DiscordChannelMapping, Notification
from macaronys_backend.utils.time import utc_now


@dataclass(slots=True)
class DispatchSummary:
    claimed_count: int = 0
    sent_count: int = 0
    failed_count: int = 0


async def dispatch_due_notifications(
    session: AsyncSession,
    batch_size: int | None = None,
) -> DispatchSummary:
    limit = batch_size or settings.notification_dispatch_batch_size
    notifications = await claim_due_notifications(session, limit)
    summary = DispatchSummary(claimed_count=len(notifications))

    for notification in notifications:
        try:
            if notification.channel == NotificationChannel.app.value:
                await mark_notification_sent(session, notification)
                summary.sent_count += 1
            elif notification.channel == NotificationChannel.discord.value:
                if await dispatch_discord_notification(session, notification):
                    summary.sent_count += 1
                else:
                    summary.failed_count += 1
            else:
                await mark_notification_failed(
                    session,
                    notification,
                    f"unsupported notification channel: {notification.channel}",
                )
                summary.failed_count += 1
        except Exception as exc:
            await mark_notification_failed(session, notification, str(exc))
            summary.failed_count += 1

    return summary


async def claim_due_notifications(
    session: AsyncSession,
    limit: int,
) -> list[Notification]:
    rows = await session.execute(
        select(Notification)
        .where(Notification.status == NotificationStatus.pending.value)
        .where(Notification.scheduled_at <= utc_now())
        .order_by(Notification.scheduled_at.asc(), Notification.created_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    notifications = list(rows.scalars().all())
    for notification in notifications:
        notification.status = NotificationStatus.sending.value
        notification.error_message = None
    await session.commit()
    return notifications


async def dispatch_discord_notification(
    session: AsyncSession,
    notification: Notification,
) -> bool:
    # 개인 과제는 채널이 아니라 소유자 개인 DM으로 보낸다.
    assignment = await session.get(Assignment, notification.assignment_id)
    if assignment is not None and assignment.is_personal and assignment.owner_discord_user_id:
        return await dispatch_personal_dm(session, notification, assignment)

    if not settings.discord_webhook_url:
        return await dispatch_discord_notification_with_bot_token(session, notification)

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            settings.discord_webhook_url,
            json={"content": notification.message},
        )
    if response.status_code >= 400:
        await mark_notification_failed(
            session,
            notification,
            f"Discord webhook returned HTTP {response.status_code}",
        )
        return False

    await mark_notification_sent(session, notification)
    return True


async def dispatch_personal_dm(
    session: AsyncSession,
    notification: Notification,
    assignment: Assignment,
) -> bool:
    if not settings.discord_bot_token:
        await mark_notification_failed(
            session,
            notification,
            "DISCORD_BOT_TOKEN is required for personal DM notifications",
        )
        return False

    headers = {
        "Authorization": f"Bot {settings.discord_bot_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        dm = await client.post(
            "https://discord.com/api/v10/users/@me/channels",
            headers=headers,
            json={"recipient_id": assignment.owner_discord_user_id},
        )
        if dm.status_code >= 400:
            await mark_notification_failed(
                session,
                notification,
                f"Failed to open DM channel: HTTP {dm.status_code}",
            )
            return False
        dm_channel_id = dm.json().get("id")
        response = await client.post(
            f"https://discord.com/api/v10/channels/{dm_channel_id}/messages",
            headers=headers,
            json={"content": notification.message},
        )

    if response.status_code >= 400:
        await mark_notification_failed(
            session,
            notification,
            f"Personal DM returned HTTP {response.status_code}",
        )
        return False

    await mark_notification_sent(session, notification)
    return True


async def dispatch_discord_notification_with_bot_token(
    session: AsyncSession,
    notification: Notification,
) -> bool:
    if not settings.discord_bot_token:
        await mark_notification_failed(
            session,
            notification,
            "DISCORD_BOT_TOKEN or DISCORD_WEBHOOK_URL is required for Discord notifications",
        )
        return False

    assignment = await session.get(Assignment, notification.assignment_id)
    if assignment is None or assignment.class_id is None:
        await mark_notification_failed(
            session,
            notification,
            "Assignment has no class mapping target for Discord notification",
        )
        return False

    rows = await session.execute(
        select(DiscordChannelMapping)
        .where(DiscordChannelMapping.class_id == assignment.class_id)
        .where(DiscordChannelMapping.enabled.is_(True))
    )
    mappings = list(rows.scalars().all())
    if not mappings:
        await mark_notification_failed(
            session,
            notification,
            "No enabled Discord channel mapping exists for this assignment class",
        )
        return False

    failures: list[str] = []
    headers = {
        "Authorization": f"Bot {settings.discord_bot_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        for mapping in mappings:
            response = await client.post(
                f"https://discord.com/api/v10/channels/{mapping.channel_id}/messages",
                headers=headers,
                json={"content": notification.message},
            )
            if response.status_code >= 400:
                failures.append(f"{mapping.channel_id}: HTTP {response.status_code}")

    if failures:
        await mark_notification_failed(session, notification, "; ".join(failures))
        return False

    await mark_notification_sent(session, notification)
    return True


async def mark_notification_sent(
    session: AsyncSession,
    notification: Notification,
) -> None:
    notification.status = NotificationStatus.sent.value
    notification.sent_at = utc_now()
    notification.error_message = None
    await session.commit()


async def mark_notification_failed(
    session: AsyncSession,
    notification: Notification,
    error_message: str,
) -> None:
    notification.status = NotificationStatus.failed.value
    notification.error_message = error_message
    await session.commit()
