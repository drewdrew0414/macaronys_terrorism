"""
Ollama 응답 후처리 모듈.

예외 처리:
- None 입력     → 빈 문자열 반환
- 정리 후 빈 결과 → 원본 반환 (clean이 내용을 날리는 경우 방지)
"""
from __future__ import annotations

from src.utils.text_cleaner import clean


def parse(raw: str | None) -> str:
    """
    Ollama 응답을 정리한다.

    Args:
        raw: Ollama 원시 응답 (None일 수 있음)
    Returns:
        정리된 텍스트. 입력이 None이거나 정리 후 비어 있으면 원본 반환.
    """
    if raw is None:
        return ""
    text = str(raw)
    try:
        cleaned = clean(text)
        # clean 후 비어 있으면 원본 반환 (예외적 상황 방지)
        return cleaned if cleaned.strip() else text
    except Exception:
        return text
