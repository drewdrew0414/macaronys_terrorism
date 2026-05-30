"""src/core/pdf_parser.py 테스트."""
import pytest
from unittest.mock import patch, MagicMock
from src.core.pdf_parser import (
    _table_to_markdown,
    from_pdf,
    is_youtube,
    from_youtube,
    from_url,
)


# ── _table_to_markdown ────────────────────────────────────────────────────────

class TestTableToMarkdown:
    def test_basic_table(self, pdfplumber_table):
        md = _table_to_markdown(pdfplumber_table)
        assert "| 이름 | 점수 | 등급 |" in md
        assert "| --- | --- | --- |" in md
        assert "| 김철수 | 95 | A |" in md
        assert "| 이영희 | 82 | B |" in md

    def test_none_cell_becomes_empty(self, pdfplumber_table):
        md = _table_to_markdown(pdfplumber_table)
        assert "|  | 77 | C |" in md

    def test_empty_table_returns_empty(self):
        assert _table_to_markdown([]) == ""
        assert _table_to_markdown([[]]) == ""

    def test_all_none_header_returns_empty(self):
        table = [[None, None], ["a", "b"]]
        result = _table_to_markdown(table)
        assert result == ""

    def test_newline_in_cell_replaced_with_space(self):
        table = [["제목\n부제목", "값"], ["data", "1"]]
        md = _table_to_markdown(table)
        assert "제목\n부제목" not in md
        assert "제목 부제목" in md

    def test_short_row_padded(self):
        """데이터 행이 헤더보다 짧으면 빈 열로 채워야 한다."""
        table = [["A", "B", "C"], ["x"]]  # 데이터 행에 열 부족
        md = _table_to_markdown(table)
        assert "| x |  |  |" in md

    def test_single_column_table(self):
        table = [["항목"], ["값1"], ["값2"]]
        md = _table_to_markdown(table)
        assert "| 항목 |" in md
        assert "| 값1 |" in md


# ── from_pdf ──────────────────────────────────────────────────────────────────

class TestFromPdf:
    def test_empty_bytes_raises_value_error(self):
        with pytest.raises(ValueError, match="비어 있습니다"):
            from_pdf(b"")

    def test_non_pdf_bytes_raises_value_error(self):
        with pytest.raises(ValueError, match="PDF 형식"):
            from_pdf(b"NOT A PDF FILE")

    def test_valid_pdf_returns_text(self, sample_pdf_bytes):
        """실제 PDF 바이너리에서 텍스트를 추출한다."""
        result = from_pdf(sample_pdf_bytes)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_encrypted_pdf_raises_runtime_error(self):
        """pdfplumber가 열 수 없는 파일은 RuntimeError를 발생시킨다."""
        fake_pdf = b"%PDF-1.4\n corrupted content"
        with pytest.raises((ValueError, RuntimeError)):
            from_pdf(fake_pdf)

    def test_table_included_in_output(self):
        """pdfplumber 표 추출이 실패해도 텍스트는 반환되어야 한다."""
        with patch("pdfplumber.open") as mock_open:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "본문 텍스트"
            mock_page.extract_tables.return_value = [
                [["이름", "점수"], ["홍길동", "100"]]
            ]
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = lambda s: mock_pdf
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_pdf

            result = from_pdf(b"%PDF-1.4\ndummy")
            assert "본문 텍스트" in result
            assert "[페이지 1 표 데이터]" in result
            assert "| 이름 | 점수 |" in result

    def test_page_extraction_failure_continues(self):
        """한 페이지가 실패해도 다른 페이지 결과를 반환한다."""
        with patch("pdfplumber.open") as mock_open:
            page1 = MagicMock()
            page1.extract_text.side_effect = Exception("페이지 오류")
            page1.extract_tables.return_value = []

            page2 = MagicMock()
            page2.extract_text.return_value = "두 번째 페이지 텍스트"
            page2.extract_tables.return_value = []

            mock_pdf = MagicMock()
            mock_pdf.pages = [page1, page2]
            mock_pdf.__enter__ = lambda s: mock_pdf
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_pdf

            result = from_pdf(b"%PDF-1.4\ndummy")
            assert "두 번째 페이지 텍스트" in result


# ── is_youtube ────────────────────────────────────────────────────────────────

class TestIsYoutube:
    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
    ])
    def test_valid_youtube_urls(self, url):
        assert is_youtube(url) is True

    @pytest.mark.parametrize("url", [
        "https://example.com",
        "https://vimeo.com/123456",
        "https://youtube.com/",          # 영상 없음
        "https://youtu.be/",             # ID 없음
        "",
    ])
    def test_non_youtube_urls(self, url):
        assert is_youtube(url) is False


# ── from_youtube ──────────────────────────────────────────────────────────────

