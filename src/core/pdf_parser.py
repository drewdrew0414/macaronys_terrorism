"""
텍스트 추출 모듈 — PDF(표 포함), 웹 URL, YouTube 자막.

예외 처리 전략:
- PDF  : 페이지별 예외를 격리 — 한 페이지 실패가 전체 추출을 막지 않음
- URL  : trafilatura 실패 → BeautifulSoup 폴백 → 네트워크 오류는 호출자에 전파
- YouTube: 자막 없는 영상·비공개 영상에 대한 명시적 오류 메시지
"""
from __future__ import annotations

import io
import re
import pdfplumber
import trafilatura
import requests
from bs4 import BeautifulSoup

# youtube-transcript-api: 없으면 None으로 설정해 ImportError를 런타임으로 이연
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None  # type: ignore[assignment,misc]

_YT_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})"
)

# requests 기본 타임아웃 (초)
_HTTP_TIMEOUT = 15

# 지원하는 MIME 타입별 인코딩 폴백 목록
_TEXT_ENCODINGS = ["utf-8", "cp949", "euc-kr", "latin-1"]


# ── PDF ──────────────────────────────────────────────────────────────────────

def _table_to_markdown(table: list) -> str:
    """
    pdfplumber 표 데이터를 마크다운 표로 변환한다.

    None 셀 → 빈 문자열, 셀 내 줄바꿈 → 공백으로 처리.
    첫 행이 완전히 비어 있으면 빈 문자열을 반환한다.
    """
    if not table or not table[0]:
        return ""

    def cell(v: object) -> str:
        return str(v).replace("\n", " ").strip() if v is not None else ""

    rows = [[cell(c) for c in row] for row in table]
    if not rows or all(c == "" for c in rows[0]):
        return ""

    header = rows[0]
    body   = rows[1:]
    n_cols = max(len(header), 1)

    md  = "| " + " | ".join(header) + " |\n"
    md += "| " + " | ".join(["---"] * n_cols) + " |\n"
    for row in body:
        padded = row + [""] * max(0, n_cols - len(row))
        md += "| " + " | ".join(padded[:n_cols]) + " |\n"
    return md


def from_pdf(file_bytes: bytes) -> str:
    """
    PDF 바이트에서 텍스트와 표를 모두 추출한다.

    페이지별로 예외를 격리하므로 일부 페이지 실패 시에도 나머지 내용을 반환한다.

    Raises:
        ValueError:  file_bytes가 비어 있거나 PDF 형식이 아닐 때
        RuntimeError: 암호화된 PDF 등 pdfplumber가 열 수 없을 때
    """
    if not file_bytes:
        raise ValueError("PDF 데이터가 비어 있습니다.")

    # PDF 매직 바이트 확인 (%PDF-)
    if not file_bytes[:5].startswith(b"%PDF-"):
        raise ValueError("PDF 형식이 아닌 파일입니다. PDF 파일을 업로드하세요.")

    try:
        pdf_obj = pdfplumber.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise RuntimeError(
            f"PDF를 열 수 없습니다. 파일이 손상됐거나 암호화된 PDF일 수 있습니다. ({exc})"
        ) from exc

    parts: list[str] = []

    with pdf_obj:
        if len(pdf_obj.pages) == 0:
            raise ValueError("PDF에 페이지가 없습니다.")

        for page_num, page in enumerate(pdf_obj.pages, 1):
            # 텍스트 추출 (실패해도 계속)
            try:
                text = page.extract_text() or ""
                if text.strip():
                    parts.append(text)
            except Exception:
                parts.append(f"[페이지 {page_num} 텍스트 추출 실패]")

            # 표 추출 (실패해도 계속)
            try:
                tables     = page.extract_tables() or []
                table_mds  = [_table_to_markdown(t) for t in tables]
                table_mds  = [m for m in table_mds if m]
                if table_mds:
                    parts.append(
                        f"\n[페이지 {page_num} 표 데이터]\n" + "\n\n".join(table_mds)
                    )
            except Exception:
                pass  # 표 추출 실패는 무시 (본문은 이미 추가됨)

    result = "\n\n".join(filter(None, parts))
    if not result.strip():
        raise ValueError(
            "PDF에서 텍스트를 추출할 수 없습니다. "
            "스캔된 이미지 PDF는 OCR이 필요합니다."
        )
    return result


# ── YouTube ───────────────────────────────────────────────────────────────────

def is_youtube(url: str) -> bool:
    """URL이 YouTube 영상 링크인지 확인한다."""
    return bool(_YT_RE.search(url))


