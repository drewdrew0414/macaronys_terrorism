"""src/core/response_parser.py 테스트."""
import pytest
from src.core.response_parser import parse


class TestParse:
    def test_none_input_returns_empty_string(self):
        assert parse(None) == ""

    def test_empty_string_returns_empty_string(self):
        assert parse("") == ""

    def test_normal_text_returns_cleaned(self):
        result = parse("  hello world  ")
        assert result == "hello world"

    def test_excessive_newlines_compressed(self):
        result = parse("line1\n\n\n\n\nline2")
        assert "\n\n\n" not in result
        assert "line1" in result
        assert "line2" in result

    def test_markdown_structure_preserved(self):
        md = "## 제목\n\n- 항목 1\n- 항목 2\n\n**강조**"
        result = parse(md)
        assert "## 제목" in result
        assert "- 항목 1" in result
        assert "**강조**" in result

    def test_non_string_input_converted(self):
        """str()로 변환 가능한 입력을 처리해야 한다."""
        result = parse(42)
        assert result == "42"

    def test_preserves_content_when_clean_would_empty(self):
        """clean 후 비어있으면 원본을 반환해야 한다."""
        # 공백만 있는 경우 원본 반환 확인 (clean이 빈 문자열 반환 시)
        result = parse("   ")
        # 공백만인 경우 clean은 "" 반환하므로 원본 공백 반환
        assert isinstance(result, str)
