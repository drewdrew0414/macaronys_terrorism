"""
소개(About) 섹션.

예외 처리:
- get_live_stats() 실패 → 개별 항목별로 격리, 0값으로 표시
- detect() 실패         → 기본값 사용
- config.env 임포트 실패 → 기본값 표시
"""
from __future__ import annotations

import streamlit as st
from config.models import model_for_vram
from src.utils.system_monitor import detect, get_live_stats
from src.utils.i18n import t


def render(theme: str = "light") -> None:
    """소개 섹션 전체를 렌더링한다."""
    _render_hero()
    _render_features()
    st.divider()
    _render_how_to_use()
    st.divider()
    _render_system_status()


def _render_hero() -> None:
    st.markdown(f"### {t('about_tagline')}")
    for line in t("about_desc").split("\\n"):
        if line.strip():
            st.caption(line)


def _render_features() -> None:
    features = [
        ("feat_docs",    "feat_docs_desc"),
        ("feat_audio",   "feat_audio_desc"),
        ("feat_url",     "feat_url_desc"),
        ("feat_chat",    "feat_chat_desc"),
        ("feat_local",   "feat_local_desc"),
        ("feat_privacy", "feat_privacy_desc"),
    ]
    cols = st.columns(3)
    for i, (title_key, desc_key) in enumerate(features):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{t(title_key)}**")
                st.caption(t(desc_key))


def _render_how_to_use() -> None:
    st.markdown(f"**{t('about_how_title')}**")
    st.markdown(t("how_step1"))
    st.markdown(t("how_step2"))
    st.markdown(t("how_step3"))


def _render_system_status() -> None:
    """실시간 시스템 현황. 각 항목 실패를 개별 격리해 UI 전체가 깨지지 않는다."""
    st.markdown(f"**{t('sys_title')}**")

    # detect() 실패 시 기본값 사용
    try:
        system, effective_gb, compute_mode = detect()
        safe_model = model_for_vram(effective_gb)
    except Exception:
        system, effective_gb, compute_mode, safe_model = "?", 4.0, "cpu", "gemma3:1b"

    # 실시간 통계 (실패 시 빈 dict 사용)
    try:
        stats = get_live_stats()
    except Exception:
        stats = {
            "cpu_percent": 0, "ram_used_gb": 0, "ram_total_gb": 0,
            "ram_available_gb": 0, "ram_percent": 0,
            "gpu_name": "", "gpu_vram_total_gb": 0, "gpu_vram_free_gb": 0,
        }

    col_cpu, col_ram, col_mode = st.columns(3)

    with col_cpu:
        try:
            st.metric(t("sys_cpu"), f"{stats['cpu_percent']:.0f}%")
        except Exception:
            st.metric(t("sys_cpu"), "N/A")

    with col_ram:
        try:
            st.metric(
                t("sys_ram"),
                f"{stats['ram_used_gb']:.1f} / {stats['ram_total_gb']:.0f} GB",
                delta=t("sys_ram_avail", n=stats["ram_available_gb"]),
                delta_color="off",
            )
        except Exception:
            st.metric(t("sys_ram"), "N/A")

    with col_mode:
        mode_label = {
            "cuda": t("sys_mode_cuda"),
            "mps":  t("sys_mode_mps"),
            "cpu":  t("sys_mode_cpu"),
        }.get(compute_mode, compute_mode)
        st.metric(t("sys_compute"), mode_label)

    if compute_mode == "cpu":
        try:
            budget = stats["ram_available_gb"] * 0.6
            st.info(t("sys_ram_budget", n=budget))
        except Exception:
            pass

    if stats.get("gpu_name"):
        try:
            st.caption(
                f"GPU: {stats['gpu_name']}  |  "
                f"VRAM: {stats['gpu_vram_free_gb']:.1f} / {stats['gpu_vram_total_gb']:.1f} GB 여유"
            )
        except Exception:
            pass

    st.success(f"{t('sys_safe_model')}: **{safe_model}**")

    try:
        col_a, col_b = st.columns(2)
        with col_a:
            cpu_pct = min(max(int(stats.get("cpu_percent", 0)), 0), 100)
            st.caption(f"CPU {cpu_pct}%")
            st.progress(cpu_pct / 100)
        with col_b:
            ram_pct = min(max(int(stats.get("ram_percent", 0)), 0), 100)
            st.caption(f"RAM {ram_pct}%")
            st.progress(ram_pct / 100)
    except Exception:
        pass

    try:
        from config.env import OLLAMA_HOST, WHISPER_MODEL as ENV_WHISPER
    except Exception:
        OLLAMA_HOST  = "http://localhost:11434"
        ENV_WHISPER  = "base"

    with st.expander(t("env_title"), expanded=False):
        st.code(
            f"{t('env_host')}:    {OLLAMA_HOST}\n"
            f"{t('env_whisper')}: {ENV_WHISPER}\n"
            f"OS:              {system}",
            language="text",
        )
        st.caption(".env 파일에서 설정값을 변경하세요 (.env.example 참고)")
