"""src/utils/text_cleaner.py 테스트."""
import pytest
from src.utils.text_cleaner import clean


class TestClean:
    def test_strips_leading_and_trailing_whitespace(self):
        assert clean("  hello  ") == "hello"

    def test_compresses_multiple_newlines(self):
        result = clean("a\n\n\n\nb")
        assert "\n\n\n" not in result
        assert "a" in result and "b" in result

    def test_preserves_double_newline_paragraph_breaks(self):
        result = clean("문단1\n\n문단2")
        assert "문단1\n\n문단2" == result

    def test_compresses_multiple_spaces(self):
        result = clean("a    b    c")
        assert result == "a b c"

    def test_compresses_tabs(self):
        result = clean("a\t\tb")
        assert result == "a b"

    def test_empty_string_returns_empty(self):
        assert clean("") == ""

    def test_markdown_structure_preserved(self):
        md = "## 제목\n\n- 항목 1\n- 항목 2"
        assert clean(md) == md

    def test_three_newlines_become_two(self):
        result = clean("a\n\n\nb")
        assert result == "a\n\nb"
