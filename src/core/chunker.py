"""
긴 문서 청킹(분할) 모듈.

예외 처리:
- None 또는 빈 입력 → 빈 리스트 반환 (예외 없음)
- CHUNK_SIZE가 0 이하 → 최솟값 100으로 보정
"""
from __future__ import annotations

from config.settings import CHUNK_SIZE

_MIN_CHUNK_SIZE = 100


def split(text: str) -> list[str]:
    """
    텍스트를 CHUNK_SIZE 글자 단위로 분할한다.
    입력이 None이거나 비어 있으면 빈 리스트를 반환한다.
    """
    if not text or not text.strip():
        return []

    safe_size = max(CHUNK_SIZE, _MIN_CHUNK_SIZE)

    if len(text) <= safe_size:
        return [text]

    return [text[i: i + safe_size] for i in range(0, len(text), safe_size)]


def needs_chunking(text: str) -> bool:
    """CHUNK_SIZE를 초과하면 True, 입력이 없으면 False를 반환한다."""
    if not text:
        return False
    safe_size = max(CHUNK_SIZE, _MIN_CHUNK_SIZE)
    return len(text) > safe_size
