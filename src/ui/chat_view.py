"""
AI 채팅 탭.

예외 처리:
- 컨텍스트 없음           → 명확한 안내 후 입력 차단
- Ollama 연결/모델 오류   → 구체적 해결 방법 안내
- 스트리밍 중 오류        → 부분 응답이라도 히스토리에 저장
- 히스토리 손상           → 빈 리스트로 초기화
"""
from __future__ import annotations

import streamlit as st
from src.core import ollama_client, prompt_builder
from src.core.ollama_client import OllamaConnectionError, OllamaModelNotFoundError
from src.utils import session_state
from src.utils.i18n import t
from src.utils.errors import show_error

_CTX_SOURCES = {
    "chat_ctx_paste":  None,
    "chat_ctx_file":   "file_text",
    "chat_ctx_url":    "url_text",
    "chat_ctx_audio":  "audio_transcript",
}

# 채팅 히스토리 최대 보관 턴 수 (무한 증가 방지)
_MAX_HISTORY_TURNS = 20


def render(model: str, system_prompt: str) -> None:
    """채팅 탭 전체를 렌더링한다."""
    context = _render_context_section()
    st.divider()

    if context is None:
        return

    if not model or not model.strip():
        st.warning("사이드바에서 모델을 선택한 뒤 채팅을 시작하세요.")
        return

    _render_chat_section(model, system_prompt, context)


def _render_context_section() -> str | None:
    """컨텍스트 선택 UI. 유효한 컨텍스트 문자열 또는 None 반환."""
    source_keys   = list(_CTX_SOURCES.keys())
    source_labels = [t(k) for k in source_keys]

    col_select, col_clear = st.columns([4, 1])
    with col_select:
        chosen_label = st.selectbox(
            t("chat_ctx_select"), options=source_labels,
            label_visibility="collapsed",
        )
    with col_clear:
        if st.button(t("chat_clear"), use_container_width=True):
            session_state.set_val("chat_messages", [])
            st.rerun()

    chosen_key  = source_keys[source_labels.index(chosen_label)]
    session_key = _CTX_SOURCES[chosen_key]

    if session_key is None:
        # 직접 입력 모드
        context = st.text_area(
            "context", height=180,
            placeholder=t("chat_ctx_hint"),
            label_visibility="collapsed",
        )
        if not context or not context.strip():
            st.markdown(
                f"<div style='text-align:center;color:#9ca3af;padding:1rem 0'>"
                f"{t('chat_ctx_none')}</div>",
                unsafe_allow_html=True,
            )
            return None
        return context
    else:
        ctx = session_state.get(session_key)
        if not ctx or not str(ctx).strip():
            st.warning(t("chat_ctx_none"))
            return None
        with st.expander(t("chat_ctx_select"), expanded=False):
            st.text(str(ctx)[:2000] + ("..." if len(str(ctx)) > 2000 else ""))
        return str(ctx)


def _render_chat_section(model: str, system_prompt: str, context: str) -> None:
    """채팅 히스토리 표시 + 사용자 입력 처리."""
    # 히스토리 로드 — 손상 시 빈 리스트로 초기화
    try:
        messages: list[dict] = session_state.get("chat_messages") or []
        if not isinstance(messages, list):
            messages = []
    except Exception:
        messages = []
        session_state.set_val("chat_messages", [])

    # 히스토리 길이 제한
    if len(messages) > _MAX_HISTORY_TURNS * 2:
        messages = messages[-(  _MAX_HISTORY_TURNS * 2):]
        session_state.set_val("chat_messages", messages)
        st.caption(f"대화가 길어져 최근 {_MAX_HISTORY_TURNS}턴만 유지합니다.")

    # 이전 대화 표시
    for msg in messages:
        if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
            continue
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 입력창
    user_input = st.chat_input(t("chat_input_ph"))
    if not user_input:
        return

    user_input = user_input.strip()
    if not user_input:
        return

    # 사용자 메시지 추가
    messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # AI 응답
    response = _get_response(model, system_prompt, context, messages, user_input)
    if response:
        messages.append({"role": "assistant", "content": response})

    session_state.set_val("chat_messages", messages)


def _get_response(
    model: str,
    system_prompt: str,
    context: str,
    messages: list[dict],
    user_input: str,
) -> str | None:
    """
    Ollama에 메시지를 전송하고 스트리밍 응답을 반환한다.
    각 예외 유형에 맞는 안내 메시지를 표시한다.
    """
    try:
        chat_system  = prompt_builder.build_chat_system(system_prompt, context)
        api_messages = prompt_builder.build_messages(
            chat_system, user_input,
            history=messages[:-1],  # 방금 추가한 user 메시지 제외
        )
        generator = ollama_client.chat(api_messages, model, stream=True)

        with st.chat_message("assistant"):
            response = st.write_stream(generator)

        if not response or not str(response).strip():
            st.warning("모델이 빈 응답을 반환했습니다. 다시 질문해 보세요.")
            return None

        return str(response)

    except OllamaConnectionError:
        with st.chat_message("assistant"):
            st.error(
                "Ollama 서버에 연결할 수 없습니다.\n\n"
                "터미널에서 `ollama serve`를 실행하거나 Ollama 앱을 시작하세요."
            )
    except OllamaModelNotFoundError:
        with st.chat_message("assistant"):
            st.error(
                f"모델 `{model}`이 설치되어 있지 않습니다.\n\n"
                "사이드바 → '모델 추가 다운로드'에서 설치하세요."
            )
    except ValueError as exc:
        with st.chat_message("assistant"):
            st.warning(f"입력 오류: {exc}")
    except Exception as exc:
        with st.chat_message("assistant"):
            show_error(exc, "AI 응답 생성 중")
    return None
