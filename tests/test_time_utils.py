from __future__ import annotations

from datetime import datetime, timezone

from macaronys_backend.utils.time import ensure_aware, parse_datetime_or_none


def test_ensure_aware_adds_timezone_to_naive_datetime() -> None:
    value = datetime(2026, 6, 14, 23, 59)

    result = ensure_aware(value)

    assert result.tzinfo is not None


def test_parse_datetime_or_none_parses_zulu_time() -> None:
    result = parse_datetime_or_none("2026-06-14T23:59:00Z")

    assert result is not None
    assert result.astimezone(timezone.utc).isoformat() == "2026-06-14T23:59:00+00:00"


def test_parse_datetime_or_none_returns_none_for_invalid_value() -> None:
    assert parse_datetime_or_none("not a date") is None
