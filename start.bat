@echo off
chcp 65001 >/dev/null
setlocal EnableDelayedExpansion

echo.
echo =================================================
echo    입력 도구 - 자동 설치 및 실행 스크립트
echo =================================================
echo.

:: ── 작업 디렉토리 ─────────────────────────────────────────────────────────────
cd /d "%~dp0"

:: ── Python 확인 ───────────────────────────────────────────────────────────────
python --version >/dev/null 2>&1
if errorlevel 1 (
    echo [ERROR] Python이 설치되어 있지 않습니다.
    echo         https://www.python.org 에서 3.9 이상 버전을 설치하세요.
    start https://www.python.org/downloads/
    pause & exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK]    Python %PY_VER%

:: ── 가상환경 ──────────────────────────────────────────────────────────────────
if not exist ".venv\" (
    echo [INFO]  가상환경 생성 중...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [OK]    가상환경 활성화

:: ── 라이브러리 설치 ───────────────────────────────────────────────────────────
echo [INFO]  라이브러리 설치 중...
pip install -r requirements.txt -q --progress-bar off
echo [OK]    라이브러리 설치 완료

:: ── Ollama 확인 ───────────────────────────────────────────────────────────────
ollama --version >/dev/null 2>&1
if errorlevel 1 (
    echo [WARN]  Ollama가 설치되어 있지 않습니다.
    echo         아래 링크에서 설치 후 다시 실행하세요:
    echo         https://ollama.com/download/windows
    start https://ollama.com/download/windows
    pause & exit /b 1
)
echo [OK]    Ollama 설치됨

:: ── 메모리 감지 & 모델 선택 ───────────────────────────────────────────────────
for /f %%m in ('powershell -NoProfile -Command "[int]((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB)"') do set MEM_GB=%%m

if !MEM_GB! GEQ 20 (
    set MODEL=gemma3:12b
) else if !MEM_GB! GEQ 8 (
    set MODEL=gemma3:4b
) else (
    set MODEL=gemma3:1b
)
echo [INFO]  메모리: !MEM_GB!GB -^> 모델: !MODEL!

:: ── 모델 다운로드 ─────────────────────────────────────────────────────────────
ollama list 2>/dev/null | findstr /C:"!MODEL!" >/dev/null 2>&1
if errorlevel 1 (
    echo [INFO]  !MODEL! 다운로드 중... (처음 실행 시 시간이 걸립니다)
    ollama pull !MODEL!
    echo [OK]    !MODEL! 다운로드 완료
) else (
    echo [OK]    모델 이미 설치됨: !MODEL!
)

:: ── 앱 실행 ───────────────────────────────────────────────────────────────────
echo.
echo [OK]    앱을 시작합니다 -^> http://localhost:8501
echo.
streamlit run app.py
pause
