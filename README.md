```
macarony's_terrorism/
├── app.py                          # Streamlit 진입점, 페이지 라우팅
├── requirements.txt                # 패키지 의존성
├── .env                            # 환경변수 템플릿 (OLLAMA_HOST 등)
│
├── config/
│   ├── settings.py                 # 앱 전역 설정 (포트, timeout, 청크크기 등)
│   └── models.py                   # 지원 모델 목록 (llama3, gemma2:2b, qwen2.5:3b)
│
├── src/
│   ├── core/
│   │   ├── pdf_parser.py           # pdfplumber 텍스트 추출, 페이지별 청킹
│   │   ├── ollama_client.py        # Ollama REST API 호출, 스트리밍 응답
│   │   ├── prompt_builder.py       # 텍스트 + 프롬프트 템플릿 조합
│   │   └── response_parser.py      # 마크다운 응답 → 요약/퀴즈 구조체 파싱
│   │
│   ├── ui/
│   │   ├── upload_view.py          # PDF 업로드 + 파일 정보 표시
│   │   ├── summary_view.py         # 요약 결과 마크다운 렌더링
│   │   ├── quiz_view.py            # 4지선다 라디오버튼 + 채점 로직
│   │   └── sidebar.py              # GPU/NPU 상태, 모델 선택 위젯
│   │
│   └── utils/
│       ├── system_monitor.py       # GPU/NPU/RAM 사용량 수집 (psutil, GPUtil)
│       ├── text_cleaner.py         # PDF 추출 텍스트 노이즈 제거
│       └── session_state.py        # Streamlit session_state 초기화·관리
│
├── prompts/
│   ├── summary_prompt.txt          # 요약 프롬프트 (형식, 길이, 언어 지시)
│   └── quiz_prompt.txt             # 퀴즈 프롬프트 (4지선다 + 정답 + 해설 형식)
│
├── assets/
│   └── css/
│       └── custom.css              # Streamlit 커스텀 스타일
│
└── tests/
    ├── test_pdf_parser.py          # PDF 파싱 단위 테스트
    ├── test_ollama_client.py       # Ollama 연결·응답 테스트
    └── test_response_parser.py     # 마크다운 파싱 정확도 테스트

```