"""src/core/chunker.py 테스트."""
import pytest
from src.core.chunker import split, needs_chunking
from config.settings import CHUNK_SIZE


class TestSplit:
    def test_empty_string_returns_empty_list(self):
        assert split("") == []

    def test_none_returns_empty_list(self):
        assert split(None) == []

    def test_whitespace_only_returns_empty_list(self):
        assert split("   \n  ") == []

    def test_short_text_returns_single_chunk(self):
        text = "짧은 텍스트"
        result = split(text)
        assert result == [text]

    def test_long_text_splits_into_multiple_chunks(self, long_text):
        chunks = split(long_text)
        assert len(chunks) > 1

    def test_chunks_cover_all_text(self, long_text):
        """분할된 청크를 이어붙이면 원본과 같아야 한다."""
        chunks = split(long_text)
        assert "".join(chunks) == long_text

    def test_each_chunk_within_size_limit(self, long_text):
        chunks = split(long_text)
        for chunk in chunks:
            assert len(chunk) <= max(CHUNK_SIZE, 100)

    def test_exact_chunk_size_boundary(self):
        """CHUNK_SIZE와 정확히 같은 길이는 1개 청크여야 한다."""
        text = "a" * CHUNK_SIZE
        assert len(split(text)) == 1

    def test_one_over_chunk_size_splits(self):
        """CHUNK_SIZE + 1은 2개 청크여야 한다."""
        text = "a" * (CHUNK_SIZE + 1)
        assert len(split(text)) == 2


class TestNeedsChunking:
    def test_empty_string_returns_false(self):
        assert needs_chunking("") is False

    def test_none_returns_false(self):
        assert needs_chunking(None) is False

    def test_short_text_returns_false(self, sample_text):
        assert needs_chunking(sample_text) is False

    def test_long_text_returns_true(self, long_text):
        assert needs_chunking(long_text) is True

    def test_exactly_chunk_size_returns_false(self):
        assert needs_chunking("a" * CHUNK_SIZE) is False

    def test_over_chunk_size_returns_true(self):
        assert needs_chunking("a" * (CHUNK_SIZE + 1)) is True
