from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from macaronys_backend.enums import SourceType


def detect_source_type(filename: str, mime_type: str | None) -> SourceType:
    suffix = Path(filename).suffix.lower()
    normalized_mime = (mime_type or "").lower()

    if suffix == ".pdf" or normalized_mime == "application/pdf":
        return SourceType.pdf
    if suffix in {".txt", ".md", ".csv", ".log"} or normalized_mime.startswith("text/"):
        return SourceType.txt

    raise HTTPException(
        status_code=415,
        detail="Only PDF and text-like files are supported in this endpoint",
    )


def extract_text_from_file(path: Path, source_type: SourceType) -> str:
    if source_type == SourceType.pdf:
        return extract_pdf_text(path)
    if source_type == SourceType.txt:
        return extract_plain_text(path)
    raise HTTPException(status_code=415, detail=f"Unsupported source type: {source_type}")


def extract_plain_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_pdf_text(path: Path) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="PyMuPDF is not installed; install pymupdf to parse PDFs",
        ) from exc

    parts: list[str] = []
    try:
        with fitz.open(path) as document:
            for index, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                if text:
                    parts.append(f"[page {index}]\n{text}")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {exc}") from exc

    extracted = "\n\n".join(parts).strip()
    if not extracted:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in PDF; OCR support will be added separately",
        )
    return extracted
