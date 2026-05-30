"""src/core/prompt_builder.py 테스트."""
import pytest
from src.core.prompt_builder import (
    build_messages,
    build_summary_user_message,
    build_chunk_merge_message,
    build_chat_system,
)
from config.settings import MAX_PROMPT_CHARS


class TestBuildMessages:
    def test_basic_user_message(self):
        msgs = build_messages("", "안녕하세요")
        assert msgs[-1] == {"role": "user", "content": "안녕하세요"}

    def test_system_prompt_prepended(self):
        msgs = build_messages("당신은 전문가입니다.", "질문")
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "당신은 전문가입니다."
        assert msgs[-1]["role"] == "user"

    def test_empty_system_prompt_omitted(self):
        msgs = build_messages("", "질문")
        assert all(m["role"] != "system" for m in msgs)

    def test_whitespace_system_prompt_omitted(self):
        msgs = build_messages("   ", "질문")
        assert all(m["role"] != "system" for m in msgs)

    def test_history_inserted_between_system_and_user(self):
        history = [
            {"role": "user",      "content": "이전 질문"},
            {"role": "assistant", "content": "이전 답변"},
        ]
        msgs = build_messages("시스템", "새 질문", history=history)
        roles = [m["role"] for m in msgs]
        assert roles == ["system", "user", "assistant", "user"]

    def test_text_truncated_at_max_prompt_chars(self):
        long_text = "a" * (MAX_PROMPT_CHARS + 500)
        msgs = build_messages("", long_text)
        assert len(msgs[-1]["content"]) == MAX_PROMPT_CHARS

    def test_empty_user_content_raises_value_error(self):
        with pytest.raises(ValueError):
            build_messages("시스템", "")

    def test_none_user_content_raises_value_error(self):
        with pytest.raises(ValueError):
            build_messages("시스템", None)

    def test_invalid_history_items_skipped(self):
        """role/content 키 없는 히스토리 항목은 무시한다."""
        history = [
            {"role": "user", "content": "정상"},
            {"invalid": "item"},            # 무시
            None,                           # 무시
        ]
        msgs = build_messages("sys", "질문", history=history)
        contents = [m["content"] for m in msgs]
        assert "정상" in contents
        assert None not in contents


class TestBuildSummaryUserMessage:
    def test_returns_string_with_text(self, sample_text):
        msg = build_summary_user_message(sample_text)
        assert sample_text[:100] in msg

    def test_empty_text_raises_value_error(self):
        with pytest.raises(ValueError, match="비어 있습니다"):
            build_summary_user_message("")

    def test_none_text_raises_value_error(self):
        with pytest.raises(ValueError):
            build_summary_user_message(None)

    def test_style_instruction_included_when_valid(self, sample_text):
        msg = build_summary_user_message(sample_text, style="간결 요약")
        assert "마크다운" in msg

    def test_invalid_style_falls_back_to_default(self, sample_text):
        msg = build_summary_user_message(sample_text, style="존재하지않는스타일")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_long_text_truncated(self, long_text):
        msg = build_summary_user_message(long_text)
        # 프롬프트 지시문이 추가되므로 MAX_PROMPT_CHARS보다 약간 길 수 있음
        assert long_text[:MAX_PROMPT_CHARS] in msg


class TestBuildChunkMergeMessage:
    def test_combines_chunk_summaries(self):
        summaries = ["요약 1", "요약 2", "요약 3"]
        msg = build_chunk_merge_message(summaries)
        assert "[청크 1]" in msg
        assert "[청크 2]" in msg
        assert "[청크 3]" in msg

    def test_empty_list_raises_value_error(self):
        with pytest.raises(ValueError, match="없습니다"):
            build_chunk_merge_message([])

    def test_all_empty_strings_raises_value_error(self):
        with pytest.raises(ValueError):
            build_chunk_merge_message(["", "  ", ""])

    def test_single_chunk_still_works(self):
        msg = build_chunk_merge_message(["단일 요약"])
        assert "단일 요약" in msg


class TestBuildChatSystem:
    def test_combines_system_and_context(self):
        result = build_chat_system("당신은 전문가입니다.", "이것은 컨텍스트입니다.")
        assert "당신은 전문가입니다." in result
        assert "이것은 컨텍스트입니다." in result

    def test_empty_context_returns_system_only(self):
        result = build_chat_system("시스템 프롬프트", "")
        assert result == "시스템 프롬프트"

    def test_empty_system_returns_context_only(self):
        result = build_chat_system("", "컨텍스트 내용")
        assert "컨텍스트 내용" in result
        assert result.strip() != ""

    def test_long_context_truncated(self):
        long_ctx = "c" * (MAX_PROMPT_CHARS + 1000)
        result = build_chat_system("sys", long_ctx)
        assert len(result) <= len("sys") + MAX_PROMPT_CHARS + 200  # 지시문 여유