class TestFromYoutube:
    def test_invalid_url_raises_value_error(self):
        with pytest.raises(ValueError, match="YouTube URL"):
            from_youtube("https://example.com/not-youtube")

    def test_successful_transcript_extraction(self):
        """youtube-transcript-api v1.x 인스턴스 기반 API 모킹."""
        mock_snippet1 = MagicMock(); mock_snippet1.text = "Hello"
        mock_snippet2 = MagicMock(); mock_snippet2.text = "World"
        mock_fetched = [mock_snippet1, mock_snippet2]

        mock_api_instance = MagicMock()
        mock_api_instance.fetch.return_value = mock_fetched

        with patch("src.core.pdf_parser.YouTubeTranscriptApi",
                   return_value=mock_api_instance):
            result = from_youtube("https://youtu.be/dQw4w9WgXcQ")
        assert result == "Hello World"

    def test_no_transcript_falls_back_to_list(self):
        """fetch 실패 시 list() API로 폴백한다."""
        mock_snippet = MagicMock(); mock_snippet.text = "Fallback text"
        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = [mock_snippet]

        mock_api_instance = MagicMock()
        mock_api_instance.fetch.side_effect = Exception("No ko/en transcript")
        mock_api_instance.list.return_value = [mock_transcript]

        with patch("src.core.pdf_parser.YouTubeTranscriptApi",
                   return_value=mock_api_instance):
            result = from_youtube("https://youtu.be/dQw4w9WgXcQ")
        assert result == "Fallback text"

    def test_no_transcripts_at_all_raises_runtime_error(self):
        mock_api_instance = MagicMock()
        mock_api_instance.fetch.side_effect = Exception("no transcript")
        mock_api_instance.list.return_value = []  # 빈 리스트

        with patch("src.core.pdf_parser.YouTubeTranscriptApi",
                   return_value=mock_api_instance):
            with pytest.raises(RuntimeError):
                from_youtube("https://youtu.be/dQw4w9WgXcQ")

    def test_empty_result_raises_runtime_error(self):
        mock_snippet1 = MagicMock(); mock_snippet1.text = "  "
        mock_snippet2 = MagicMock(); mock_snippet2.text = ""
        mock_api_instance = MagicMock()
        mock_api_instance.fetch.return_value = [mock_snippet1, mock_snippet2]

        with patch("src.core.pdf_parser.YouTubeTranscriptApi",
                   return_value=mock_api_instance):
            with pytest.raises(RuntimeError, match="비어 있습니다"):
                from_youtube("https://youtu.be/dQw4w9WgXcQ")


# ── from_url ──────────────────────────────────────────────────────────────────

class TestFromUrl:
    def test_empty_url_raises_value_error(self):
        with pytest.raises(ValueError):
            from_url("")

    def test_trafilatura_success(self):
        with patch("trafilatura.fetch_url", return_value="<html>content</html>"):
            with patch("trafilatura.extract", return_value="추출된 본문 텍스트"):
                result = from_url("https://example.com")
        assert result == "추출된 본문 텍스트"

    def test_fallback_to_beautifulsoup_when_trafilatura_fails(self):
        import requests
        mock_resp = MagicMock()
        mock_resp.content = "<html><body><p>BS4 extracted text</p></body></html>".encode("utf-8")
        mock_resp.text = "<html><body><p>BS4 extracted text</p></body></html>"
        mock_resp.raise_for_status = MagicMock()

        with patch("trafilatura.fetch_url", return_value=None):
            with patch("trafilatura.extract", return_value=None):
                with patch("requests.get", return_value=mock_resp):
                    result = from_url("https://example.com")
        assert "BS4 extracted text" in result

    def test_timeout_raises_runtime_error(self):
        import requests
        with patch("trafilatura.fetch_url", return_value=None):
            with patch("trafilatura.extract", return_value=None):
                with patch("requests.get",
                           side_effect=requests.exceptions.Timeout()):
                    with pytest.raises(RuntimeError, match="시간이 초과"):
                        from_url("https://example.com")

    def test_http_error_raises_runtime_error(self):
        import requests
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        http_err = requests.exceptions.HTTPError(response=mock_resp)

        with patch("trafilatura.fetch_url", return_value=None):
            with patch("trafilatura.extract", return_value=None):
                with patch("requests.get", side_effect=http_err):
                    with pytest.raises(RuntimeError, match="HTTP"):
                        from_url("https://example.com")

    def test_youtube_url_delegates_to_from_youtube(self):
        with patch("src.core.pdf_parser.from_youtube", return_value="유튜브 자막") as mock_yt:
            result = from_url("https://youtu.be/dQw4w9WgXcQ")
        mock_yt.assert_called_once_with("https://youtu.be/dQw4w9WgXcQ")
        assert result == "유튜브 자막"
