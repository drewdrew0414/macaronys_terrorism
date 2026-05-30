"""
음성 녹음 탭 UI.

예외 처리:
- faster-whisper 미설치 → 설치 안내 표시
- 빈 오디오 데이터     → 경고 메시지
- 임시 파일 정리      → finally 블록으로 보장
- GPU/CPU 모드 자동 폴백
"""
from __future__ import annotations

import os
import tempfile
import streamlit as st
from audio_recorder_streamlit import audio_recorder
from src.utils import session_state
from src.utils.i18n import t
from src.utils.errors import show_error
from src.ui.summary_view import render_summary_button


def render(model: str, system_prompt: str) -> None:
    """음성 녹음 탭 전체를 렌더링한다."""
    with st.container(border=True):
        st.markdown(f"**{t('audio_hint')}**")
        try:
            audio_bytes = audio_recorder(
                text="",
                recording_color="#ef4444",
                neutral_color="#3b82f6",
                icon_size="2x",
            )
        except Exception as exc:
            show_error(exc, "마이크 컴포넌트 로드 중")
            return

    if not audio_bytes:
        return

    # 최소 크기 검사 (헤더만 있는 빈 WAV ~ 44 bytes)
    if len(audio_bytes) < 100:
        st.warning("녹음된 오디오가 너무 짧습니다. 다시 녹음하세요.")
        return

    st.divider()
    col_play, col_dl = st.columns([3, 1])
    with col_play:
        st.audio(audio_bytes, format="audio/wav")
    with col_dl:
        st.download_button(
            label=t("btn_dl_wav"),
            data=audio_bytes,
            file_name="recording.wav",
            mime="audio/wav",
            use_container_width=True,
        )

    if st.button(t("btn_transcribe"), use_container_width=True):
        _transcribe(audio_bytes)

    transcript = session_state.get("audio_transcript")
    if transcript:
        with st.container(border=True):
            st.markdown(f"**{t('audio_result')}**")
            st.text_area("", transcript, height=160, label_visibility="collapsed")

        render_summary_button(
            text=transcript, model=model, system_prompt=system_prompt,
            source="audio", button_label=t("btn_sum_audio"), button_key="sum_audio",
        )


def _transcribe(audio_bytes: bytes) -> None:
    """
    faster-whisper로 WAV를 텍스트로 변환한다.

    임시 파일은 finally 블록에서 반드시 삭제한다.
    변환 실패 시 디바이스를 CPU로 폴백해 재시도한다.
    """
    # faster-whisper 설치 여부 확인
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        st.error(
            "faster-whisper가 설치되어 있지 않습니다.\n\n"
            "`pip install faster-whisper`를 실행하세요."
        )
        return

    from config.env import WHISPER_MODEL as MODEL_SIZE

    tmp_path: str | None = None
    try:
        # 임시 WAV 파일 생성
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with st.spinner(t("transcribe_spinner")):
            transcript = _try_transcribe(WhisperModel, MODEL_SIZE, tmp_path)

        if not transcript or not transcript.strip():
            st.warning("변환 결과가 비어 있습니다. 음성이 녹음됐는지 확인하세요.")
            return

        session_state.set_val("audio_transcript", transcript)
        st.success(t("transcribe_ok"))
        st.rerun()

    except MemoryError:
        st.error(
            "메모리가 부족해 Whisper를 실행할 수 없습니다.\n\n"
            "다른 프로그램을 종료하거나 더 작은 Whisper 모델을 사용하세요."
        )
    except Exception as exc:
        show_error(exc, "음성 변환 중")
    finally:
        # 임시 파일 반드시 삭제
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _try_transcribe(
    WhisperModel: type,
    model_size: str,
    wav_path: str,
) -> str:
    """
    Whisper 변환 시도.
    GPU(CUDA/MPS) 실패 시 CPU로 자동 폴백한다.
    """
    for device, compute_type in [("cuda", "float16"), ("cpu", "int8")]:
        try:
            wm = WhisperModel(model_size, device=device, compute_type=compute_type)
            segments, _ = wm.transcribe(wav_path)
            return " ".join(s.text for s in segments)
        except Exception as exc:
            if device == "cpu":
                raise  # CPU도 실패 → 호출자에 전파
            # GPU 실패 → CPU로 재시도
            continue
    return ""  # unreachable, for type checker
