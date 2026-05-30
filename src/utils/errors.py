"""
공통 예외 처리 유틸리티.

앱 전반에서 발생하는 예외를 일관된 방식으로 처리한다.
- Streamlit UI에 사용자 친화적 메시지 표시
- 디버그 모드에서 전체 트레이스백 노출
- 예외 종류별 맞춤 안내 메시지 제공
"""
from __future__ import annotations

import traceback
import os
from typing import Callable, TypeVar, Any

import streamlit as st

# DEBUG=true 환경변수 설정 시 전체 트레이스백을 UI에 표시
_DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

T = TypeVar("T")


# ── 예외 종류별 안내 메시지 ───────────────────────────────────────────────────

def _classify(exc: Exception) -> tuple[str, str]:
    """
    예외 객체를 받아 (제목, 해결 방법) 튜플을 반환한다.
    알려진 예외는 구체적인 안내를, 그 외엔 일반 오류 메시지를 반환한다.
    """
    msg = str(exc).lower()
    name = type(exc).__name__

    # Ollama 연결 오류
    if "connection refused" in msg or "connect" in msg and "11434" in msg:
        return (
            "Ollama 서버에 연결할 수 없습니다.",
            "터미널에서 `ollama serve` 를 실행하거나 Ollama 앱을 시작하세요.",
        )
    if "model" in msg and ("not found" in msg or "pull" in msg):
        return (
            "모델이 설치되어 있지 않습니다.",
            "사이드바의 '모델 추가 다운로드' 에서 모델을 설치하세요.",
        )

    # 파일 관련
    if name in ("FileNotFoundError", "IsADirectoryError"):
        return "파일을 찾을 수 없습니다.", "파일 경로를 확인하세요."
    if "permission" in msg:
        return "파일 접근 권한이 없습니다.", "파일의 읽기 권한을 확인하세요."
    if "pdf" in msg or "pdfplumber" in name.lower():
        return "PDF를 읽을 수 없습니다.", "파일이 손상됐거나 암호화된 PDF일 수 있습니다."

    # 네트워크 관련
    if name in ("ConnectionError", "Timeout", "ConnectTimeout", "ReadTimeout"):
        return "네트워크 오류가 발생했습니다.", "인터넷 연결을 확인하거나 잠시 후 다시 시도하세요."
    if "http" in msg or "url" in msg or "request" in name.lower():
        return "URL에 접근할 수 없습니다.", "URL이 올바른지, 페이지가 공개 상태인지 확인하세요."

    # YouTube 관련
    if "transcript" in msg or "youtube" in msg or "subtitles" in msg:
        return (
            "YouTube 자막을 가져올 수 없습니다.",
            "자막이 비활성화된 영상이거나 비공개 영상일 수 있습니다.",
        )
    if "video unavailable" in msg:
        return "YouTube 영상에 접근할 수 없습니다.", "영상이 비공개 또는 삭제됐을 수 있습니다."

    # Whisper / torch 관련
    if "whisper" in msg or "faster_whisper" in name.lower():
        return "음성 변환(Whisper)에 실패했습니다.", "오디오 파일 형식이 지원되는지 확인하세요."
    if "cuda" in msg or "mps" in msg:
        return "GPU 연산 오류가 발생했습니다.", "CPU 모드로 재시도하거나 드라이버를 업데이트하세요."
    if "out of memory" in msg:
        return (
            "메모리가 부족합니다.",
            "더 작은 모델을 선택하거나 다른 프로그램을 종료하세요.",
        )

    # 인코딩 관련
    if "codec" in msg or "decode" in msg or "encode" in msg or "unicode" in msg:
        return "텍스트 인코딩 오류가 발생했습니다.", "파일이 UTF-8 또는 일반 한국어 인코딩인지 확인하세요."

    # 기본
    return f"오류: {name}", "자세한 내용은 아래 메시지를 확인하세요."


def show_error(exc: Exception, context: str = "") -> None:
    """
    예외를 Streamlit UI에 사용자 친화적으로 표시한다.

    Args:
        exc:     발생한 예외 객체
        context: 어느 동작 중 발생했는지 설명 (예: "PDF 파싱 중")
    """
    title, hint = _classify(exc)
    prefix = f"**{context}** — " if context else ""
    st.error(f"{prefix}{title}\n\n{hint}")

    if _DEBUG:
        with st.expander("디버그 트레이스백", expanded=False):
            st.code(traceback.format_exc(), language="python")


def show_warning(msg: str) -> None:
    """경고 메시지를 표시한다."""
    st.warning(msg)


def safe_run(
    fn: Callable[..., T],
    *args: Any,
    context: str = "",
    default: T | None = None,
    **kwargs: Any,
) -> T | None:
    """
    함수를 안전하게 실행하고 예외 발생 시 UI에 오류를 표시한 뒤 default를 반환한다.

    사용 예:
        result = safe_run(from_pdf, file_bytes, context="PDF 파싱")
        if result is None:
            return  # 오류 메시지는 이미 표시됨

    Args:
        fn:      실행할 함수
        *args:   함수 인자
        context: 오류 메시지에 표시할 동작 설명
        default: 오류 시 반환할 기본값 (기본 None)
    Returns:
        성공 시 fn(*args, **kwargs) 반환값, 실패 시 default
    """
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        show_error(exc, context)
        return default
