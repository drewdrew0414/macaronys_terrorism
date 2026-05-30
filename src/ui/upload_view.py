"""
파일 업로드 탭 + 텍스트 직접 입력.

예외 처리:
- PDF 암호화·손상    → 사용자 친화적 오류 메시지
- 빈 추출 결과      → 스캔 PDF 안내
- 인코딩 오류       → 다중 인코딩 폴백
- 파일 크기 한도    → 100MB 초과 경고
"""
from __future__ import annotations

import streamlit as st
from src.core.pdf_parser import from_pdf
from src.ui.summary_view import render_summary_button
from src.utils import session_state
from src.utils.i18n import t
from src.utils.errors import show_error

_ACCEPTED    = ["pdf", "txt", "png", "jpg", "jpeg", "mp3", "wav", "m4a"]
_MAX_SIZE_MB = 100
_TXT_ENCODINGS = ["utf-8", "cp949", "euc-kr", "latin-1"]


def render(model: str, system_prompt: str) -> None:
    """파일 업로드와 텍스트 입력을 서브 탭으로 분리해 렌더링한다."""
    sub_file, sub_paste = st.tabs([t("file_upload_hint"), t("paste_label")])
    with sub_file:
        _render_file_tab(model, system_prompt)
    with sub_paste:
        _render_paste_tab(model, system_prompt)


def _render_file_tab(model: str, system_prompt: str) -> None:
    uploaded_files = st.file_uploader(
        t("file_upload_hint"), type=_ACCEPTED,
        accept_multiple_files=True, label_visibility="collapsed",
    )

    if not uploaded_files:
        st.markdown(
            f"<div style='text-align:center;color:#9ca3af;padding:2.5rem 0;font-size:0.95rem'>"
            f"{t('file_upload_empty')}</div>",
            unsafe_allow_html=True,
        )
        return

    for f in uploaded_files:
        with st.container(border=True):
            # 파일 크기 한도 검사
            if f.size > _MAX_SIZE_MB * 1024 * 1024:
                st.error(
                    f"**{f.name}** 파일이 너무 큽니다 "
                    f"({f.size / 1024 / 1024:.1f} MB). "
                    f"최대 {_MAX_SIZE_MB} MB까지 지원합니다."
                )
                continue

            col_name, col_size = st.columns([3, 1])
            col_name.markdown(f"**{f.name}**")
            col_size.caption(t("file_size", kb=f.size / 1024))

            extracted = _extract_file(f)

            if extracted:
                session_state.set_val("file_text", extracted)
                render_summary_button(
                    text=extracted, model=model, system_prompt=system_prompt,
                    source=f.name, button_key=f"sum_file_{f.name}",
                )


def _extract_file(f) -> str | None:
    """
    업로드된 파일에서 텍스트를 추출한다.
    파일 타입별로 처리하고, 실패 시 오류를 UI에 표시한 뒤 None을 반환한다.
    """
    try:
        if f.type == "application/pdf":
            extracted = from_pdf(f.read())
            with st.expander(t("file_preview_pdf")):
                st.text(extracted[:3000] + ("..." if len(extracted) > 3000 else ""))
            _show_stats(extracted)
            return extracted

        elif f.type.startswith("image/"):
            st.image(f, use_container_width=True)
            return None

        elif f.type.startswith("audio/"):
            st.audio(f)
            return None

        elif f.type == "text/plain" or f.name.endswith(".txt"):
            raw_bytes = f.read()
            extracted = _decode_text(raw_bytes, f.name)
            with st.expander(t("file_preview_txt")):
                st.text(extracted[:3000] + ("..." if len(extracted) > 3000 else ""))
            _show_stats(extracted)
            return extracted

        else:
            st.info(f"지원하지 않는 파일 형식입니다: `{f.type}`")
            return None

    except ValueError as exc:
        st.warning(str(exc))
    except RuntimeError as exc:
        st.error(str(exc))
    except Exception as exc:
        show_error(exc, f"{f.name} 처리 중")
    return None


def _decode_text(raw: bytes, filename: str) -> str:
    """
    바이트를 여러 인코딩으로 순서대로 디코딩 시도한다.
    모든 인코딩이 실패하면 errors='replace'로 강제 디코딩한다.
    """
    for enc in _TXT_ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    # 최후 수단: 알 수 없는 문자를 대체 문자(□)로 교체
    return raw.decode("utf-8", errors="replace")


def _render_paste_tab(model: str, system_prompt: str) -> None:
    """텍스트를 직접 붙여넣어 요약하는 서브 탭."""
    col_label, col_clear = st.columns([4, 1])
    col_label.caption(t("paste_label"))
    if col_clear.button(t("paste_clear"), key="paste_clear"):
        session_state.set_val("_paste_text", "")
        st.rerun()

    text = st.text_area(
        "paste", value=session_state.get("_paste_text") or "",
        height=260, placeholder=t("paste_placeholder"),
        label_visibility="collapsed",
    )
    session_state.set_val("_paste_text", text)

    if not text or not text.strip():
        st.markdown(
            f"<div style='text-align:center;color:#9ca3af;padding:1rem 0;font-size:0.9rem'>"
            f"{t('paste_empty')}</div>",
            unsafe_allow_html=True,
        )
        return

    _show_stats(text)
    session_state.set_val("file_text", text)
    render_summary_button(
        text=text, model=model, system_prompt=system_prompt,
        source="paste", button_key="sum_paste",
    )


def _show_stats(text: str) -> None:
    """단어 수·글자 수·예상 읽기 시간을 표시한다."""
    words = len(text.split())
    chars = len(text)
    mins  = max(1, round(words / 200))
    st.caption(t("doc_stats", words=words, chars=chars, mins=mins))
