"""
요약 히스토리 탭.

세션 내에 저장된 요약 결과를 시간 역순으로 표시한다.
각 항목은 마크다운 렌더링 + 복사용 코드 블록 + 개별 삭제 버튼을 제공한다.
"""
import streamlit as st
from src.utils import session_state
from src.utils.i18n import t


def render() -> None:
    """히스토리 탭 전체를 렌더링한다."""
    history: list[dict] = session_state.get("summary_history") or []

    col_title, col_clear = st.columns([4, 1])
    col_title.markdown(f"### {t('history_label')}")

    if history and col_clear.button(t("history_clear"), use_container_width=True):
        session_state.set_val("summary_history", [])
        st.rerun()

    if not history:
        st.markdown(
            f"<div style='text-align:center;color:#9ca3af;padding:3rem 0;font-size:0.95rem'>"
            f"{t('history_empty')}</div>",
            unsafe_allow_html=True,
        )
        return

    for i, item in enumerate(history):
        with st.container(border=True):
            meta_col, del_col = st.columns([6, 1])
            with meta_col:
                st.caption(
                    f"{t('history_source', src=item.get('source','?'))}  ·  "
                    f"{t('history_style', style=item.get('style','?'))}"
                )
            with del_col:
                if st.button("✕", key=f"del_hist_{i}", help="이 항목 삭제"):
                    history.pop(i)
                    session_state.set_val("summary_history", history)
                    st.rerun()

            # 마크다운 렌더링 (접힘 가능)
            with st.expander(t("tab_preview"), expanded=(i == 0)):
                st.markdown(item.get("summary", ""))

            # 복사용 코드 블록
            st.code(item.get("summary", ""), language="markdown")