def from_youtube(url: str) -> str:
    """
    YouTube 자막을 추출해 하나의 문자열로 반환한다.

    youtube-transcript-api v1.x 이상의 인스턴스 기반 API를 사용한다.
    자막 우선순위: ko → en → 첫 번째 사용 가능 자막

    Raises:
        ValueError:  URL에서 YouTube ID를 추출할 수 없을 때
        RuntimeError: 자막이 없거나 비공개 영상일 때
    """
    if YouTubeTranscriptApi is None:
        raise RuntimeError(
            "youtube-transcript-api가 설치되어 있지 않습니다. "
            "`pip install youtube-transcript-api`를 실행하세요."
        )

    match = _YT_RE.search(url)
    if not match:
        raise ValueError(f"YouTube URL에서 영상 ID를 추출할 수 없습니다: {url}")

    video_id = match.group(1)
    api = YouTubeTranscriptApi()

    try:
        try:
            # 1차: 한국어·영어 자막 시도
            fetched = api.fetch(video_id, languages=["ko", "en"])
        except Exception:
            # 폴백: 사용 가능한 첫 번째 자막
            transcript_list = api.list(video_id)
            available = list(transcript_list)
            if not available:
                raise RuntimeError("이 영상에 사용 가능한 자막이 없습니다.")
            fetched = available[0].fetch()

    except RuntimeError:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if "disabled" in msg or "no transcript" in msg:
            raise RuntimeError("이 영상은 자막이 비활성화되어 있습니다.") from exc
        if "unavailable" in msg or "private" in msg:
            raise RuntimeError("영상에 접근할 수 없습니다. 비공개 또는 삭제된 영상일 수 있습니다.") from exc
        raise RuntimeError(f"YouTube 자막 추출 실패: {exc}") from exc

    # FetchedTranscript는 FetchedTranscriptSnippet 객체의 이터러블
    # 각 snippet은 .text 속성을 가짐
    try:
        text = " ".join(
            snippet.text for snippet in fetched if snippet.text and snippet.text.strip()
        )
    except AttributeError:
        # 이전 API 버전 폴백 (dict 형식)
        text = " ".join(
            seg.get("text", "") for seg in fetched if seg.get("text", "").strip()
        )

    if not text.strip():
        raise RuntimeError("자막 데이터가 비어 있습니다.")
    return text


# ── 웹 URL ────────────────────────────────────────────────────────────────────

def from_url(url: str) -> str:
    """
    웹 페이지 URL에서 본문 텍스트를 추출한다.
    YouTube URL은 from_youtube()로 분기한다.

    1차: trafilatura (광고·메뉴 제거, 본문만)
    폴백: BeautifulSoup (모든 텍스트)

    Raises:
        ValueError:  URL 형식이 잘못됐을 때
        RuntimeError: 네트워크 오류 또는 텍스트 추출 실패
    """
    if not url or not url.strip():
        raise ValueError("URL이 비어 있습니다.")

    if is_youtube(url):
        return from_youtube(url)

    # trafilatura
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text and text.strip():
                return text
    except Exception:
        pass  # trafilatura 실패 → BeautifulSoup 폴백

    # BeautifulSoup 폴백
    try:
        resp = requests.get(url, timeout=_HTTP_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (compatible; InputTool/1.0)"
        })
        resp.raise_for_status()

        # 인코딩 자동 감지 (Content-Type 우선, 폴백 순서 시도)
        for enc in _TEXT_ENCODINGS:
            try:
                html = resp.content.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            html = resp.text  # requests의 감지 결과 사용

        soup = BeautifulSoup(html, "html.parser")
        # script · style 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        if not text.strip():
            raise RuntimeError(
                "페이지에서 텍스트를 추출할 수 없습니다. "
                "JavaScript로 렌더링되는 페이지일 수 있습니다."
            )
        return text

    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"요청 시간이 초과됐습니다 ({_HTTP_TIMEOUT}초). "
            "페이지가 응답하지 않거나 URL이 잘못됐을 수 있습니다."
        )
    except requests.exceptions.SSLError:
        raise RuntimeError(
            "SSL 인증서 오류가 발생했습니다. HTTPS URL을 확인하세요."
        )
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"연결할 수 없습니다. 인터넷 연결이나 URL을 확인하세요. ({exc})"
        ) from exc
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response else "?"
        raise RuntimeError(
            f"HTTP {code} 오류: 페이지에 접근할 수 없습니다."
        ) from exc
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"URL 추출 중 예상치 못한 오류: {exc}") from exc
