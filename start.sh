#!/usr/bin/env bash
set -euo pipefail

# ── 색상 ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

echo ""
echo "================================================="
echo "   입력 도구 — 자동 설치 및 실행 스크립트"
echo "================================================="
echo ""

# ── 작업 디렉토리 ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OS="$(uname -s)"   # Darwin | Linux

# ── Python 확인 ───────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER="$($cmd -c 'import sys; print(sys.version_info >= (3,9))')"
        if [[ "$VER" == "True" ]]; then
            PYTHON="$cmd"
            break
        fi
    fi
done
[[ -z "$PYTHON" ]] && error "Python 3.9 이상이 필요합니다.\nhttps://www.python.org 에서 설치하세요."
success "Python: $($PYTHON --version)"

# ── 가상환경 ──────────────────────────────────────────────────────────────────
if [[ ! -d ".venv" ]]; then
    info "가상환경 생성 중..."
    $PYTHON -m venv .venv
fi
source .venv/bin/activate
success "가상환경 활성화"

# ── 라이브러리 설치 ───────────────────────────────────────────────────────────
info "라이브러리 설치 중 (requirements.txt)..."
pip install -r requirements.txt -q --progress-bar off
success "라이브러리 설치 완료"

# ── Ollama 설치 확인 ──────────────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    warn "Ollama가 설치되어 있지 않습니다."
    if [[ "$OS" == "Darwin" ]]; then
        if command -v brew &>/dev/null; then
            info "Homebrew로 Ollama 설치 중..."
            brew install ollama
        else
            warn "Homebrew가 없습니다. 아래 링크에서 직접 설치하세요:"
            echo "  https://ollama.com/download/mac"
            open "https://ollama.com/download/mac" 2>/dev/null || true
            error "Ollama 설치 후 다시 실행하세요."
        fi
    elif [[ "$OS" == "Linux" ]]; then
        info "Ollama 설치 중..."
        curl -fsSL https://ollama.com/install.sh | sh
    else
        error "지원하지 않는 OS입니다. https://ollama.com 에서 설치하세요."
    fi
fi
success "Ollama: $(ollama --version 2>/dev/null | head -1)"

# ── Ollama 서버 시작 ──────────────────────────────────────────────────────────
if ! ollama list &>/dev/null; then
    info "Ollama 서버 시작 중..."
    if [[ "$OS" == "Darwin" ]]; then
        open -a Ollama 2>/dev/null || ollama serve &>/dev/null &
    else
        ollama serve &>/dev/null &
    fi
    sleep 3
fi

# ── 메모리 감지 & 모델 선택 ───────────────────────────────────────────────────
if [[ "$OS" == "Darwin" ]]; then
    MEM_BYTES="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
    MEM_GB=$(( MEM_BYTES / 1024 / 1024 / 1024 ))
else
    MEM_KB="$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)"
    MEM_GB=$(( MEM_KB / 1024 / 1024 ))
fi

if   (( MEM_GB >= 20 )); then MODEL="gemma3:12b"
elif (( MEM_GB >= 8  )); then MODEL="gemma3:4b"
else                           MODEL="gemma3:1b"
fi

info "메모리: ${MEM_GB}GB → 모델: ${MODEL}"

# ── 모델 다운로드 (없을 때만) ─────────────────────────────────────────────────
if ollama list 2>/dev/null | awk 'NR>1{print $1}' | grep -q "^${MODEL}$"; then
    success "모델 이미 설치됨: ${MODEL}"
else
    info "${MODEL} 다운로드 중... (처음 실행 시 시간이 걸립니다)"
    ollama pull "$MODEL"
    success "${MODEL} 다운로드 완료"
fi

# ── 앱 실행 ───────────────────────────────────────────────────────────────────
echo ""
success "앱을 시작합니다 → http://localhost:8501"
echo ""
streamlit run app.py
