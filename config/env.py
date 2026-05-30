"""
환경 변수 로더 — Zero-Configuration Security.

.env 파일에서 민감한 설정값을 읽어 소스코드에 직접 노출하지 않는다.
.env 파일이 없어도 기본값으로 정상 실행된다.

사용 예:
    from config.env import OLLAMA_HOST, WHISPER_MODEL
"""
from pathlib import Path
from dotenv import load_dotenv
import os

# 프로젝트 루트의 .env 파일 로드 (없으면 조용히 넘어감, override=False → 이미 설정된 환경변수 유지)
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env", override=False)

# Ollama 서버 주소 — 원격 Ollama 서버를 쓸 때 변경 (기본: 로컬)
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Whisper 모델 크기 — tiny | base | small | medium | large
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")

# 내보내기 저장 경로 (현재 미사용, 추후 자동 저장 기능 확장 시 사용)
EXPORT_DIR: str = os.getenv("EXPORT_DIR", "./exports")

# YouTube Data API 키 (선택사항 — 없으면 무료 자막 API 사용)
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
