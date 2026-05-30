"""
공유 픽스처 및 테스트 설정.

Streamlit session_state 의존성을 모킹하고,
테스트용 샘플 데이터(PDF bytes, 텍스트, 메시지 등)를 제공한다.
"""
import io
import pytest


# ── Streamlit 모킹 ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_streamlit_session(monkeypatch):
    """
    모든 테스트에 자동 적용.
    st.session_state를 딕셔너리로 대체해 Streamlit 없이도 실행 가능하게 한다.
    """
    import types

    fake_state = {}

    class FakeSessionState(dict):
        def __getattr__(self, key):
            return self.get(key)
        def __setattr__(self, key, value):
            self[key] = value

    fake_ss = FakeSessionState()

    import streamlit as st
    monkeypatch.setattr(st, "session_state", fake_ss)
    return fake_ss


# ── 샘플 데이터 픽스처 ────────────────────────────────────────────────────────

@pytest.fixture
def sample_text():
    return (
        "인공지능(AI)은 컴퓨터 시스템이 인간의 지능을 모방하는 기술입니다.\n"
        "머신러닝과 딥러닝이 AI의 핵심 분야이며, 자연어 처리(NLP)를 통해\n"
        "텍스트를 이해하고 생성할 수 있습니다.\n"
        "GPT, BERT, LLaMA 등 대형 언어 모델(LLM)이 최근 주목받고 있습니다."
    )


@pytest.fixture
def long_text():
    """CHUNK_SIZE를 확실히 초과하는 긴 텍스트 (설정값 기반으로 동적 생성)."""
    from config.settings import CHUNK_SIZE
    base = "AI 기술은 컴퓨터 시스템이 인간의 지능을 모방하는 혁신적인 분야입니다. "  # ~40자
    repeats = (CHUNK_SIZE // len(base)) + 10
    return base * repeats


@pytest.fixture
def sample_pdf_bytes():
    """실제 최소 PDF 바이너리 (텍스트 1줄 포함)."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 << /Type /Font "
        b"/Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\n"
        b"BT /F1 12 Tf 100 700 Td (Hello World) Tj ET\n"
        b"endstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \n0000000266 00000 n \n"
        b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n358\n%%EOF"
    )


@pytest.fixture
def sample_messages():
    return [
        {"role": "system",    "content": "당신은 요약 전문가입니다."},
        {"role": "user",      "content": "다음 텍스트를 요약해줘."},
    ]


@pytest.fixture
def mock_ollama_response():
    """ollama.chat()의 정상 응답 구조를 흉내낸다."""
    return {"message": {"content": "## 요약\n- 핵심 내용 1\n- 핵심 내용 2"}}


@pytest.fixture
def pdfplumber_table():
    """pdfplumber extract_tables() 반환 형식의 샘플 표."""
    return [
        ["이름", "점수", "등급"],
        ["김철수", "95",  "A"],
        ["이영희", "82",  "B"],
        [None,    "77",  "C"],
    ]
