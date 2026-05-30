"""src/utils/errors.py 테스트."""
import pytest
from unittest.mock import patch, MagicMock
from src.utils.errors import _classify, safe_run


class TestClassify:
    """_classify: 예외 → (제목, 해결방법) 튜플 매핑 검증."""

    def test_connection_refused_ollama(self):
        exc = ConnectionRefusedError("connection refused 11434")
        title, hint = _classify(exc)
        assert "Ollama" in title
        assert "ollama serve" in hint

    def test_model_not_found(self):
        exc = Exception("model 'gemma3:4b' not found, try pull")
        title, hint = _classify(exc)
        assert "모델" in title
        assert "설치" in hint or "다운로드" in hint

    def test_pdf_error(self):
        exc = Exception("pdfplumber failed")
        title, hint = _classify(exc)
        assert "PDF" in title

    def test_memory_error(self):
        exc = MemoryError("out of memory")
        title, hint = _classify(exc)
        assert "메모리" in title

    def test_timeout_error(self):
        import requests
        exc = requests.exceptions.Timeout()
        title, hint = _classify(exc)
        assert "시간" in title or "네트워크" in title

    def test_youtube_transcript_error(self):
        exc = Exception("No transcript found for video")
        title, hint = _classify(exc)
        assert "YouTube" in title or "자막" in title

    def test_encoding_error(self):
        exc = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")
        title, hint = _classify(exc)
        assert "인코딩" in title or "텍스트" in title

    def test_file_not_found(self):
        exc = FileNotFoundError("no such file")
        title, hint = _classify(exc)
        assert "파일" in title

    def test_unknown_exception_returns_generic(self):
        exc = Exception("completely unknown error xyz123")
        title, hint = _classify(exc)
        assert isinstance(title, str) and len(title) > 0
        assert isinstance(hint, str) and len(hint) > 0


class TestSafeRun:
    def test_successful_function_returns_result(self):
        result = safe_run(lambda x: x * 2, 5)
        assert result == 10

    def test_exception_returns_default_none(self):
        def fail():
            raise ValueError("오류")

        result = safe_run(fail)
        assert result is None

    def test_exception_returns_custom_default(self):
        def fail():
            raise RuntimeError("오류")

        result = safe_run(fail, default="기본값")
        assert result == "기본값"

    def test_exception_shows_error_in_streamlit(self):
        """예외 발생 시 st.error가 호출되어야 한다."""
        def fail():
            raise RuntimeError("테스트 오류")

        with patch("src.utils.errors.st") as mock_st:
            safe_run(fail, context="테스트 중")
            mock_st.error.assert_called_once()

    def test_passes_args_to_function(self):
        def add(a, b):
            return a + b

        result = safe_run(add, 3, 4)
        assert result == 7

    def test_passes_kwargs_to_function(self):
        def greet(name, greeting="안녕"):
            return f"{greeting}, {name}!"

        result = safe_run(greet, "홍길동", greeting="반가워요")
        assert result == "반가워요, 홍길동!"
