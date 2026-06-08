from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.dependencies import get_session, require_worker_token
from macaronys_backend.schemas.notification import (
    DispatchNotificationsResponse,
    NotificationRead,
    NotificationRuleRead,
    NotificationRuleWrite,
)
from macaronys_backend.services.notification_dispatcher import dispatch_due_notifications
from macaronys_backend.services.notification_service import (
    list_notification_rules,
    list_notifications,
    replace_notification_rules,
    retry_notification,
)

router = APIRouter(tags=["notifications"])


@router.get("/api/notifications", response_model=list[NotificationRead])
async def list_notifications_route(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[NotificationRead]:
    notifications = await list_notifications(session, status=status)
    return [NotificationRead.model_validate(notification) for notification in notifications]


@router.get("/api/notification-rules", response_model=list[NotificationRuleRead])
async def list_notification_rules_route(
    session: AsyncSession = Depends(get_session),
) -> list[NotificationRuleRead]:
    rules = await list_notification_rules(session)
    return [NotificationRuleRead.model_validate(rule) for rule in rules]


@router.put("/api/notification-rules", response_model=list[NotificationRuleRead])
async def replace_notification_rules_route(
    payload: list[NotificationRuleWrite],
    session: AsyncSession = Depends(get_session),
) -> list[NotificationRuleRead]:
    rules = await replace_notification_rules(session, payload)
    return [NotificationRuleRead.model_validate(rule) for rule in rules]


@router.post(
    "/api/notifications/dispatch-due",
    response_model=DispatchNotificationsResponse,
    dependencies=[Depends(require_worker_token)],
)
async def dispatch_due_notifications_route(
    limit: int | None = Query(default=None, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> DispatchNotificationsResponse:
    summary = await dispatch_due_notifications(session, batch_size=limit)
    return DispatchNotificationsResponse(
        claimed_count=summary.claimed_count,
        sent_count=summary.sent_count,
        failed_count=summary.failed_count,
    )


@router.post(
    "/api/notifications/{notification_id}/retry",
    response_model=NotificationRead,
    dependencies=[Depends(require_worker_token)],
)
async def retry_notification_route(
    notification_id: str,
    session: AsyncSession = Depends(get_session),
) -> NotificationRead:
    notification = await retry_notification(session, notification_id)
    return NotificationRead.model_validate(notification)
