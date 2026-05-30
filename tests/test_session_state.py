"""src/utils/session_state.py 테스트."""
import pytest


class TestInit:
    def test_sets_default_lang(self, mock_streamlit_session):
        from src.utils.session_state import init
        init()
        assert mock_streamlit_session.get("lang") in ("ko", "en")

    def test_sets_default_theme(self, mock_streamlit_session):
        from src.utils.session_state import init
        init()
        assert mock_streamlit_session.get("theme") == "light"

    def test_does_not_overwrite_existing_values(self, mock_streamlit_session):
        mock_streamlit_session["lang"] = "en"
        from src.utils.session_state import init
        init()
        assert mock_streamlit_session["lang"] == "en"  # 덮어쓰지 않음

    def test_initializes_lists_as_copies(self, mock_streamlit_session):
        """리스트 기본값이 참조 공유가 아닌 복사본이어야 한다."""
        from src.utils.session_state import init, _DEFAULTS
        init()
        # 세션 리스트를 수정해도 _DEFAULTS에 영향 없어야 함
        mock_streamlit_session["chat_messages"].append("test")
        assert _DEFAULTS["chat_messages"] == []


class TestGetAndSetVal:
    def test_get_returns_set_value(self, mock_streamlit_session):
        from src.utils.session_state import get, set_val
        set_val("test_key", "test_value")
        assert get("test_key") == "test_value"

    def test_get_missing_key_returns_none(self, mock_streamlit_session):
        from src.utils.session_state import get
        result = get("nonexistent_key_xyz")
        assert result is None

    def test_set_val_overwrites(self, mock_streamlit_session):
        from src.utils.session_state import set_val, get
        set_val("lang", "ko")
        set_val("lang", "en")
        assert get("lang") == "en"


class TestAddToHistory:
    def test_adds_item_to_history(self, mock_streamlit_session):
        from src.utils.session_state import init, add_to_history, get
        init()
        add_to_history("test.pdf", "## 요약 내용", "간결 요약")
        history = get("summary_history")
        assert len(history) == 1
        assert history[0]["source"] == "test.pdf"
        assert history[0]["summary"] == "## 요약 내용"
        assert history[0]["style"] == "간결 요약"

    def test_most_recent_item_is_first(self, mock_streamlit_session):
        from src.utils.session_state import init, add_to_history, get
        init()
        add_to_history("file1.pdf", "요약1", "간결")
        add_to_history("file2.pdf", "요약2", "상세")
        history = get("summary_history")
        assert history[0]["source"] == "file2.pdf"

    def test_history_capped_at_20(self, mock_streamlit_session):
        from src.utils.session_state import init, add_to_history, get
        init()
        for i in range(25):
            add_to_history(f"file{i}.pdf", f"요약{i}", "간결")
        history = get("summary_history")
        assert len(history) == 20
