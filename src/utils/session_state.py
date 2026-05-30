"""
Streamlit 세션 상태 관리 모듈.

Streamlit은 매 인터랙션마다 전체 스크립트를 재실행하므로
st.session_state를 통해 상태를 보존한다.
이 모듈은 기본값을 한 곳에서 관리해 일관성을 보장한다.
"""
import streamlit as st
from config.settings import DEFAULT_LANG

_DEFAULTS: dict = {
    # UI 설정
    "lang":              DEFAULT_LANG,  # "ko" | "en"
    "theme":             "light",       # "light" | "dark"

    # 콘텐츠 (탭 간 공유)
    "system_prompt":     "",            # 사이드바 시스템 프롬프트
    "audio_transcript":  "",            # Whisper 변환 결과
    "url_text":          "",            # URL 추출 본문
    "file_text":         "",            # 마지막 업로드 파일 본문

    # 채팅
    "chat_messages":     [],            # [{"role": "user"/"assistant", "content": "..."}]

    # 요약 히스토리
    "summary_history":   [],            # [{"source": str, "summary": str, "style": str}]

    # 내부 플래그
    "_pending_download": None,          # 이용약관 동의 후 대기 중인 모델명
}


def init() -> None:
    """최초 실행 시 모든 기본값을 설정한다. 기존 값은 덮어쓰지 않는다."""
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            # 리스트·딕트는 참조 공유 방지를 위해 복사
            st.session_state[key] = default.copy() if isinstance(default, (list, dict)) else default


def get(key: str):
    """세션 값을 읽는다. 키가 없으면 기본값을 반환한다."""
    return st.session_state.get(key, _DEFAULTS.get(key))


def set_val(key: str, value) -> None:
    """세션 값을 설정한다."""
    st.session_state[key] = value


def add_to_history(source: str, summary: str, style: str) -> None:
    """요약 결과를 히스토리에 추가한다 (최대 20개 보관)."""
    history: list = st.session_state.get("summary_history", [])
    history.insert(0, {"source": source, "summary": summary, "style": style})
    st.session_state["summary_history"] = history[:20]  # 최대 20개 유지
