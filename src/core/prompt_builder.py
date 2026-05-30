"""
프롬프트 빌더 — Chat API 메시지 리스트를 조립한다.

예외 처리:
- 빈 텍스트나 None 입력은 빈 문자열로 안전 처리
- MAX_PROMPT_CHARS 초과 시 자동 잘림 (예외 없음)
- _get_lang() 실패 시 "ko" 기본값 사용
"""
from __future__ import annotations

from config.settings import MAX_PROMPT_CHARS, get_styles
from src.utils.i18n import t

Message = dict[str, str]


def build_messages(
    system_prompt: str,
    user_content: str,
    history: list[Message] | None = None,
) -> list[Message]:
    """
    Chat API messages 리스트를 조립한다.

    입력 검증:
    - system_prompt가 None이면 빈 문자열로 처리
    - user_content가 비거나 None이면 ValueError 발생
    - history의 각 항목이 role/content 키를 가지지 않으면 건너뜀
    """
    if user_content is None or not str(user_content).strip():
        raise ValueError("user_content가 비어 있습니다.")

    messages: list[Message] = []

    safe_system = (system_prompt or "").strip()
    if safe_system:
        messages.append({"role": "system", "content": safe_system})

    if history:
        for msg in history:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append(msg)

    messages.append({
        "role": "user",
        "content": str(user_content)[:MAX_PROMPT_CHARS],
    })
    return messages


def build_summary_user_message(text: str, style: str | None = None) -> str:
    """
    요약 요청 user 메시지를 만든다.

    text가 None이거나 비어 있으면 ValueError를 발생시킨다.
    style이 없거나 유효하지 않으면 기본 sum_prompt 템플릿을 사용한다.
    """
    if not text or not text.strip():
        raise ValueError("요약할 텍스트가 비어 있습니다.")

    lang             = _get_lang()
    style_instruction = get_styles(lang).get(style or "", "")

    safe_text = text[:MAX_PROMPT_CHARS]

    if style_instruction:
        return (
            f"{style_instruction}\n\n"
            "반드시 마크다운 형식으로 작성해.\n\n"
            f"{safe_text}"
        )
    return t("sum_prompt", text=safe_text)


def build_chunk_merge_message(chunk_summaries: list[str]) -> str:
    """
    청크별 요약을 병합하는 최종 요약 요청 메시지를 만든다.

    chunk_summaries가 비거나 모두 빈 문자열이면 ValueError를 발생시킨다.
    """
    valid = [s.strip() for s in (chunk_summaries or []) if s and s.strip()]
    if not valid:
        raise ValueError("병합할 청크 요약이 없습니다.")

    joined = "\n\n---\n\n".join(
        f"[청크 {i+1}]\n{s}" for i, s in enumerate(valid)
    )
    lang = _get_lang()

    if lang == "en":
        return (
            "The following are summaries of individual sections of a long document.\n"
            "Create a single, coherent final summary in markdown format.\n\n"
            f"{joined}"
        )
    return (
        "다음은 긴 문서를 여러 부분으로 나눠 각각 요약한 내용입니다.\n"
        "이를 종합해서 하나의 일관된 최종 요약을 마크다운 형식으로 작성해줘.\n\n"
        f"{joined}"
    )


def build_chat_system(system_prompt: str, context: str) -> str:
    """
    채팅 탭의 system 메시지를 만든다.

    context가 너무 길면 MAX_PROMPT_CHARS로 잘린다.
    system_prompt가 비면 컨텍스트 지시만 반환한다.
    """
    safe_ctx = (context or "")[:MAX_PROMPT_CHARS]
    if not safe_ctx.strip():
        return (system_prompt or "").strip()

    ctx_instruction = t("chat_system_ctx", ctx=safe_ctx)
    safe_system     = (system_prompt or "").strip()
    if safe_system:
        return safe_system + "\n\n" + ctx_instruction
    return ctx_instruction


def _get_lang() -> str:
    """현재 선택된 언어를 세션 상태에서 읽는다. 실패 시 'ko' 반환."""
    try:
        import streamlit as st
        return st.session_state.get("lang", "ko")
    except Exception:
        return "ko"
