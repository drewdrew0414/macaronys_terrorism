"""
테마 관리 모듈.

라이트 모드와 다크 모드의 CSS를 각각 문자열로 정의하고,
현재 세션 테마에 맞는 CSS를 반환한다.

Streamlit은 config.toml로만 정적 테마를 지원하므로,
런타임 전환은 <style> 태그 주입으로 구현한다.
"""

# ── 공통 기본 CSS ─────────────────────────────────────────────────────────────
# 테마와 무관하게 항상 적용되는 레이아웃·전환 스타일
_BASE = """
/* 버튼: 공통 라운딩·폰트·호버 효과 */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.18) !important;
}

/* 탭: 공통 둥근 모서리·패딩 */
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    font-weight: 500 !important;
    padding: 0.45rem 1.1rem !important;
    transition: background 0.15s ease !important;
}
.stTabs [data-baseweb="tab-list"] {
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 3px !important;
}

/* 테두리 컨테이너 (st.container(border=True)) */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* 메트릭 카드: 공통 라운딩·패딩 */
[data-testid="metric-container"] {
    border-radius: 10px !important;
    padding: 0.65rem 0.9rem !important;
}

/* Expander: 공통 라운딩 */
[data-testid="stExpander"] {
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* 코드 블록 라운딩 */
[data-testid="stCode"] > div {
    border-radius: 8px !important;
}

/* 선택박스 라운딩 */
[data-baseweb="select"] > div {
    border-radius: 8px !important;
}

/* 텍스트 입력 라운딩 */
[data-testid="stTextInput"] > div > div {
    border-radius: 8px !important;
}
textarea { border-radius: 8px !important; }

/* 알림 박스 공통 라운딩 */
[data-testid="stSuccess"],
[data-testid="stWarning"],
[data-testid="stError"],
[data-testid="stInfo"] {
    border-radius: 10px !important;
}

/* 구분선 마진 */
hr { margin: 0.75rem 0 !important; }
"""

# ── 라이트 모드 CSS ───────────────────────────────────────────────────────────
_LIGHT = """
/* === 배경 === */
[data-testid="stAppViewContainer"] { background: #f8fafc !important; }
[data-testid="stMain"]             { background: #f8fafc !important; }
[data-testid="stSidebar"]          { background: #ffffff !important;
                                     border-right: 1px solid #e2e8f0 !important; }
[data-testid="stHeader"]           { background: rgba(248,250,252,0.85) !important;
                                     backdrop-filter: blur(8px) !important;
                                     border-bottom: 1px solid #e2e8f0 !important; }

/* === 헤더 텍스트 === */
h1, h2, h3, h4 { color: #0f172a !important; font-weight: 700 !important; }
p, li          { color: #1e293b !important; }
label          { color: #374151 !important; }
[data-testid="stCaptionContainer"] p,
small          { color: #64748b !important; }

/* === 메트릭 카드 === */
[data-testid="metric-container"] {
    background: #f1f5f9 !important;
    border: 1px solid #e2e8f0 !important;
}
[data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #475569 !important; }

/* === 버튼 === */
.stButton > button[kind="primary"] {
    background: #2563eb !important;
    color: #ffffff !important;
    border: none !important;
    box-shadow: 0 1px 3px rgba(37,99,235,0.3) !important;
}
.stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
    background: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    color: #1e293b !important;
}
.stButton > button[kind="secondary"]:hover,
.stButton > button:not([kind]):hover {
    background: #f1f5f9 !important;
}

/* === 탭 === */
.stTabs [data-baseweb="tab-list"]          { background: #f1f5f9 !important; }
.stTabs [aria-selected="true"]             { background: #ffffff !important;
                                             box-shadow: 0 1px 5px rgba(0,0,0,0.08) !important; }
.stTabs [data-baseweb="tab"]               { color: #64748b !important; }
.stTabs [aria-selected="true"][data-baseweb="tab"] { color: #0f172a !important; }
.stTabs [data-baseweb="tab-highlight"]     { background: #2563eb !important; }

/* === 컨테이너·카드 === */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}

/* === Expander === */
[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
}
[data-testid="stExpander"] summary { color: #374151 !important; font-weight: 500 !important; }

/* === 입력 필드 === */
[data-testid="stTextInput"] input {
    background: #ffffff !important;
    border: 1px solid #d1d5db !important;
    color: #0f172a !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 2px rgba(37,99,235,0.15) !important;
}
textarea {
    background: #ffffff !important;
    border: 1px solid #d1d5db !important;
    color: #0f172a !important;
}
textarea:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 2px rgba(37,99,235,0.15) !important;
}

/* === 선택박스 === */
[data-baseweb="select"] > div {
    background: #ffffff !important;
    border: 1px solid #d1d5db !important;
    color: #0f172a !important;
}

/* === 알림 박스 === */
[data-testid="stSuccess"] { background: #f0fdf4 !important; border: 1px solid #86efac !important; color: #15803d !important; }
[data-testid="stWarning"] { background: #fffbeb !important; border: 1px solid #fde68a !important; color: #b45309 !important; }
[data-testid="stError"]   { background: #fef2f2 !important; border: 1px solid #fecaca !important; color: #dc2626 !important; }
[data-testid="stInfo"]    { background: #eff6ff !important; border: 1px solid #bfdbfe !important; color: #1d4ed8 !important; }

/* === 코드 블록 === */
[data-testid="stCode"] > div {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
}

/* === 구분선 === */
hr { border-color: #e2e8f0 !important; }

/* === 사이드바 텍스트 === */
[data-testid="stSidebar"] p     { color: #475569 !important; }
[data-testid="stSidebar"] label { color: #374151 !important; }
[data-testid="stSidebar"] small { color: #94a3b8 !important; }

/* === 파일 업로더 === */
[data-testid="stFileUploader"] {
    background: #ffffff !important;
    border: 2px dashed #cbd5e1 !important;
    border-radius: 12px !important;
}

/* === 다이얼로그 === */
[data-testid="stDialog"] > div {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 16px !important;
    box-shadow: 0 20px 60px rgba(0,0,0,0.12) !important;
}
"""

