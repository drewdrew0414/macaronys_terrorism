"""
사이트 URL 탭 — 웹 페이지와 YouTube를 지원한다.

예외 처리:
- URL 형식 오류   → 정규식으로 사전 차단
- 네트워크 오류  → 구체적 안내 (타임아웃/SSL/HTTP 코드)
- YouTube 오류   → 자막 없음/비공개 구분 안내
- 빈 추출 결과   → JS 렌더링 페이지 가능성 안내
"""
from __future__ import annotations

import re
import streamlit as st
from src.core.pdf_parser import from_url, from_youtube, is_youtube
from src.utils import session_state
from src.utils.i18n import t
from src.utils.errors import show_error
from src.ui.summary_view import render_summary_button
from src.ui.upload_view import _show_stats

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def render(model: str, system_prompt: str) -> None:
    """URL 탭 전체를 렌더링한다."""
    url = st.text_input(
        "URL", placeholder=t("url_placeholder"), label_visibility="collapsed",
    )

    if not url:
        st.markdown(
            f"<div style='text-align:center;color:#9ca3af;padding:2.5rem 0;font-size:0.95rem'>"
            f"{t('url_empty')}</div>",
            unsafe_allow_html=True,
        )
        return

    url = url.strip()

    # URL 형식 사전 검증
    if not _URL_RE.match(url):
        st.warning(t("url_invalid"))
        return

    # URL 길이 제한 (비정상적으로 긴 URL 차단)
    if len(url) > 2048:
        st.warning("URL이 너무 깁니다 (최대 2,048자).")
        return

    is_yt = is_youtube(url)
    if is_yt:
        st.info(t("youtube_detected"))

    fetch_label  = t("youtube_fetch") if is_yt else t("btn_fetch")
    spinner_msg  = t("youtube_spinner") if is_yt else t("fetch_spinner")

    if st.button(fetch_label, use_container_width=True):
        session_state.set_val("url_text", "")
        _fetch_content(url, is_yt, spinner_msg)

    page_text = session_state.get("url_text")
    if page_text:
        with st.expander(t("url_expander"), expanded=False):
            st.text(page_text[:5000] + ("..." if len(page_text) > 5000 else ""))
        _show_stats(page_text)

        render_summary_button(
            text=page_text, model=model, system_prompt=system_prompt,
            source=url[:60], button_label=t("btn_sum_url"), button_key="sum_url",
        )


def _fetch_content(url: str, is_yt: bool, spinner_msg: str) -> None:
    """URL/YouTube에서 텍스트를 가져와 세션에 저장한다."""
    try:
        with st.spinner(spinner_msg):
            text = from_url(url)

        if not text or not text.strip():
            st.warning(t("fetch_empty"))
            return

        session_state.set_val("url_text", text)
        ok_msg = t("youtube_ok", n=len(text)) if is_yt else t("fetch_ok", n=len(text))
        st.success(ok_msg)

    except ValueError as exc:
        # URL 형식 오류 (from_url 내부 검증)
        st.warning(str(exc))
    except RuntimeError as exc:
        # 네트워크·YouTube·파싱 오류 (구체적 메시지 포함)
        if is_yt:
            st.error(t("youtube_fail", err=exc))
        else:
            st.error(t("fetch_error", err=exc))
    except Exception as exc:
        show_error(exc, "URL 내용 가져오기 중")
