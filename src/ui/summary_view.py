"""
요약 결과 공유 컴포넌트.

예외 처리:
- OllamaConnectionError    → 서버 시작 안내
- OllamaModelNotFoundError → 모델 설치 안내
- ValueError               → 입력 문제 안내
- 청킹 중 단일 청크 실패   → 해당 청크 건너뛰고 계속
- 스트리밍 중단            → 부분 결과라도 반환
"""
from __future__ import annotations

import streamlit as st
from config.settings import get_styles, get_default_style
from src.core import ollama_client, prompt_builder, response_parser
from src.core.chunker import split, needs_chunking
from src.core.ollama_client import OllamaConnectionError, OllamaModelNotFoundError
from src.utils.i18n import t
from src.utils import session_state
from src.utils.errors import show_error


def render_summary_button(
    text: str,
    model: str,
    system_prompt: str,
    source: str = "unknown",
    button_label: str | None = None,
    button_key:   str = "summarize",
) -> None:
    """
    스타일 선택기 + 요약 버튼을 렌더링한다.
    클릭 시 스트리밍 요약 실행, 결과를 히스토리에 저장한다.
    """
    lang   = session_state.get("lang") or "ko"
    styles = list(get_styles(lang).keys())
    default_style = get_default_style(lang)

    col_style, col_btn = st.columns([2, 1])
    with col_style:
        style = st.selectbox(
            t("sum_style_label"), options=styles,
            index=styles.index(default_style) if default_style in styles else 0,
            key=f"style_{button_key}", label_visibility="collapsed",
        )
    with col_btn:
        clicked = st.button(
            button_label or t("btn_summarize"),
            key=button_key, use_container_width=True, type="primary",
        )

    if not clicked:
        return

    # 입력 사전 검증
    if not text or not text.strip():
        st.warning("요약할 텍스트가 비어 있습니다.")
        return
    if not model or not model.strip():
        st.warning("사이드바에서 모델을 선택하세요.")
        return

    result = _run_summary(text, model, system_prompt, style, button_key)
    if not result:
        return

    # 결과 표시
    st.divider()
    st.markdown(t("summary_title"))

    tab_preview, tab_copy = st.tabs([t("tab_preview"), t("tab_copy")])
    with tab_preview:
        with st.container(border=True):
            st.markdown(result)
    with tab_copy:
        st.info(t("copy_hint"))
        st.code(result, language="markdown")

    st.download_button(
        label=t("btn_export_md"),
        data=result.encode("utf-8"),
        file_name=t("export_filename"),
        mime="text/markdown",
        key=f"dl_{button_key}",
    )

    session_state.add_to_history(source=source, summary=result, style=style)


def _run_summary(
    text: str, model: str, system_prompt: str, style: str, key: str
) -> str | None:
    """예외를 잡아 UI에 표시하고, 성공 시 요약 텍스트를 반환한다."""
    try:
        if needs_chunking(text):
            return _run_chunked(text, model, system_prompt, style)
        return _stream_single(text, model, system_prompt, style)

    except OllamaConnectionError as exc:
        st.error(
            f"**Ollama 서버에 연결할 수 없습니다.**\n\n"
            f"터미널에서 `ollama serve`를 실행하거나 Ollama 앱을 시작하세요.\n\n"
            f"`{exc}`"
        )
    except OllamaModelNotFoundError as exc:
        st.error(
            f"**모델이 설치되어 있지 않습니다.**\n\n"
            f"사이드바 → '모델 추가 다운로드'에서 `{model}`을 설치하세요.\n\n"
            f"`{exc}`"
        )
    except ValueError as exc:
        st.warning(f"입력 오류: {exc}")
    except Exception as exc:
        show_error(exc, "요약 중")
    return None


def _stream_single(text: str, model: str, system_prompt: str, style: str) -> str:
    """단일 청크 스트리밍 요약 — st.write_stream 사용."""
    user_msg  = prompt_builder.build_summary_user_message(text, style)
    messages  = prompt_builder.build_messages(system_prompt, user_msg)
    generator = ollama_client.chat(messages, model, stream=True)

    with st.container(border=True):
        raw = st.write_stream(generator)

    if not raw or not str(raw).strip():
        raise RuntimeError("모델이 빈 응답을 반환했습니다. 다시 시도하세요.")
    return response_parser.parse(str(raw))


def _run_chunked(text: str, model: str, system_prompt: str, style: str) -> str:
    """
    MAP-REDUCE 청킹 요약.

    각 청크 실패 시 해당 청크를 건너뛰고 계속 진행한다.
    성공한 청크가 하나도 없으면 RuntimeError를 발생시킨다.
    """
    chunks = split(text)
    st.info(t("chunk_notice", n=len(chunks)))

    chunk_summaries: list[str] = []
    progress = st.progress(0, text=t("chunk_progress", i=0, n=len(chunks)))

    for i, chunk in enumerate(chunks, 1):
        progress.progress(i / len(chunks), text=t("chunk_progress", i=i, n=len(chunks)))
        try:
            user_msg = prompt_builder.build_summary_user_message(chunk, style)
            messages = prompt_builder.build_messages(system_prompt, user_msg)
            with st.spinner(t("chunk_progress", i=i, n=len(chunks))):
                raw = ollama_client.chat(messages, model)
            chunk_summaries.append(response_parser.parse(str(raw)))
        except (OllamaConnectionError, OllamaModelNotFoundError):
            raise  # 연결/모델 오류는 즉시 전파
        except Exception as exc:
            st.warning(f"청크 {i} 처리 실패 (건너뜀): {exc}")
            continue

    progress.empty()

    if not chunk_summaries:
        raise RuntimeError("모든 청크 처리에 실패했습니다.")

    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    # REDUCE 단계
    st.info(t("chunk_merge"))
    try:
        merge_msg = prompt_builder.build_chunk_merge_message(chunk_summaries)
        messages  = prompt_builder.build_messages(system_prompt, merge_msg)
        generator = ollama_client.chat(messages, model, stream=True)
        with st.container(border=True):
            raw = st.write_stream(generator)
        return response_parser.parse(str(raw))
    except Exception as exc:
        # REDUCE 실패 시 청크 요약을 이어붙여 반환 (부분 결과)
        st.warning(f"최종 병합 실패, 청크 요약을 그대로 반환합니다: {exc}")
        return "\n\n---\n\n".join(chunk_summaries)
