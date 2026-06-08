#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

MODE="all"
UPDATE_PYTHON="0"
SKIP_DEPS="0"
CHOOSE_MODEL="always"
MIN_PYTHON_MAJOR="3"
MIN_PYTHON_MINOR="11"
RUNTIME_DIR="data/runtime"
LOG_DIR="data/logs"

log() {
  printf '[macaronys] %s\n' "$1"
}

usage() {
  cat <<'EOF'
Usage: ./start.sh [options]

Options:
  --all             Start API, Discord bot, and local AI worker. Default.
  --docker          Start API and Discord bot with Docker Compose.
  --api-only        Start only the Docker API service.
  --local           Run FastAPI locally after preparing .venv.
  --worker          Run the local Ollama/Gemma AI worker in the foreground.
  --discord-bot     Run the Discord bot locally in the foreground.
  --choose-model    Show the interactive Ollama model picker.
  --update-python   Try to update/install Python with the OS package manager.
  --skip-deps       Skip .venv creation and pip install.
  --help            Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      MODE="all"
      ;;
    --docker)
      MODE="docker"
      ;;
    --api-only)
      MODE="api-only"
      ;;
    --local)
      MODE="local"
      ;;
    --worker)
      MODE="worker"
      ;;
    --discord-bot)
      MODE="discord-bot"
      ;;
    --choose-model)
      CHOOSE_MODEL="always"
      ;;
    --update-python)
      UPDATE_PYTHON="1"
      ;;
    --skip-deps)
      SKIP_DEPS="1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$1"
      usage
      exit 2
      ;;
  esac
  shift
done

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

python_version_ok() {
  "$1" - "$MIN_PYTHON_MAJOR" "$MIN_PYTHON_MINOR" <<'PY' >/dev/null 2>&1
import sys

major = int(sys.argv[1])
minor = int(sys.argv[2])
raise SystemExit(0 if sys.version_info >= (major, minor) else 1)
PY
}

