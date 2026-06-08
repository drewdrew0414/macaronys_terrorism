@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "MODE=all"
set "UPDATE_PYTHON=0"
set "SKIP_DEPS=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--all" set "MODE=all" & shift & goto parse_args
if /I "%~1"=="--docker" set "MODE=docker" & shift & goto parse_args
if /I "%~1"=="--api-only" set "MODE=api-only" & shift & goto parse_args
if /I "%~1"=="--local" set "MODE=local" & shift & goto parse_args
if /I "%~1"=="--worker" set "MODE=worker" & shift & goto parse_args
if /I "%~1"=="--discord-bot" set "MODE=discord-bot" & shift & goto parse_args
if /I "%~1"=="--update-python" set "UPDATE_PYTHON=1" & shift & goto parse_args
if /I "%~1"=="--skip-deps" set "SKIP_DEPS=1" & shift & goto parse_args
if /I "%~1"=="--help" goto usage
if /I "%~1"=="-h" goto usage
echo Unknown option: %~1
echo.
goto usage_error

:usage
echo Usage: start.bat [options]
echo.
echo Options:
echo   --all             Start API, Discord bot, and local AI worker. Default.
echo   --docker          Start API and Discord bot with Docker Compose.
echo   --api-only        Start only the Docker API service.
echo   --local           Run FastAPI locally after preparing .venv.
echo   --worker          Run the local AI worker after preparing .venv.
echo   --discord-bot     Run the Discord bot after preparing .venv.
echo   --update-python   Try to install/update Python through winget.
echo   --skip-deps       Skip .venv creation and pip install.
echo   --help            Show this help.
exit /b 0

:usage_error
echo Usage: start.bat [--all] [--docker] [--api-only] [--local] [--worker] [--discord-bot] [--update-python] [--skip-deps]
exit /b 2

:args_done
call :ensure_env_file
call :ensure_database_url
if errorlevel 1 exit /b 1
call :ensure_python_deps
if errorlevel 1 exit /b 1

if /I "%MODE%"=="all" (
  call :ensure_discord_bot_token
  if errorlevel 1 exit /b 1
  call :ensure_ollama
  if errorlevel 1 exit /b 1
  call :start_compose_stack
  if errorlevel 1 exit /b 1
  call :start_local_worker_background
  exit /b %ERRORLEVEL%
)

if /I "%MODE%"=="docker" (
  call :ensure_discord_bot_token
  if errorlevel 1 exit /b 1
  call :start_compose_stack
  exit /b %ERRORLEVEL%
)

if /I "%MODE%"=="api-only" (
  call :start_compose_api
  docker compose ps
  echo [macaronys] API URL: http://localhost:8000
  exit /b %ERRORLEVEL%
)

if /I "%MODE%"=="local" (
  echo [macaronys] Starting local FastAPI server with external DATABASE_URL.
  ".venv\Scripts\python.exe" app.py
  exit /b %ERRORLEVEL%
)

if /I "%MODE%"=="worker" (
  call :ensure_ollama
  if errorlevel 1 exit /b 1
  echo [macaronys] Starting local AI worker.
  ".venv\Scripts\python.exe" app.py local-worker
  exit /b %ERRORLEVEL%
)

if /I "%MODE%"=="discord-bot" (
  call :ensure_discord_bot_token
  if errorlevel 1 exit /b 1
  echo [macaronys] Starting Discord bot.
  ".venv\Scripts\python.exe" app.py discord-bot
  exit /b %ERRORLEVEL%
)

exit /b 0

:ensure_discord_bot_token
set "DISCORD_BOT_TOKEN_VALUE="
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if /I "%%A"=="DISCORD_BOT_TOKEN" set "DISCORD_BOT_TOKEN_VALUE=%%B"
)
if not defined DISCORD_BOT_TOKEN_VALUE (
  echo [macaronys] DISCORD_BOT_TOKEN is empty in .env. Add the Discord bot token before starting all Discord features.
  exit /b 1
)
exit /b 0

:ensure_env_file
if not exist ".env" if exist ".env.example" (
  copy ".env.example" ".env" >nul
  echo [macaronys] Created .env from .env.example. Edit tokens/passwords before production use.
)
exit /b 0

:ensure_database_url
if not exist ".env" (
  echo [macaronys] DATABASE_URL is required in .env because this project uses an external PostgreSQL database only.
  exit /b 1
)
findstr /B /C:"DATABASE_URL=" ".env" >nul 2>nul
if errorlevel 1 (
  echo [macaronys] DATABASE_URL is required in .env because this project uses an external PostgreSQL database only.
  exit /b 1
)
exit /b 0

:ensure_python_deps
if "%SKIP_DEPS%"=="1" (
  echo [macaronys] Skipping Python dependency setup.
  exit /b 0
)

