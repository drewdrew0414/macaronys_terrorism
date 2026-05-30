"""
Gemma 모델 목록과 VRAM 기반 자동 선택 로직.
설치된 Ollama 모델 전체를 동적으로 가져오는 함수도 제공한다.
"""
import subprocess
from functools import lru_cache

# UI 드롭다운에서 수동 선택 가능한 Gemma 모델 목록
GEMMA_MODELS = ["gemma3:1b", "gemma3:4b", "gemma3:12b", "gemma3:27b"]

# (최소 VRAM GB, 권장 모델) — 내림차순 정렬 필수
_THRESHOLDS = [
    (20.0, "gemma3:12b"),
    (8.0,  "gemma3:4b"),
    (0.0,  "gemma3:1b"),
]


def model_for_vram(vram_gb: float) -> str:
    """VRAM 크기에 맞는 Gemma 모델 이름을 반환한다."""
    for threshold, model in _THRESHOLDS:
        if vram_gb >= threshold:
            return model
    return "gemma3:1b"


@lru_cache(maxsize=1)
def get_installed_models() -> list[str]:
    """
    현재 Ollama에 설치된 모든 모델 이름 목록을 반환한다.

    'ollama list' 출력의 헤더 행을 제외하고 첫 번째 열(모델명)만 수집한다.
    Ollama가 없거나 실행 중이지 않으면 빈 리스트를 반환한다.
    lru_cache: 세션 내 최초 1회만 호출 후 캐시 (모델 추가 시 앱 재시작 필요)
    """
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        models = []
        for line in result.stdout.strip().splitlines()[1:]:  # 헤더 제외
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except Exception:
        return []


def refresh_installed_models() -> list[str]:
    """캐시를 무효화하고 설치 모델 목록을 새로 가져온다."""
    get_installed_models.cache_clear()
    return get_installed_models()
