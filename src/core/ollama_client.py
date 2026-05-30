"""
Ollama Chat API 클라이언트.

OLLAMA_HOST 환경 변수로 로컬·원격 서버를 선택할 수 있다.
기본값은 http://localhost:11434 (로컬 Ollama).

예외 처리:
- ConnectionRefusedError → Ollama 서버 미실행 안내
- ResponseError(model not found) → 모델 미설치 안내
- 스트리밍 중 예외 → Generator 내에서 re-raise (호출자가 처리)
"""
from __future__ import annotations

from typing import Generator
import ollama as _ollama
from config.env import OLLAMA_HOST

# OLLAMA_HOST가 기본 로컬이 아니면 Client 인스턴스 생성
if OLLAMA_HOST and OLLAMA_HOST != "http://localhost:11434":
    _client = _ollama.Client(host=OLLAMA_HOST)
else:
    _client = _ollama  # type: ignore[assignment]

Message = dict[str, str]


class OllamaConnectionError(RuntimeError):
    """Ollama 서버에 연결할 수 없을 때 발생하는 커스텀 예외."""


class OllamaModelNotFoundError(RuntimeError):
    """요청한 모델이 설치되어 있지 않을 때 발생하는 커스텀 예외."""


def chat(
    messages: list[Message],
    model: str,
    stream: bool = False,
) -> str | Generator:
    """
    Ollama 모델에 메시지를 전송하고 응답을 반환한다.

    Raises:
        OllamaConnectionError:    Ollama 서버가 실행 중이지 않을 때
        OllamaModelNotFoundError: 모델이 설치되어 있지 않을 때
        RuntimeError:             그 외 API 오류
    """
    _validate_inputs(messages, model)

    try:
        if stream:
            return _stream_response(messages, model)

        response = _client.chat(model=model, messages=messages)
        content  = response["message"]["content"]

        if not content or not content.strip():
            raise RuntimeError("모델이 빈 응답을 반환했습니다. 다시 시도하세요.")

        return content

    except _ollama.ResponseError as exc:
        _handle_response_error(exc, model)
    except (ConnectionRefusedError, OSError) as exc:
        raise OllamaConnectionError(
            f"Ollama 서버({OLLAMA_HOST})에 연결할 수 없습니다. `ollama serve`를 실행하세요."
        ) from exc
    except Exception as exc:
        # 이미 변환된 커스텀 예외는 그대로 전파
        if isinstance(exc, (OllamaConnectionError, OllamaModelNotFoundError)):
            raise
        raise RuntimeError(f"Ollama API 오류: {exc}") from exc


def _stream_response(messages: list[Message], model: str) -> Generator:
    """
    스트리밍 응답 Generator.

    스트리밍 도중 예외 발생 시 Generator 내에서 OllamaConnectionError로 변환한다.
    st.write_stream()은 Generator를 소비하므로 호출자 try-except에서 잡힌다.
    """
    try:
        for chunk in _client.chat(model=model, messages=messages, stream=True):
            yield chunk["message"]["content"]
    except _ollama.ResponseError as exc:
        _handle_response_error(exc, model)
    except (ConnectionRefusedError, OSError) as exc:
        raise OllamaConnectionError(
            f"스트리밍 중 Ollama 서버 연결이 끊겼습니다."
        ) from exc


def _validate_inputs(messages: list[Message], model: str) -> None:
    """입력값 기본 검증 — 빈 messages나 빈 model 이름 방지."""
    if not model or not model.strip():
        raise ValueError("모델 이름이 비어 있습니다. 사이드바에서 모델을 선택하세요.")
    if not messages:
        raise ValueError("messages 리스트가 비어 있습니다.")
    last = messages[-1]
    if last.get("role") != "user" or not last.get("content", "").strip():
        raise ValueError("마지막 메시지가 비어 있거나 user role이 아닙니다.")


def _handle_response_error(exc: "_ollama.ResponseError", model: str) -> None:
    """ollama.ResponseError를 의미있는 커스텀 예외로 변환한다."""
    msg = str(exc).lower()
    if "not found" in msg or "pull" in msg:
        raise OllamaModelNotFoundError(
            f"모델 '{model}'이 설치되어 있지 않습니다. "
            f"사이드바 '모델 추가 다운로드'에서 설치하세요."
        ) from exc
    raise RuntimeError(f"Ollama 응답 오류: {exc}") from exc