# ── 다크 모드 CSS ─────────────────────────────────────────────────────────────
_DARK = """
/* === 배경 === */
[data-testid="stAppViewContainer"] { background: #0f172a !important; }
[data-testid="stMain"]             { background: #0f172a !important; }
[data-testid="stSidebar"]          { background: #1e293b !important;
                                     border-right: 1px solid #334155 !important; }
[data-testid="stHeader"]           { background: rgba(15,23,42,0.85) !important;
                                     backdrop-filter: blur(8px) !important;
                                     border-bottom: 1px solid #1e293b !important; }

/* === 헤더 텍스트 === */
h1, h2, h3, h4 { color: #f1f5f9 !important; font-weight: 700 !important; }
p, li          { color: #cbd5e1 !important; }
label          { color: #94a3b8 !important; }
[data-testid="stCaptionContainer"] p,
small          { color: #475569 !important; }

/* === 메트릭 카드 === */
[data-testid="metric-container"] {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
}
[data-testid="stMetricValue"] { color: #f1f5f9 !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; }

/* === 버튼 === */
.stButton > button[kind="primary"] {
    background: #2563eb !important;
    color: #ffffff !important;
    border: none !important;
    box-shadow: 0 1px 3px rgba(37,99,235,0.4) !important;
}
.stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
    background: #1e293b !important;
    border: 1px solid #475569 !important;
    color: #e2e8f0 !important;
}
.stButton > button[kind="secondary"]:hover,
.stButton > button:not([kind]):hover {
    background: #334155 !important;
}

/* === 탭 === */
.stTabs [data-baseweb="tab-list"]          { background: #1e293b !important; }
.stTabs [aria-selected="true"]             { background: #334155 !important;
                                             box-shadow: 0 1px 5px rgba(0,0,0,0.3) !important; }
.stTabs [data-baseweb="tab"]               { color: #64748b !important; }
.stTabs [aria-selected="true"][data-baseweb="tab"] { color: #f1f5f9 !important; }
.stTabs [data-baseweb="tab-highlight"]     { background: #3b82f6 !important; }

/* === 컨테이너·카드 === */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
}

/* === Expander === */
[data-testid="stExpander"] {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
}
[data-testid="stExpander"] summary { color: #cbd5e1 !important; font-weight: 500 !important; }

/* === 입력 필드 === */
[data-testid="stTextInput"] input {
    background: #1e293b !important;
    border: 1px solid #475569 !important;
    color: #f1f5f9 !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
}
textarea {
    background: #1e293b !important;
    border: 1px solid #475569 !important;
    color: #f1f5f9 !important;
}
textarea:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
}

/* === 선택박스 === */
[data-baseweb="select"] > div {
    background: #1e293b !important;
    border: 1px solid #475569 !important;
    color: #e2e8f0 !important;
}
/* 드롭다운 메뉴 배경 */
[data-baseweb="menu"]         { background: #1e293b !important; border: 1px solid #475569 !important; }
[data-baseweb="option"]       { background: #1e293b !important; color: #cbd5e1 !important; }
[data-baseweb="option"]:hover { background: #334155 !important; }

/* === 알림 박스 === */
[data-testid="stSuccess"] { background: #052e16 !important; border: 1px solid #166534 !important; color: #86efac !important; }
[data-testid="stWarning"] { background: #2d1a00 !important; border: 1px solid #92400e !important; color: #fcd34d !important; }
[data-testid="stError"]   { background: #1a0505 !important; border: 1px solid #991b1b !important; color: #fca5a5 !important; }
[data-testid="stInfo"]    { background: #0c1a2e !important; border: 1px solid #1e40af !important; color: #93c5fd !important; }

/* === 코드 블록 === */
[data-testid="stCode"] > div {
    background: #020617 !important;
    border: 1px solid #1e293b !important;
}
/* 코드 텍스트 색상 */
[data-testid="stCode"] code { color: #7dd3fc !important; }

/* === 구분선 === */
hr { border-color: #334155 !important; }

/* === 사이드바 텍스트 === */
[data-testid="stSidebar"] p     { color: #94a3b8 !important; }
[data-testid="stSidebar"] label { color: #cbd5e1 !important; }
[data-testid="stSidebar"] small { color: #475569 !important; }

/* === 파일 업로더 === */
[data-testid="stFileUploader"] {
    background: #1e293b !important;
    border: 2px dashed #475569 !important;
    border-radius: 12px !important;
}

/* === 다이얼로그 === */
[data-testid="stDialog"] > div {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 16px !important;
    box-shadow: 0 20px 60px rgba(0,0,0,0.6) !important;
}
[data-testid="stDialog"] p,
[data-testid="stDialog"] li { color: #cbd5e1 !important; }
[data-testid="stDialog"] h1,
[data-testid="stDialog"] h2,
[data-testid="stDialog"] h3 { color: #f1f5f9 !important; }

/* === 스피너 === */
[data-testid="stSpinner"] svg { color: #3b82f6 !important; }

/* === 토글 === */
[data-testid="stToggle"] label { color: #94a3b8 !important; }
"""


def get_css(theme: str) -> str:
    """
    지정한 테마의 CSS 문자열을 반환한다.

    Args:
        theme: "light" 또는 "dark"
    Returns:
        <style> 태그에 주입할 CSS 문자열
    """
    return _BASE + (_DARK if theme == "dark" else _LIGHT)
