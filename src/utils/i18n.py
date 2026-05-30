"""
다국어 지원 — 한국어(ko) / English(en).

사용법:
    from src.utils.i18n import t
    st.button(t("btn_download"))
    st.caption(t("file_extracted", n=1234))
"""
import streamlit as st

# ── 이용약관 텍스트 ───────────────────────────────────────────────────────────

TERMS_KO = """
## 이용약관

**최종 업데이트: 2026년 5월 30일**

---

### 1. 서비스 개요

본 앱은 **로컬 환경**에서 실행되는 AI 기반 문서 요약 도구입니다.  
모든 처리는 사용자의 기기에서 이루어지며, 외부 서버로 어떠한 데이터도 전송되지 않습니다.

---

### 2. 오픈소스 소프트웨어 고지

본 앱은 아래 오픈소스 소프트웨어를 사용합니다:

| 소프트웨어 | 라이선스 |
|---|---|
| Ollama | MIT License |
| Google Gemma | Gemma Terms of Use |
| Streamlit | Apache 2.0 |
| faster-whisper | MIT License |

---

### 3. Google Gemma 모델 이용 약관

Gemma 모델을 다운로드하고 사용함으로써 귀하는 **Google의 Gemma Terms of Use**에 동의하게 됩니다.

- Gemma 모델은 상업적 목적을 포함하여 무료로 사용할 수 있습니다.
- 단, Google이 정한 허용 정책(Acceptable Use Policy)을 준수해야 합니다.
- 모델을 이용하여 타인에게 해를 끼치거나 불법적인 콘텐츠를 생성하는 것은 금지됩니다.

---

### 4. 데이터 처리 및 개인정보 보호

- **파일 업로드**: 업로드된 파일은 로컬에서만 처리되며 저장되지 않습니다.
- **음성 녹음**: 녹음 데이터는 기기 내에서만 변환(Whisper)되며 외부로 전송되지 않습니다.
- **URL 콘텐츠**: 웹 페이지 내용은 로컬에서 처리됩니다.

---

### 5. 면책 조항

본 앱은 **"있는 그대로(AS IS)"** 제공됩니다.  
개발자는 앱 사용으로 인한 직·간접적 손해에 대해 어떠한 책임도 지지 않습니다.  
AI 요약 결과의 정확성을 보장하지 않으며, 중요한 결정에 앞서 원문을 직접 확인하세요.

---

### 6. 사용 제한

다음의 목적으로 본 앱을 사용하는 것은 금지됩니다:
- 불법적이거나 유해한 콘텐츠 생성
- 타인의 개인정보 침해
- 저작권 침해

---

**아래 버튼을 클릭함으로써 위 이용약관 전체에 동의하는 것으로 간주됩니다.**
"""

TERMS_EN = """
## Terms of Service

**Last updated: May 30, 2026**

---

### 1. Overview

This application is a **locally-running** AI document summarization tool.  
All processing occurs on your device. No data is transmitted to external servers.

---

### 2. Open Source Software Notice

This app uses the following open source software:

| Software | License |
|---|---|
| Ollama | MIT License |
| Google Gemma | Gemma Terms of Use |
| Streamlit | Apache 2.0 |
| faster-whisper | MIT License |

---

### 3. Google Gemma Model Terms

By downloading and using Gemma models, you agree to **Google's Gemma Terms of Use**.

- Gemma models are free to use, including for commercial purposes.
- You must comply with Google's Acceptable Use Policy.
- Generating harmful or illegal content using the model is prohibited.

---

### 4. Data Processing & Privacy

- **File uploads**: Files are processed locally only and are not stored.
- **Voice recordings**: Audio is transcribed on-device (Whisper) and never sent externally.
- **URL content**: Web page content is processed locally.

---

### 5. Disclaimer

This app is provided **"AS IS"** without warranty of any kind.  
The developers are not liable for any direct or indirect damages arising from use of this app.  
AI summaries may not be accurate — always verify important information against the source.

---

### 6. Prohibited Uses

You may not use this app to:
- Generate illegal or harmful content
- Violate others' privacy
- Infringe on copyrights

---

**By clicking the button below, you agree to all of the above terms.**
"""