find_python() {
  local candidate
  for candidate in "${PYTHON:-}" python3.13 python3.12 python3.11 python3 python; do
    if [[ -n "$candidate" ]] && have_cmd "$candidate" && python_version_ok "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

install_or_update_python() {
  local os_name
  os_name="$(uname -s)"

  if [[ "$os_name" == "Darwin" ]]; then
    if ! have_cmd brew; then
      log "Homebrew is not installed. Install it from https://brew.sh, then rerun with --update-python."
      return 1
    fi
    log "Updating Python through Homebrew."
    brew update
    brew install python@3.12 || brew upgrade python@3.12 || true
    return 0
  fi

  if [[ "$os_name" == "Linux" ]]; then
    if have_cmd apt-get; then
      log "Installing/updating Python through apt."
      sudo apt-get update
      sudo apt-get install -y python3 python3-venv python3-pip
      return 0
    fi
    if have_cmd dnf; then
      log "Installing/updating Python through dnf."
      sudo dnf install -y python3 python3-pip
      return 0
    fi
    if have_cmd yum; then
      log "Installing/updating Python through yum."
      sudo yum install -y python3 python3-pip
      return 0
    fi
    if have_cmd pacman; then
      log "Installing/updating Python through pacman."
      sudo pacman -Sy --needed python python-pip
      return 0
    fi
  fi

  log "Could not install Python automatically on this OS. Install Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ manually."
  return 1
}

ensure_python() {
  if [[ "$UPDATE_PYTHON" == "1" ]]; then
    install_or_update_python || true
  fi

  if ! PY_BIN="$(find_python)"; then
    log "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ was not found. Trying automatic install."
    install_or_update_python
    PY_BIN="$(find_python)"
  fi

  log "Using Python: $("$PY_BIN" --version 2>&1)"
}

ensure_env_file() {
  if [[ ! -f ".env" && -f ".env.example" ]]; then
    cp .env.example .env
    log "Created .env from .env.example. Edit tokens/passwords before running everything."
  fi
}

env_value() {
  local key="$1"
  if [[ ! -f ".env" ]]; then
    return 0
  fi
  grep -E "^${key}=" .env | tail -n 1 | cut -d= -f2- | sed -e "s/^['\"]//" -e "s/['\"]$//"
}

set_env_value() {
  local key="$1"
  local value="$2"
  local python_cmd="${PY_BIN:-}"
  if [[ -z "$python_cmd" ]]; then
    python_cmd="$(find_python)"
  fi
  "$python_cmd" - "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(".env")
key = sys.argv[1]
value = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
updated = False
for index, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[index] = f"{key}={value}"
        updated = True
        break
if not updated:
    lines.append(f"{key}={value}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

ensure_database_url() {
  local db_url
  db_url="$(env_value DATABASE_URL)"
  if [[ -z "$db_url" ]] || [[ "$db_url" == postgresql://USER:* ]]; then
    log "DATABASE_URL is required in .env because this project uses an external PostgreSQL database only."
    exit 1
  fi
}

ensure_discord_bot_token() {
  local token
  token="$(env_value DISCORD_BOT_TOKEN)"
  if [[ -z "$token" ]]; then
    log "DISCORD_BOT_TOKEN is empty in .env. Add the Discord bot token before starting all Discord features."
    exit 1
  fi
}

ensure_python_deps() {
  if [[ "$SKIP_DEPS" == "1" ]]; then
    log "Skipping Python dependency setup."
    return 0
  fi

  ensure_python

  if [[ ! -d ".venv" ]]; then
    log "Creating virtual environment."
    "$PY_BIN" -m venv .venv
  fi

  log "Installing/updating Python dependencies."
  .venv/bin/python -m pip install --upgrade pip setuptools wheel
  .venv/bin/python -m pip install -r requirements.txt
}

install_docker_prompt() {
  if [[ "$(uname -s)" == "Linux" ]] && have_cmd curl; then
    printf 'Docker is not installed. Install Docker now? [y/N] '
    read -r answer
    case "$answer" in
      y|Y|yes|YES)
        curl -fsSL https://get.docker.com | sudo sh
        sudo usermod -aG docker "$USER" || true
        log "Docker was installed. You may need to log out and back in for group changes."
        ;;
      *)
        log "Docker install skipped."
        return 1
        ;;
    esac
  else
    log "Docker is not installed. Install Docker Desktop, then rerun this script."
    return 1
  fi
}

ensure_docker() {
  if ! have_cmd docker; then
    install_docker_prompt
  fi

  if ! docker info >/dev/null 2>&1; then
    if [[ "$(uname -s)" == "Darwin" ]]; then
      log "Starting Docker Desktop on macOS."
      open -a Docker || true
    elif have_cmd systemctl; then
      log "Starting Docker service."
      sudo systemctl start docker || true
    fi

    for _ in {1..60}; do
      if docker info >/dev/null 2>&1; then
        break
      fi
      sleep 2
    done
  fi

  if ! docker info >/dev/null 2>&1; then
    log "Docker daemon is not running."
    exit 1
  fi

  if ! docker compose version >/dev/null 2>&1; then
    log "Docker Compose plugin is not available. Install Docker Compose v2."
    exit 1
  fi
}

install_ollama_prompt() {
  local os_name
  os_name="$(uname -s)"

  if [[ ! -t 0 ]]; then
    log "Ollama is not installed and this shell is not interactive. Install Ollama, then rerun start.sh."
    exit 1
  fi

  printf 'Ollama is not installed. Install it now? [y/N] '
  read -r answer
  case "$answer" in
    y|Y|yes|YES)
      if [[ "$os_name" == "Darwin" ]] && have_cmd brew; then
        brew install ollama
      elif [[ "$os_name" == "Linux" ]] && have_cmd curl; then
        curl -fsSL https://ollama.com/install.sh | sh
      else
        log "Automatic Ollama install is not supported here. Install from https://ollama.com/download."
        exit 1
      fi
      ;;
    *)
      log "Ollama install skipped."
      exit 1
      ;;
  esac
}

ensure_ollama() {
  if ! have_cmd ollama; then
    install_ollama_prompt
  fi

  local host
  host="$(env_value OLLAMA_HOST)"
  host="${host:-http://localhost:11434}"

  if have_cmd curl && curl -fsS "${host}/api/tags" >/dev/null 2>&1; then
    return 0
  fi

  if [[ "$(uname -s)" == "Darwin" ]]; then
    open -a Ollama >/dev/null 2>&1 || true
  fi

  if ! have_cmd curl || ! curl -fsS "${host}/api/tags" >/dev/null 2>&1; then
    mkdir -p "$LOG_DIR"
    if ! pgrep -f "ollama serve" >/dev/null 2>&1; then
      log "Starting Ollama server in the background."
      nohup ollama serve >"${LOG_DIR}/ollama.log" 2>&1 &
    fi
  fi

  for _ in {1..30}; do
    if have_cmd curl && curl -fsS "${host}/api/tags" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  log "Ollama is installed but the API is not responding at ${host}."
  exit 1
}

choose_ollama_model() {
  local ai_mode
  ai_mode="$(env_value AI_EXECUTION_MODE)"
  ai_mode="${ai_mode:-local}"
  if [[ "$ai_mode" != "local" ]]; then
    log "AI_EXECUTION_MODE=${ai_mode}; local Ollama worker is not used."
    return 0
  fi

  ensure_ollama

  local current_model
  current_model="$(env_value OLLAMA_MODEL)"
  current_model="${current_model:-gemma3:4b}"

  models=()
  while IFS= read -r _line; do
    [[ -n "$_line" ]] && models+=("$_line")
  done < <(ollama list 2>/dev/null | awk 'NR > 1 {print $1}')
  if [[ "${#models[@]}" -eq 0 ]]; then
    log "No Ollama models are installed. Pulling ${current_model}."
    ollama pull "$current_model"
    set_env_value OLLAMA_MODEL "$current_model"
    return 0
  fi

  local current_installed="0"
  local model
  for model in "${models[@]}"; do
    if [[ "$model" == "$current_model" ]]; then
      current_installed="1"
      break
    fi
  done

  if [[ "$CHOOSE_MODEL" != "always" && "$current_installed" == "1" ]]; then
    log "Using Ollama model from .env: ${current_model}"
    return 0
  fi

  if [[ ! -t 0 ]]; then
    if [[ "$current_installed" == "0" ]]; then
      log "Configured OLLAMA_MODEL=${current_model} is not installed. Pulling it for non-interactive start."
      ollama pull "$current_model"
    fi
    return 0
  fi

  log "Installed Ollama models:"
  local index=1
  for model in "${models[@]}"; do
    printf '  %d) %s\n' "$index" "$model"
    index=$((index + 1))
  done
  printf 'Choose model number, or press Enter to keep %s: ' "$current_model"
  read -r answer
  if [[ -z "$answer" ]]; then
    if [[ "$current_installed" == "0" ]]; then
      ollama pull "$current_model"
    fi
    set_env_value OLLAMA_MODEL "$current_model"
    return 0
  fi
  if ! [[ "$answer" =~ ^[0-9]+$ ]] || (( answer < 1 || answer > ${#models[@]} )); then
    log "Invalid model selection."
    exit 1
  fi
  selected="${models[$((answer - 1))]}"
  set_env_value OLLAMA_MODEL "$selected"
  log "Selected Ollama model: ${selected}"
}

compose_service_running() {
  local service="$1"
  docker compose ps --services --status running 2>/dev/null | grep -qx "$service"
}

start_compose_api() {
  ensure_docker
  if compose_service_running api; then
    log "Docker API is already running."
  else
    log "Starting Docker API with external DATABASE_URL."
    docker compose up -d --build api
  fi
}

start_compose_discord_bot() {
  ensure_docker
  if compose_service_running discord-bot; then
    log "Discord bot container is already running."
  else
    log "Starting Discord bot container."
    docker compose --profile bot up -d --build discord-bot
  fi
}

start_compose_stack() {
  start_compose_api
  start_compose_discord_bot
  docker compose ps
  log "API URL: http://localhost:8000"
  log "Docs URL: http://localhost:8000/docs"
}

wait_for_api() {
  local url
  url="$(env_value SERVER_BASE_URL)"
  url="${url:-http://localhost:8000}"
  for _ in {1..60}; do
    if have_cmd curl && curl -fsS "${url}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  log "API health check did not become ready at ${url}/health."
  exit 1
}

local_worker_running() {
  local pid_file="${RUNTIME_DIR}/local-ai-worker.pid"
  [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" >/dev/null 2>&1
}

start_local_worker_background() {
  mkdir -p "$RUNTIME_DIR" "$LOG_DIR"
  if local_worker_running; then
    log "Local AI worker is already running."
    return 0
  fi

  log "Starting local AI worker in the background."
  nohup .venv/bin/python app.py local-worker >"${LOG_DIR}/local-ai-worker.log" 2>&1 &
  echo "$!" >"${RUNTIME_DIR}/local-ai-worker.pid"
}

ensure_env_file
ensure_python_deps
ensure_database_url

case "$MODE" in
  all)
    ensure_discord_bot_token
    choose_ollama_model
    start_compose_stack
    wait_for_api
    start_local_worker_background
    log "All services requested by start.sh are running."
    ;;
  docker)
    ensure_discord_bot_token
    start_compose_stack
    ;;
  api-only)
    start_compose_api
    docker compose ps
    log "API URL: http://localhost:8000"
    ;;
  local)
    choose_ollama_model
    log "Starting local FastAPI server with external DATABASE_URL."
    exec .venv/bin/python app.py
    ;;
  worker)
    choose_ollama_model
    log "Starting local AI worker."
    exec .venv/bin/python app.py local-worker
    ;;
  discord-bot)
    ensure_discord_bot_token
    log "Starting Discord bot."
    exec .venv/bin/python app.py discord-bot
    ;;
esac
