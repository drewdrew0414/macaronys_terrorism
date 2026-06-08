from __future__ import annotations

from macaronys_backend.services.ai_result_parser import parse_ai_candidates


def test_parse_ai_candidates_accepts_plain_json_array() -> None:
    result = parse_ai_candidates(
        """
        [
          {
            "title": "역사 수행평가 보고서",
            "subject": "역사",
            "due_at": "2026-06-14T23:59:00+09:00",
            "submit_method": "클래스룸",
            "source_quote": "다음 주 금요일까지 제출",
            "confidence": 0.9
          }
        ]
        """
    )

    assert result[0]["title"] == "역사 수행평가 보고서"
    assert result[0]["confidence"] == 0.9


def test_parse_ai_candidates_extracts_array_from_extra_text() -> None:
    result = parse_ai_candidates(
        """
        결과는 다음과 같습니다.
        [{"title": "국어 독서 감상문", "confidence": 0.7}]
        """
    )

    assert result == [{"title": "국어 독서 감상문", "confidence": 0.7}]