call :ensure_python
if errorlevel 1 exit /b 1

if not exist ".venv\Scripts\python.exe" (
  echo [macaronys] Creating virtual environment.
  %PY_CMD% -m venv .venv
  if errorlevel 1 exit /b 1
)

echo [macaronys] Installing/updating Python dependencies.
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
exit /b 0

:ensure_python
if "%UPDATE_PYTHON%"=="1" call :install_python_with_winget

call :find_python
if not defined PY_CMD (
  echo [macaronys] Python 3.11+ was not found. Trying winget install.
  call :install_python_with_winget
  call :find_python
)

if not defined PY_CMD (
  echo [macaronys] Install Python 3.11+ from https://www.python.org/downloads/ and rerun this script.
  exit /b 1
)

for /f "tokens=*" %%V in ('%PY_CMD% --version 2^>^&1') do echo [macaronys] Using Python: %%V
exit /b 0

:find_python
set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3.12" & exit /b 0
  py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3.11" & exit /b 0
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3" & exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
  python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python" & exit /b 0
)
exit /b 0

:install_python_with_winget
where winget >nul 2>nul
if errorlevel 1 (
  echo [macaronys] winget is not available, so Python cannot be installed automatically.
  exit /b 1
)
echo [macaronys] Installing/updating Python through winget.
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
exit /b 0

:ensure_ollama
where ollama >nul 2>nul
if errorlevel 1 (
  where winget >nul 2>nul
  if errorlevel 1 (
    echo [macaronys] Ollama is not installed. Install it from https://ollama.com/download
    exit /b 1
  )
  set /p INSTALL_OLLAMA="Ollama is not installed. Install it with winget now? [y/N] "
  if /I "!INSTALL_OLLAMA!"=="y" (
    winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
  ) else (
    echo [macaronys] Ollama install skipped.
    exit /b 1
  )
)
ollama list >nul 2>nul
if errorlevel 1 (
  echo [macaronys] Start Ollama first, then rerun start.bat.
  exit /b 1
)
echo [macaronys] Ollama is available. Use OLLAMA_MODEL in .env to choose the model.
exit /b 0

:ensure_docker
where docker >nul 2>nul
if errorlevel 1 (
  echo [macaronys] Docker is not installed. Install Docker Desktop from https://www.docker.com/products/docker-desktop/
  exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
  echo [macaronys] Docker Desktop is not running. Trying to start it.
  if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
  )
  for /L %%I in (1,1,60) do (
    docker info >nul 2>nul
    if not errorlevel 1 goto docker_ready
    timeout /t 2 /nobreak >nul
  )
)

:docker_ready
docker info >nul 2>nul
if errorlevel 1 (
  echo [macaronys] Docker daemon is not running.
  exit /b 1
)

docker compose version >nul 2>nul
if errorlevel 1 (
  echo [macaronys] Docker Compose v2 plugin is not available.
  exit /b 1
)
exit /b 0

:compose_status
set "API_RUNNING=0"
set "DISCORD_BOT_RUNNING=0"
for /f "tokens=*" %%S in ('docker compose ps --services --status running 2^>nul') do (
  if /I "%%S"=="api" set "API_RUNNING=1"
  if /I "%%S"=="discord-bot" set "DISCORD_BOT_RUNNING=1"
)
exit /b 0

:start_compose_api
call :ensure_docker
if errorlevel 1 exit /b 1
call :compose_status
if "%API_RUNNING%"=="1" (
  echo [macaronys] Docker API is already running.
  exit /b 0
)
echo [macaronys] Starting Docker API with DATABASE_URL from .env.
docker compose up -d --build api
if errorlevel 1 exit /b 1
exit /b 0

:start_compose_discord_bot
call :ensure_docker
if errorlevel 1 exit /b 1
call :compose_status
if "%DISCORD_BOT_RUNNING%"=="1" (
  echo [macaronys] Discord bot container is already running.
  exit /b 0
)
echo [macaronys] Starting Discord bot container.
docker compose --profile bot up -d --build discord-bot
if errorlevel 1 exit /b 1
exit /b 0

:start_compose_stack
call :start_compose_api
if errorlevel 1 exit /b 1
call :start_compose_discord_bot
if errorlevel 1 exit /b 1

docker compose ps
echo [macaronys] API URL: http://localhost:8000
echo [macaronys] Docs URL: http://localhost:8000/docs
exit /b 0

:start_local_worker_background
if not exist "data\\logs" mkdir "data\\logs"
echo [macaronys] Starting local AI worker in a background window.
start "Macaronys Local AI Worker" /MIN ".venv\\Scripts\\python.exe" app.py local-worker
exit /b 0
