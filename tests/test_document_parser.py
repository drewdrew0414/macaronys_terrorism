from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from macaronys_backend.enums import SourceType
from macaronys_backend.services.document_parser import (
    detect_source_type,
    extract_plain_text,
)


def test_detect_source_type_pdf_by_extension() -> None:
    assert detect_source_type("notice.pdf", None) == SourceType.pdf


def test_detect_source_type_text_by_mime() -> None:
    assert detect_source_type("notice.data", "text/plain") == SourceType.txt


def test_detect_source_type_rejects_unsupported_file() -> None:
    with pytest.raises(HTTPException) as error:
        detect_source_type("notice.exe", "application/octet-stream")

    assert error.value.status_code == 415


def test_extract_plain_text_supports_cp949(tmp_path: Path) -> None:
    path = tmp_path / "notice.txt"
    path.write_bytes("수행평가 제출".encode("cp949"))

    assert extract_plain_text(path) == "수행평가 제출"
