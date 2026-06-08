from __future__ import annotations

import logging
from datetime import datetime
from html import unescape
import re
from typing import Any
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger("macaronys.neis")

NEIS_BASE = "https://open.neis.go.kr/hub"
NEIS_TIMEOUT = httpx.Timeout(10.0, connect=3.0)
NEIS_NO_DATA_CODE = "INFO-200"
KST = ZoneInfo("Asia/Seoul")
BR_TAG_RE = re.compile(r"(?i)<br\s*/?>")
ALLERGY_RE = re.compile(r"\s*[\(\[]\s*\d{1,2}(?:\.\d{1,2})*\.?\s*[\)\]]")

# 급식 종류 코드
MEAL_TYPES = {
    "1": "🌅 조식",
    "2": "☀️ 중식",
    "3": "🌙 석식",
}


class NeisApiError(RuntimeError):
    """Raised when NEIS returns a real API error instead of an empty result."""


def kst_now() -> datetime:
    return datetime.now(KST)


def kst_date_str(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def sem_from_date(dt: datetime) -> str:
    """학기 계산: 3~8월 → 1학기, 9~2월 → 2학기"""
    return "1" if 3 <= dt.month <= 8 else "2"


def parse_class_for_neis(class_key: str) -> tuple[str, str]:
    """'1-1' → grade='1', class_nm='1'"""
    parts = class_key.split("-", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "1", "1"


def clean_dish_name(raw: str) -> str:
    """HTML 개행 태그를 줄바꿈으로, 알레르기 번호 제거."""
    result = unescape(raw or "")
    result = BR_TAG_RE.sub("\n", result)
    result = ALLERGY_RE.sub("", result)
    lines = (" ".join(line.split()) for line in result.splitlines())
    return "\n".join(line for line in lines if line).strip()


def _extract_rows(data: dict[str, Any], endpoint: str) -> list[dict]:
    result = data.get("RESULT")
    if isinstance(result, dict):
        code = str(result.get("CODE", ""))
        message = str(result.get("MESSAGE", ""))
        if code == NEIS_NO_DATA_CODE:
            return []
        raise NeisApiError(f"NEIS API 오류 ({code}): {message or '응답을 확인할 수 없습니다.'}")

    container = data.get(endpoint, [])
    if not isinstance(container, list) or len(container) < 2:
        return []

    body = container[1]
    if not isinstance(body, dict):
        return []

    rows = body.get("row", [])
    return rows if isinstance(rows, list) else []


async def _fetch_rows(endpoint: str, params: dict[str, str], date_yyyymmdd: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=NEIS_TIMEOUT) as client:
            resp = await client.get(f"{NEIS_BASE}/{endpoint}", params=params)
            resp.raise_for_status()
        return _extract_rows(resp.json(), endpoint)
    except NeisApiError:
        raise
    except httpx.HTTPError as exc:
        logger.warning("NEIS 요청 실패 (%s, %s): %s", endpoint, date_yyyymmdd, exc)
        raise NeisApiError("NEIS API 요청에 실패했습니다. 네트워크 상태를 확인하거나 잠시 후 다시 시도하세요.") from exc
    except ValueError as exc:
        logger.warning("NEIS JSON 파싱 실패 (%s, %s): %s", endpoint, date_yyyymmdd, exc)
        raise NeisApiError("NEIS API 응답을 해석하지 못했습니다. 잠시 후 다시 시도하세요.") from exc


def _period_order(row: dict) -> int:
    try:
        return int(row.get("PERIO", 0))
    except (TypeError, ValueError):
        return 0


def _base_params(api_key: str, atpt_code: str, school_code: str) -> dict[str, str]:
    return {
        "KEY": api_key.strip(),
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": atpt_code.strip(),
        "SD_SCHUL_CODE": school_code.strip(),
    }


async def fetch_timetable(
    api_key: str,
    atpt_code: str,
    school_code: str,
    grade: str,
    class_nm: str,
    date_yyyymmdd: str,
) -> list[dict]:
    """특정 날짜의 시간표 조회. 데이터 없으면 빈 리스트 반환."""
    if not api_key:
        return []
    dt = datetime.strptime(date_yyyymmdd, "%Y%m%d")
    params = {
        **_base_params(api_key, atpt_code, school_code),
        "AY": dt.strftime("%Y"),
        "SEM": sem_from_date(dt),
        "ALL_TI_YMD": date_yyyymmdd,
        "GRADE": grade,
        "CLASS_NM": class_nm,
    }
    rows = await _fetch_rows("hisTimetable", params, date_yyyymmdd)
    return sorted(rows, key=_period_order)


async def fetch_meal(
    api_key: str,
    atpt_code: str,
    school_code: str,
    date_yyyymmdd: str,
) -> list[dict]:
    """특정 날짜의 급식 정보 조회. 데이터 없으면 빈 리스트 반환."""
    if not api_key:
        return []
    params = {
        **_base_params(api_key, atpt_code, school_code),
        "MLSV_YMD": date_yyyymmdd,
    }
    return await _fetch_rows("mealServiceDietInfo", params, date_yyyymmdd)


def build_timetable_embeds(
    rows_by_date: list[tuple[str, list[dict]]],
    grade: str,
    class_nm: str,
) -> list["discord_embed"]:
    """[(날짜라벨, rows), ...] 로부터 embed 리스트 생성 (discord import 없이 dict 반환)."""
    result = []
    label_map = {"어제": "📅", "오늘": "📌", "내일": "🔜"}
    for label, rows in rows_by_date:
        icon = label_map.get(label, "📅")
        if rows:
            lines = [
                f"`{r.get('PERIO', '?')}교시` {r.get('ITRT_CNTNT', '정보 없음')}"
                for r in rows
            ]
            desc = "\n".join(lines)
        else:
            desc = "📭 시간표 정보가 없습니다.\n(주말, 공휴일 또는 방학일 수 있습니다.)"
        result.append({
            "title": f"{icon} {label} 시간표 — {grade}학년 {class_nm}반",
            "description": desc,
            "color": 0x5865F2 if label == "오늘" else 0x99AAB5,
        })
    return result


def build_meal_embeds(rows: list[dict], date_label: str) -> list[dict]:
    """급식 rows → embed dict 리스트 (조식/중식/석식)."""
    meals_by_type: dict[str, dict] = {}
    for row in rows:
        code = row.get("MMEAL_SC_CODE", "")
        meals_by_type[code] = row

    result = []
    for code, label in MEAL_TYPES.items():
        row = meals_by_type.get(code)
        if row:
            dishes = clean_dish_name(row.get("DDISH_NM", "정보 없음"))
            cal = row.get("CAL_INFO", "")
            desc = f"```\n{dishes}\n```"
            if cal:
                desc += f"\n🔥 **{cal}**"
        else:
            desc = "📭 급식 정보가 없습니다."
        result.append({
            "title": f"{label} — {date_label}",
            "description": desc,
            "color": 0xFEE75C if code == "2" else (0xFF9500 if code == "1" else 0x5865F2),
        })
    return result
