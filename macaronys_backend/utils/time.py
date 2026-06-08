from __future__ import annotations

import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from macaronys_backend.config import settings


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def app_tz() -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


def ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=app_tz())
    return dt


def remaining_text(due_at: datetime) -> tuple[int, str]:
    seconds = int((ensure_aware(due_at).astimezone(timezone.utc) - utc_now()).total_seconds())
    abs_seconds = abs(seconds)
    days, remainder = divmod(abs_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    if days > 0:
        text = f"{days}일 {hours}시간"
    elif hours > 0:
        text = f"{hours}시간 {minutes}분"
    else:
        text = f"{minutes}분"

    return seconds, f"{text} 남음" if seconds >= 0 else f"{text} 지남"


def parse_datetime_or_none(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return ensure_aware(value)
    if not isinstance(value, str):
        return None

    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return ensure_aware(parsed)