# ── 번역 사전 ─────────────────────────────────────────────────────────────────

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ko": {
        # 앱
        "app_title":          "입력 도구",
        "app_subtitle":       "파일 업로드 · 음성 녹음 · URL — Ollama Gemma 요약",
        "tab_file":           "  파일 업로드  ",
        "tab_audio":          "  음성 녹음  ",
        "tab_url":            "  사이트 URL  ",

        # 사이드바 — 언어
        "lang_label":         "언어 / Language",

        # 사이드바 — 모델
        "sidebar_model":      "모델 설정",
        "metric_os":          "OS",
        "metric_memory":      "메모리",
        "model_select":       "Gemma 모델",
        "model_auto":         "자동 선택",
        "model_auto_caption": "자동 선택 결과: `{model}`",
        "model_installed":    "`{model}` 설치됨",
        "model_not_installed":"`{model}` 미설치",
        "btn_download":       "모델 다운로드",
        "download_status":    "{model} 다운로드 중...",
        "download_complete":  "`{model}` 다운로드 완료",
        "download_failed":    "다운로드 실패",
        "ollama_not_found":   "Ollama가 설치되어 있지 않습니다.\n`start.sh` 또는 `start.bat`를 실행하세요.",
        "ollama_error":       "Ollama 연결 오류: {err}",

        # 사이드바 — 프롬프트
        "sidebar_prompt":         "시스템 프롬프트",
        "sidebar_prompt_caption": "AI 역할을 사전 설정합니다 — Chat API의 `system` role로 주입됩니다.",
        "preset_label":           "프리셋",
        "prompt_placeholder":     "AI의 역할과 응답 방식을 입력하세요...",
        "prompt_char_count":      "{n}자",

        # 테마 토글
        "theme_toggle":       "다크 모드",

        # 이용약관
        "terms_title":   "이용약관",
        "terms_scroll":  "아래 약관을 끝까지 읽고 동의 여부를 선택하세요.",
        "terms_accept":  "동의하고 설치",
        "terms_decline": "취소",
        "terms_text":    TERMS_KO,

        # 파일 업로드
        "file_upload_hint":  "파일을 끌어다 놓거나 클릭해서 선택하세요",
        "file_upload_empty": "PDF · TXT · 이미지 · 오디오 파일을 업로드하세요",
        "file_preview_pdf":  "PDF 텍스트 미리보기",
        "file_preview_txt":  "텍스트 미리보기",
        "file_extracted":    "총 {n:,}자 추출됨",
        "file_size":         "{kb:.1f} KB",
        "btn_summarize":     "요약하기",

        # 음성 녹음
        "audio_hint":         "마이크 버튼을 눌러 녹음을 시작 / 종료하세요",
        "btn_dl_wav":         "다운로드",
        "btn_transcribe":     "Whisper로 텍스트 변환",
        "transcribe_spinner": "Whisper 변환 중...",
        "transcribe_ok":      "변환 완료",
        "transcribe_fail":    "변환 실패: {err}",
        "audio_result":       "변환 결과",
        "btn_sum_audio":      "변환된 텍스트 요약하기",

        # URL
        "url_placeholder": "https://example.com",
        "url_empty":       "웹 페이지 URL을 붙여넣으세요",
        "url_invalid":     "올바른 URL을 입력하세요 (https:// 또는 http://로 시작)",
        "btn_fetch":       "내용 가져오기",
        "fetch_spinner":   "페이지 불러오는 중...",
        "fetch_empty":     "텍스트를 추출할 수 없는 페이지입니다.",
        "fetch_ok":        "추출 완료 — {n:,}자",
        "fetch_error":     "오류: {err}",
        "url_expander":    "추출된 텍스트",
        "btn_sum_url":     "페이지 내용 요약하기",

        # 요약 결과
        "summary_title":   "### 요약 결과",
        "tab_preview":     "미리보기",
        "tab_copy":        "텍스트 복사",
        "copy_hint":       "오른쪽 상단 복사 버튼을 클릭하세요.",
        "sum_spinner":     "{model} 요약 중...",
        "sum_fail":        "**요약 실패** — Ollama가 실행 중인지, 모델이 설치되어 있는지 확인하세요.\n\n오류: `{err}`",

        # 요약 프롬프트 (AI에게 전달)
        "sum_prompt": (
            "다음 텍스트를 한국어로 요약해줘.\n"
            "반드시 마크다운 형식으로: ## 제목, ### 소제목, **강조**, - 항목을 적극 활용해서 가독성 높게 구성해.\n"
            "불필요한 서론 없이 바로 요약 결과만 출력해.\n\n{text}"
        ),

        # 탭
        "tab_chat":         "  AI 채팅  ",

        # 모델 (리뉴얼)
        "sidebar_installed":  "설치된 모델",
        "sidebar_no_models":  "설치된 모델 없음",
        "sidebar_recommend":  "추천 (메모리 기준): `{model}`",
        "sidebar_dl_title":   "모델 추가 다운로드",
        "sidebar_dl_select":  "다운로드할 모델 선택",
        "sidebar_refresh":    "목록 새로고침",

        # 요약 스타일
        "sum_style_label":  "요약 방식",

        # 내보내기
        "btn_export_md":    "마크다운 저장",
        "export_filename":  "summary.md",

        # 문서 통계
        "doc_stats":        "{words:,}단어 · {chars:,}자 · 약 {mins}분 읽기",

        # 청킹
        "chunk_notice":     "긴 문서 — {n}개 청크로 나눠 처리합니다",
        "chunk_progress":   "청크 {i}/{n} 처리 중...",
        "chunk_merge":      "청크 요약 병합 중...",

        # 직접 입력 탭
        "paste_label":      "텍스트 직접 입력",
        "paste_placeholder":"분석할 텍스트를 여기에 붙여넣으세요...",
        "paste_empty":      "분석할 텍스트를 입력하거나 붙여넣으세요",
        "paste_clear":      "지우기",

        # YouTube
        "youtube_detected": "YouTube 영상이 감지되었습니다.",
        "youtube_fetch":    "자막 가져오기",
        "youtube_spinner":  "YouTube 자막 불러오는 중...",
        "youtube_ok":       "자막 추출 완료 — {n:,}자",
        "youtube_fail":     "자막 가져오기 실패: {err}",

        # 채팅
        "chat_ctx_select":  "컨텍스트 선택",
        "chat_ctx_paste":   "직접 입력",
        "chat_ctx_file":    "최근 파일",
        "chat_ctx_url":     "최근 URL",
        "chat_ctx_audio":   "최근 음성",
        "chat_ctx_hint":    "분석할 텍스트를 여기에 입력하세요...",
        "chat_ctx_none":    "컨텍스트 없음 — 다른 탭에서 내용을 불러오거나 직접 입력하세요.",
        "chat_input_ph":    "질문을 입력하세요... (Shift+Enter로 줄바꿈)",
        "chat_clear":       "대화 초기화",
        "chat_no_ctx":      "컨텍스트를 먼저 입력하거나 선택하세요.",
        "chat_system_ctx":  "다음 컨텍스트를 참고해서 사용자의 질문에 답변해:\n\n{ctx}",

        # 히스토리
        "history_label":    "요약 히스토리",
        "history_empty":    "아직 저장된 요약이 없습니다.",
        "history_clear":    "히스토리 전체 삭제",
        "history_source":   "출처: {src}",
        "history_style":    "방식: {style}",
        "history_copy":     "복사",

        # 소개 페이지 — 설명
        "about_tagline":      "완전 로컬 실행 AI 분석 플랫폼",
        "about_desc":         "파일·음성·URL을 Ollama 로컬 AI로 분석합니다.\n인터넷 연결 없이, 내 PC에서만 실행 — 데이터가 외부로 절대 나가지 않습니다.",
        "about_how_title":    "사용 방법",
        "how_step1":          "① 사이드바에서 Ollama 모델을 선택하세요.",
        "how_step2":          "② 파일을 업로드하거나 URL·음성을 입력하세요.",
        "how_step3":          "③ 요약하기 버튼을 누르면 AI가 분석을 시작합니다.",

        # 소개 페이지 — 기능 카드
        "feat_docs":          "문서 분석",
        "feat_docs_desc":     "PDF·TXT를 추출하고 표(Table)도 구조적으로 인식해 AI가 정확하게 요약합니다.",
        "feat_audio":         "음성 인식",
        "feat_audio_desc":    "마이크 녹음 또는 오디오 파일을 업로드하면 Whisper가 텍스트로 변환합니다.",
        "feat_url":           "URL · YouTube",
        "feat_url_desc":      "웹 페이지 본문과 YouTube 자막을 자동 추출해 즉시 요약합니다.",
        "feat_chat":          "AI 채팅",
        "feat_chat_desc":     "문서를 컨텍스트로 삼아 AI와 멀티턴 대화를 나눌 수 있습니다.",
        "feat_local":         "완전 로컬 실행",
        "feat_local_desc":    "Ollama로 내 PC에서만 실행합니다. API 키와 인터넷이 필요 없습니다.",
        "feat_privacy":       "개인정보 보호",
        "feat_privacy_desc":  "파일·음성·URL 내용이 외부 서버로 전송되지 않습니다.",

        # 시스템 현황
        "sys_title":          "시스템 현황",
        "sys_cpu":            "CPU",
        "sys_ram":            "메모리",
        "sys_ram_avail":      "사용 가능: {n:.1f} GB",
        "sys_ram_budget":     "RAM 예산: {n:.1f} GB (여유분 60%)",
        "sys_compute":        "연산 모드",
        "sys_mode_cuda":      "NVIDIA GPU",
        "sys_mode_mps":       "Apple Silicon",
        "sys_mode_cpu":       "CPU 전용 (RAM 예산 적용)",
        "sys_safe_model":     "안전 권장 모델",

        # 환경 변수 안내
        "env_title":          "환경 설정 (.env)",
        "env_host":           "Ollama 서버",
        "env_whisper":        "Whisper 모델",

    },"en": {
        # App
        "app_title":    "Input Tool",
        "app_subtitle": "File Upload · Voice Recording · URL — Summarize with Ollama Gemma",
        "tab_file":     "  File Upload  ",
        "tab_audio":    "  Voice Recording  ",
        "tab_url":      "  Site URL  ",

        # Sidebar — language
        "lang_label": "언어 / Language",

        # Sidebar — model
        "sidebar_model":      "Model Settings",
        "metric_os":          "OS",
        "metric_memory":      "Memory",
        "model_select":       "Gemma Model",
        "model_auto":         "Auto Select",
        "model_auto_caption": "Auto selected: `{model}`",
        "model_installed":    "`{model}` installed",
        "model_not_installed":"`{model}` not installed",
        "btn_download":       "Download Model",
        "download_status":    "Downloading {model}...",
        "download_complete":  "`{model}` download complete",
        "download_failed":    "Download failed",
        "ollama_not_found":   "Ollama is not installed.\nRun `start.sh` or `start.bat`.",
        "ollama_error":       "Ollama connection error: {err}",

        # Sidebar — prompt
        "sidebar_prompt":         "System Prompt",
        "sidebar_prompt_caption": "Pre-configure AI behavior — injected as Chat API `system` role.",
        "preset_label":           "Preset",
        "prompt_placeholder":     "Describe the AI's role and response style...",
        "prompt_char_count":      "{n} chars",

        # Theme toggle
        "theme_toggle":       "Dark Mode",

        # Terms
        "terms_title":   "Terms of Service",
        "terms_scroll":  "Please read the terms carefully before proceeding.",
        "terms_accept":  "Accept & Install",
        "terms_decline": "Cancel",
        "terms_text":    TERMS_EN,

        # File upload
        "file_upload_hint":  "Drag and drop or click to browse files",
        "file_upload_empty": "Upload PDF · TXT · Image · Audio files",
        "file_preview_pdf":  "PDF Text Preview",
        "file_preview_txt":  "Text Preview",
        "file_extracted":    "{n:,} characters extracted",
        "file_size":         "{kb:.1f} KB",
        "btn_summarize":     "Summarize",

        # Audio
        "audio_hint":         "Click the microphone to start / stop recording",
        "btn_dl_wav":         "Download",
        "btn_transcribe":     "Transcribe with Whisper",
        "transcribe_spinner": "Transcribing with Whisper...",
        "transcribe_ok":      "Transcription complete",
        "transcribe_fail":    "Transcription failed: {err}",
        "audio_result":       "Transcription Result",
        "btn_sum_audio":      "Summarize Transcription",

        # URL
        "url_placeholder": "https://example.com",
        "url_empty":       "Paste a web page URL here",
        "url_invalid":     "Enter a valid URL (starting with https:// or http://)",
        "btn_fetch":       "Fetch Content",
        "fetch_spinner":   "Loading page...",
        "fetch_empty":     "Could not extract text from this page.",
        "fetch_ok":        "Extracted {n:,} characters",
        "fetch_error":     "Error: {err}",
        "url_expander":    "Extracted Text",
        "btn_sum_url":     "Summarize Page",

        # Summary
        "summary_title": "### Summary",
        "tab_preview":   "Preview",
        "tab_copy":      "Copy Text",
        "copy_hint":     "Click the copy button in the top-right corner.",
        "sum_spinner":   "{model} summarizing...",
        "sum_fail":      "**Summarization failed** — Check that Ollama is running and the model is installed.\n\nError: `{err}`",

        # Summary prompt (sent to AI)
        "sum_prompt": (
            "Please summarize the following text.\n"
            "Use markdown format: ## headings, ### subheadings, **bold**, and - bullet points for clarity.\n"
            "Output the summary directly without any preamble.\n\n{text}"
        ),
        # Tab
        "tab_chat":         "  AI Chat  ",

        # Model (redesign)
        "sidebar_installed":  "Installed Models",
        "sidebar_no_models":  "No models installed",
        "sidebar_recommend":  "Recommended (by memory): `{model}`",
        "sidebar_dl_title":   "Download New Model",
        "sidebar_dl_select":  "Select model to download",
        "sidebar_refresh":    "Refresh list",

        # Summary style
        "sum_style_label":  "Summary Style",

        # Export
        "btn_export_md":    "Save as Markdown",
        "export_filename":  "summary.md",

        # Document stats
        "doc_stats":        "{words:,} words · {chars:,} chars · ~{mins} min read",

        # Chunking
        "chunk_notice":     "Long document — processing in {n} chunks",
        "chunk_progress":   "Processing chunk {i}/{n}...",
        "chunk_merge":      "Merging chunk summaries...",

        # Paste tab
        "paste_label":      "Paste Text",
        "paste_placeholder":"Paste text to analyze here...",
        "paste_empty":      "Enter or paste text to analyze",
        "paste_clear":      "Clear",

        # YouTube
        "youtube_detected": "YouTube video detected.",
        "youtube_fetch":    "Get Transcript",
        "youtube_spinner":  "Fetching YouTube transcript...",
        "youtube_ok":       "Transcript extracted — {n:,} chars",
        "youtube_fail":     "Failed to get transcript: {err}",

        # Chat
        "chat_ctx_select":  "Select context",
        "chat_ctx_paste":   "Type / Paste",
        "chat_ctx_file":    "Recent File",
        "chat_ctx_url":     "Recent URL",
        "chat_ctx_audio":   "Recent Audio",
        "chat_ctx_hint":    "Enter text to use as context...",
        "chat_ctx_none":    "No context — load content from another tab or type here.",
        "chat_input_ph":    "Ask a question... (Shift+Enter for newline)",
        "chat_clear":       "Clear Chat",
        "chat_no_ctx":      "Please enter or select a context first.",
        "chat_system_ctx":  "Answer the user\'s questions based on the following context:\n\n{ctx}",

        # History
        "history_label":    "Summary History",
        "history_empty":    "No summaries saved yet.",
        "history_clear":    "Clear All History",
        "history_source":   "Source: {src}",
        "history_style":    "Style: {style}",
        "history_copy":     "Copy",

        # About page
        "about_tagline":      "Fully Local AI Analysis Platform",
        "about_desc":         "Analyze files, audio, and URLs with Ollama AI.\nRuns entirely on your PC — no internet required, no data leaves your machine.",
        "about_how_title":    "How to Use",
        "how_step1":          "① Select an Ollama model in the sidebar.",
        "how_step2":          "② Upload a file, enter a URL, or record audio.",
        "how_step3":          "③ Click Summarize and the AI will analyze the content.",

        # Feature cards
        "feat_docs":          "Document Analysis",
        "feat_docs_desc":     "Extracts text from PDF and TXT files, including structured table data, for accurate AI summarization.",
        "feat_audio":         "Voice Recognition",
        "feat_audio_desc":    "Record with your microphone or upload an audio file — Whisper converts it to text.",
        "feat_url":           "URL · YouTube",
        "feat_url_desc":      "Automatically extracts web page content and YouTube subtitles for instant summarization.",
        "feat_chat":          "AI Chat",
        "feat_chat_desc":     "Use any document as context and have a multi-turn conversation with the AI.",
        "feat_local":         "Fully Local",
        "feat_local_desc":    "Runs entirely via Ollama on your PC. No API keys or internet connection required.",
        "feat_privacy":       "Privacy Protected",
        "feat_privacy_desc":  "Files, audio, and URL content never leave your machine.",

        # System status
        "sys_title":          "System Status",
        "sys_cpu":            "CPU",
        "sys_ram":            "Memory",
        "sys_ram_avail":      "Available: {n:.1f} GB",
        "sys_ram_budget":     "RAM budget: {n:.1f} GB (60% of free)",
        "sys_compute":        "Compute Mode",
        "sys_mode_cuda":      "NVIDIA GPU",
        "sys_mode_mps":       "Apple Silicon",
        "sys_mode_cpu":       "CPU only (RAM budget applied)",
        "sys_safe_model":     "Recommended Model",

        # Environment config
        "env_title":          "Configuration (.env)",
        "env_host":           "Ollama Server",
        "env_whisper":        "Whisper Model",

    },
}

def t(key: str, **kwargs) -> str:
    """현재 선택된 언어로 번역된 문자열을 반환한다."""
    try:
        import streamlit as st
        lang = st.session_state.get("lang", "ko")
    except Exception:
        lang = "ko"
    text = TRANSLATIONS.get(lang, TRANSLATIONS["ko"]).get(key, key)
    return text.format(**kwargs) if kwargs else text
