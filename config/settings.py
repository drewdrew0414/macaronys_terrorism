"""
앱 전역 설정.

수치 상수, 기본값, 시스템 프롬프트 프리셋, 요약 스타일,
다운로드 제안 모델 목록을 정의한다.
"""

# ── 앱 기본 정보 ──────────────────────────────────────────────────────────────
APP_TITLE    = "입력 도구"
DEFAULT_LANG = "ko"           # "ko" | "en"

# ── 텍스트 처리 제한 ──────────────────────────────────────────────────────────
MAX_PREVIEW_CHARS = 5000      # UI 미리보기 최대 글자 수
MAX_PROMPT_CHARS  = 5000      # 단일 청크 최대 글자 수
CHUNK_SIZE        = 4500      # 긴 문서 청킹 단위 (청크 간 문맥 여유 포함)
WHISPER_MODEL     = "base"    # tiny | base | small | medium | large

# ── 요약 스타일 ───────────────────────────────────────────────────────────────
# 각 스타일은 user 메시지의 지시 부분을 교체해 다른 출력을 유도한다.
SUMMARY_STYLES: dict[str, dict[str, str]] = {
    "ko": {
        "간결 요약":     "핵심 내용을 3~5문장으로 간결하게 요약해. ## 제목으로 시작하는 마크다운 형식으로 작성해.",
        "상세 분석":     "## 개요, ## 주요 내용, ## 결론 섹션으로 나눠 구조적으로 분석해. 마크다운 형식으로 작성해.",
        "핵심만 (TL;DR)":"TL;DR: 으로 시작해서 1~2문장으로만 핵심을 요약해.",
        "항목별 정리":   "주요 포인트를 - 항목 형식의 마크다운 목록으로 정리해. 최소 5개 이상 항목을 뽑아줘.",
    },
    "en": {
        "Concise":       "Summarize in 3-5 concise sentences. Use a ## heading in markdown.",
        "Detailed":      "Provide a structured analysis with ## Overview, ## Key Points, ## Conclusion sections in markdown.",
        "TL;DR":         "Start with 'TL;DR:' and summarize in 1-2 sentences only.",
        "Bullet Points": "List the key points as markdown - bullet items. Provide at least 5 items.",
    },
}

def get_default_style(lang: str = "ko") -> str:
    return "Concise" if lang == "en" else "간결 요약"

def get_styles(lang: str = "ko") -> dict[str, str]:
    return SUMMARY_STYLES.get(lang, SUMMARY_STYLES["ko"])

# ── 시스템 프롬프트 프리셋 ────────────────────────────────────────────────────
SYSTEM_PROMPT_PRESETS: dict[str, dict[str, str]] = {
    "ko": {
        "요약 전문가":   "당신은 텍스트 요약 전문가입니다.\n핵심 내용만 간결하고 명확하게 한국어로 요약하세요.\n불필요한 서론 없이 바로 요약 결과만 출력하세요.",
        "학술 분석가":   "당신은 학술 논문 분석 전문가입니다.\n연구 목적, 방법론, 주요 결과, 결론을 구조적으로 분석하여 한국어로 정리하세요.",
        "뉴스 편집자":   "당신은 뉴스 편집 기자입니다.\n5W1H 원칙에 따라 핵심 정보를 간결하게 정리하세요.",
        "번역가":        "당신은 전문 번역가입니다.\n원문의 뉘앙스와 문체를 살려 자연스러운 한국어로 번역하세요.",
        "사실 확인자":   "당신은 팩트체커입니다.\n텍스트에서 주요 주장과 사실을 추출하고, 각 주장의 근거와 불확실한 부분을 분석하세요.",
        "사용자 지정":   "",
    },
    "en": {
        "Summarizer":    "You are an expert text summarizer.\nSummarize the key points concisely and clearly.\nOutput the summary directly without any preamble.",
        "Academic":      "You are an academic paper analyst.\nAnalyze: research objectives, methodology, key results, and conclusions in a structured format.",
        "News Editor":   "You are a news editor.\nOrganize key information following the 5W1H principle.",
        "Translator":    "You are a professional translator.\nTranslate the text naturally while preserving nuance and style.",
        "Fact Checker":  "You are a fact checker.\nExtract key claims and facts from the text, analyzing evidence and identifying uncertain statements.",
        "Custom":        "",
    },
}

# 다운로드 제안 모델 — Ollama에서 무료로 받을 수 있는 모델 목록
SUGGESTED_MODELS = [
    "gemma3:1b", "gemma3:4b", "gemma3:12b",
    "qwen2.5:3b", "qwen2.5:7b",
    "llama3.2:1b", "llama3.2:3b",
    "phi3.5",
    "mistral:7b",
]

def get_presets(lang: str = "ko") -> dict[str, str]:
    return SYSTEM_PROMPT_PRESETS.get(lang, SYSTEM_PROMPT_PRESETS["ko"])

def get_default_preset(lang: str = "ko") -> str:
    return "Summarizer" if lang == "en" else "요약 전문가"
