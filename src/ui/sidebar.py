"""
사이드바 UI.

예외 처리:
- ollama 커맨드 없음   → FileNotFoundError로 잡아 설치 안내
- ollama list 타임아웃  → 5초 초과 시 경고 표시
- detect() 실패       → system_monitor 내부에서 기본값 반환
- 다운로드 실패        → stderr 내용 표시 후 계속 실행
"""
from __future__ import annotations

import subprocess
import streamlit as st
from config.models import model_for_vram, get_installed_models, refresh_installed_models, GEMMA_MODELS
from config.settings import get_presets, get_default_preset, SUGGESTED_MODELS
from src.utils.system_monitor import detect
from src.utils import session_state
from src.utils.i18n import t


@st.dialog("이용약관 / Terms of Service", width="large")
def _terms_dialog(model: str) -> None:
    """이용약관 모달. 동의 시 _pending_download 플래그를 설정하고 rerun."""
    st.caption(t("terms_scroll"))
    with st.container(height=440):
        st.markdown(t("terms_text"))
    st.divider()
    col_ok, col_cancel = st.columns(2)
    with col_ok:
        if st.button(t("terms_accept"), type="primary", use_container_width=True):
            session_state.set_val("_pending_download", model)
            st.rerun()
    with col_cancel:
        if st.button(t("terms_decline"), use_container_width=True):
            st.rerun()


def render() -> tuple[str, str]:
    """사이드바를 그리고 (active_model, system_prompt)를 반환한다."""
    with st.sidebar:
        _render_top_bar()
        st.divider()
        active_model = _render_model_section()
        st.divider()
        system_prompt = _render_prompt_section()
    _run_pending_download()
    return active_model, system_prompt


def _render_top_bar() -> None:
    lang_options  = {"한국어": "ko", "English": "en"}
    current_lang  = session_state.get("lang") or "ko"
    current_label = next(
        (k for k, v in lang_options.items() if v == current_lang),
        "한국어",
    )
    col_lang, col_theme = st.columns([3, 2])
    with col_lang:
        chosen = st.selectbox(
            t("lang_label"), list(lang_options.keys()),
            index=list(lang_options.keys()).index(current_label),
            label_visibility="collapsed",
        )
        session_state.set_val("lang", lang_options[chosen])
    with col_theme:
        is_dark = st.toggle(
            t("theme_toggle"),
            value=(session_state.get("theme") == "dark"),
        )
        session_state.set_val("theme", "dark" if is_dark else "light")


def _render_model_section() -> str:
    st.markdown(f"### {t('sidebar_model')}")

    try:
        system, effective_gb, compute_mode = detect()
    except Exception:
        system, effective_gb, compute_mode = "Unknown", 4.0, "cpu"

    safe_model = model_for_vram(effective_gb)

    col1, col2 = st.columns(2)
    col1.metric(t("metric_os"), system)
    col2.metric(t("metric_memory"), f"{effective_gb:.0f} GB")

    if compute_mode == "cpu":
        st.caption(t("sys_mode_cpu"))

    installed = _safe_get_installed()
    if installed:
        default_idx  = installed.index(safe_model) if safe_model in installed else 0
        active_model = st.selectbox(
            t("sidebar_installed"), options=installed, index=default_idx
        )
        st.caption(t("sidebar_recommend", model=safe_model))
    else:
        st.warning(t("sidebar_no_models"))
        active_model = st.selectbox(t("model_select"), GEMMA_MODELS)

    session_state.set_val("_active_model", active_model)

    if st.button(t("sidebar_refresh"), use_container_width=True):
        refresh_installed_models()
        st.rerun()

    _render_download_section()
    return active_model


def _safe_get_installed() -> list[str]:
    """ollama list 실패 시 빈 리스트를 반환한다."""
    try:
        return get_installed_models()
    except Exception:
        return []


def _render_download_section() -> None:
    with st.expander(t("sidebar_dl_title"), expanded=False):
        try:
            installed     = set(_safe_get_installed())
            not_installed = [m for m in SUGGESTED_MODELS if m not in installed]
        except Exception:
            not_installed = SUGGESTED_MODELS

        if not not_installed:
            st.success("추천 모델이 모두 설치되어 있습니다.")
            return

        model_to_dl = st.selectbox(
            t("sidebar_dl_select"), options=not_installed, key="dl_select"
        )
        if st.button(t("btn_download"), key="btn_dl_new", use_container_width=True):
            _terms_dialog(model_to_dl)


def _run_pending_download() -> None:
    """이용약관 동의 후 대기 중인 모델을 다운로드한다."""
    model = session_state.get("_pending_download")
    if not model:
        return
    session_state.set_val("_pending_download", None)

    with st.sidebar:
        with st.status(t("download_status", model=model), expanded=True) as status:
            try:
                proc = subprocess.run(
                    ["ollama", "pull", model],
                    capture_output=True, text=True, timeout=600,  # 10분 타임아웃
                )
                if proc.returncode == 0:
                    status.update(label=t("download_complete", model=model), state="complete")
                    refresh_installed_models()
                else:
                    status.update(label=t("download_failed"), state="error")
                    st.error(proc.stderr[:400] or "알 수 없는 오류")
            except FileNotFoundError:
                status.update(label="Ollama 없음", state="error")
                st.error(t("ollama_not_found"))
            except subprocess.TimeoutExpired:
                status.update(label="타임아웃", state="error")
                st.error("다운로드 시간이 초과됐습니다 (10분). 네트워크 연결을 확인하세요.")
            except Exception as exc:
                status.update(label=t("download_failed"), state="error")
                st.error(str(exc))
    st.rerun()


def _render_prompt_section() -> str:
    st.markdown(f"### {t('sidebar_prompt')}")
    st.caption(t("sidebar_prompt_caption"))

    lang    = session_state.get("lang") or "ko"
    presets = get_presets(lang)
    names   = list(presets.keys())
    default = get_default_preset(lang)
    idx     = names.index(default) if default in names else 0
    selected    = st.selectbox(t("preset_label"), options=names, index=idx)
    custom_key  = "Custom" if lang == "en" else "사용자 지정"
    default_txt = (
        session_state.get("system_prompt") or ""
        if selected == custom_key else presets.get(selected, "")
    )
    prompt = st.text_area(
        "prompt", value=default_txt, height=180,
        label_visibility="collapsed", placeholder=t("prompt_placeholder"),
    )
    session_state.set_val("system_prompt", prompt)
    n     = len(prompt)
    color = "#ef4444" if n > 1000 else "#6b7280"
    st.markdown(
        f"<p style='color:{color};font-size:0.75rem;margin:0'>"
        f"{t('prompt_char_count', n=n)}</p>",
        unsafe_allow_html=True,
    )
    return prompt
