from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from macaronys_backend.models import AssignmentCandidate
from macaronys_backend.utils.time import parse_datetime_or_none


def parse_ai_candidates(raw_result: str) -> list[dict[str, Any]]:
    text = raw_result.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("AI result is not a JSON array")
        parsed = json.loads(text[start : end + 1])

    if isinstance(parsed, dict):
        parsed = parsed.get("assignments", [])
    if not isinstance(parsed, list):
        raise ValueError("AI result must be a JSON array")
    return [item for item in parsed if isinstance(item, dict)]


async def save_candidates_from_ai_result(
    session: AsyncSession,
    source_id: str,
    raw_result: str,
) -> int:
    items = parse_ai_candidates(raw_result)
    saved = 0
    for item in items:
        title = str(item.get("title") or "").strip()
        if not title:
            continue

        confidence = item.get("confidence", 0.0)
        try:
            confidence_float = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence_float = 0.0

        session.add(
            AssignmentCandidate(
                source_id=source_id,
                title=title[:255],
                subject=item.get("subject") or None,
                due_at=parse_datetime_or_none(item.get("due_at")),
                submit_method=item.get("submit_method") or None,
                source_quote=item.get("source_quote") or None,
                confidence=confidence_float,
            )
        )
        saved += 1
    return saved
