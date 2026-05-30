"""
입력 도구 — 앱 진입점.

탭 구성:
  1. 파일 업로드 / 텍스트 입력
  2. 음성 녹음
  3. 사이트 URL (YouTube 포함)
  4. AI 채팅 (컨텍스트 기반 멀티턴 대화)
  5. 요약 히스토리

렌더링 순서:
  1. 페이지 메타 설정
  2. 세션 초기화
  3. 사이드바 렌더링 → 언어·테마 확정
  4. 테마 CSS 주입
  5. 헤더 + 메인 탭
"""
"""
입력 도구 — 앱 진입점.

탭 구성:
  소개 (접힘 가능) → 파일 업로드 → 음성 녹음 → URL/YouTube → AI 채팅 → 히스토리

렌더링 순서:
  1. 페이지 메타    → set_page_config
  2. 세션 초기화   → session_state.init()
  3. 사이드바      → 언어·테마 확정
  4. 테마 CSS 주입 → 사이드바 이후 (세션값 확정 뒤)
  5. 소개 섹션     → 앱 설명·기능·시스템 현황
  6. 메인 탭       → 5개 분석 탭
"""
import streamlit as st
from config.settings import APP_TITLE
from src.utils import session_state
from src.utils.i18n import t
from src.utils.theme import get_css
from src.ui import sidebar, upload_view, audio_view, url_view, chat_view, history_view, about_view

# 1. 페이지 메타 — 최우선 실행
st.set_page_config(
    page_title=APP_TITLE,
    layout="centered",
    initial_sidebar_state="expanded",
)

# 2. 세션 초기화
session_state.init()

# 3. 사이드바 — 언어·테마 세션값이 여기서 확정됨
active_model, system_prompt = sidebar.render()

# 4. 테마 CSS 주입 — 사이드바 렌더링 후 호출해야 세션에서 정확한 테마를 읽음
theme = session_state.get("theme") or "light"
st.markdown(f"<style>{get_css(theme)}</style>", unsafe_allow_html=True)

# 5. 소개 섹션 — 접힘 가능한 expander로 표시
st.markdown(f"## {t('app_title')}")
with st.expander(t("about_tagline"), expanded=not any([
    session_state.get("file_text"),
    session_state.get("url_text"),
    session_state.get("audio_transcript"),
])):
    # 첫 방문(콘텐츠 없음)이면 펼쳐서 표시, 이후엔 접힘
    about_view.render(theme)

st.divider()

# 6. 메인 분석 탭
tab_file, tab_audio, tab_url, tab_chat, tab_hist = st.tabs([
    t("tab_file"),
    t("tab_audio"),
    t("tab_url"),
    t("tab_chat"),
    t("history_label"),
])

with tab_file:
    upload_view.render(active_model, system_prompt)

with tab_audio:
    audio_view.render(active_model, system_prompt)

with tab_url:
    url_view.render(active_model, system_prompt)

with tab_chat:
    chat_view.render(active_model, system_prompt)

with tab_hist:
    history_view.render()
