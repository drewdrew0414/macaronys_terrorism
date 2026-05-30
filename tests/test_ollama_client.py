"""src/core/ollama_client.py 테스트."""
import pytest
from unittest.mock import patch, MagicMock
from src.core.ollama_client import (
    chat,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    _validate_inputs,
)


# ── _validate_inputs ──────────────────────────────────────────────────────────

class TestValidateInputs:
    def test_empty_model_raises_value_error(self, sample_messages):
        with pytest.raises(ValueError, match="모델 이름"):
            _validate_inputs(sample_messages, "")

    def test_none_model_raises_value_error(self, sample_messages):
        with pytest.raises(ValueError, match="모델 이름"):
            _validate_inputs(sample_messages, None)

    def test_empty_messages_raises_value_error(self):
        with pytest.raises(ValueError, match="messages"):
            _validate_inputs([], "gemma3:4b")

    def test_last_message_not_user_raises_value_error(self):
        messages = [{"role": "assistant", "content": "응답"}]
        with pytest.raises(ValueError, match="user role"):
            _validate_inputs(messages, "gemma3:4b")

    def test_last_message_empty_content_raises_value_error(self):
        messages = [{"role": "user", "content": "  "}]
        with pytest.raises(ValueError, match="비어 있"):
            _validate_inputs(messages, "gemma3:4b")

    def test_valid_inputs_pass(self, sample_messages):
        _validate_inputs(sample_messages, "gemma3:4b")  # 예외 없어야 함


# ── chat ──────────────────────────────────────────────────────────────────────

class TestChat:
    def test_successful_chat_returns_content(self, sample_messages, mock_ollama_response):
        with patch("src.core.ollama_client._client") as mock_client:
            mock_client.chat.return_value = mock_ollama_response
            result = chat(sample_messages, "gemma3:4b")
        assert result == "## 요약\n- 핵심 내용 1\n- 핵심 내용 2"

    def test_connection_refused_raises_ollama_connection_error(self, sample_messages):
        with patch("src.core.ollama_client._client") as mock_client:
            mock_client.chat.side_effect = ConnectionRefusedError()
            with pytest.raises(OllamaConnectionError):
                chat(sample_messages, "gemma3:4b")

    def test_model_not_found_raises_ollama_model_not_found_error(self, sample_messages):
        import ollama
        err = ollama.ResponseError("model 'gemma3:4b' not found, try pulling it first")

        with patch("src.core.ollama_client._client") as mock_client:
            mock_client.chat.side_effect = err
            with pytest.raises(OllamaModelNotFoundError):
                chat(sample_messages, "gemma3:4b")

    def test_empty_response_raises_runtime_error(self, sample_messages):
        with patch("src.core.ollama_client._client") as mock_client:
            mock_client.chat.return_value = {"message": {"content": "  "}}
            with pytest.raises(RuntimeError, match="빈 응답"):
                chat(sample_messages, "gemma3:4b")

    def test_stream_returns_generator(self, sample_messages):
        chunks = [
            {"message": {"content": "## "}},
            {"message": {"content": "요약"}},
            {"message": {"content": "\n결과"}},
        ]
        with patch("src.core.ollama_client._client") as mock_client:
            mock_client.chat.return_value = iter(chunks)
            gen = chat(sample_messages, "gemma3:4b", stream=True)
        import types
        assert isinstance(gen, types.GeneratorType)

    def test_stream_yields_tokens(self, sample_messages):
        chunks = [
            {"message": {"content": "토큰1"}},
            {"message": {"content": "토큰2"}},
        ]
        with patch("src.core.ollama_client._client") as mock_client:
            mock_client.chat.return_value = iter(chunks)
            tokens = list(chat(sample_messages, "gemma3:4b", stream=True))
        assert tokens == ["토큰1", "토큰2"]

    def test_os_error_raises_ollama_connection_error(self, sample_messages):
        with patch("src.core.ollama_client._client") as mock_client:
            mock_client.chat.side_effect = OSError("connection error")
            with pytest.raises(OllamaConnectionError):
                chat(sample_messages, "gemma3:4b")
