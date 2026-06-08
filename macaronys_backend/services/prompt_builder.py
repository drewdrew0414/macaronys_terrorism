from __future__ import annotations

from datetime import datetime

from macaronys_backend.config import settings
from macaronys_backend.utils.time import app_tz


def build_assignment_extraction_prompt(raw_text: str) -> str:
    now = datetime.now(app_tz()).isoformat()
    return f"""
너는 한국 학교 수행평가/과제 공지를 구조화하는 추출기다.

현재 기준 시각: {now}
기본 시간대: {settings.app_timezone}
사용 모델: Ollama Gemma 계열

아래 텍스트에서 수행평가, 과제, 발표, 보고서, 시험 준비, 제출물 정보를 찾아라.
반드시 JSON 배열만 출력해라. 설명 문장, 마크다운 코드블록, 주석은 출력하지 마라.

각 항목 스키마:
[
  {{
    "title": "과제명",
    "subject": "과목 또는 null",
    "due_at": "ISO-8601 마감 시각 또는 null",
    "submit_method": "제출 방식 또는 null",
    "source_quote": "근거 원문 문장",
    "confidence": 0.0
  }}
]

규칙:
- 마감일이 상대 표현이면 현재 기준 시각과 기본 시간대를 기준으로 ISO-8601로 바꿔라.
- 날짜가 있지만 시간이 없으면 23:59로 추정해라.
- 확실한 과제가 없으면 []를 출력해라.
- confidence는 0.0부터 1.0 사이 숫자로 출력해라.

텍스트:
{raw_text}
""".strip()
