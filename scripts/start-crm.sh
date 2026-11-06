#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

if [ -d "$HOME/.nvm" ]; then
    export NVM_DIR="$HOME/.nvm"
    # shellcheck disable=SC1090
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
elif [ -s "/opt/homebrew/opt/nvm/nvm.sh" ]; then
    # shellcheck disable=SC1091
    . "/opt/homebrew/opt/nvm/nvm.sh"
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

APP_NAME="TAIICO CRM"
LOG_DIR="$HOME/Library/Logs/$APP_NAME"
LOG_FILE="$LOG_DIR/launcher.log"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PORT="${TAIICO_CRM_BACKEND_PORT:-7777}"
FRONTEND_PORT="${TAIICO_CRM_FRONTEND_PORT:-3000}"
BACKEND_URL="http://localhost:$BACKEND_PORT"
FRONTEND_URL="http://localhost:$FRONTEND_PORT"
BASE_DIR="$(dirname "$REPO_ROOT")"
VENV_DIR="$REPO_ROOT/backend/.venv"

mkdir -p "$LOG_DIR"
exec >> "$LOG_FILE" 2>&1

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
    local message="$1"
    local code="${2:-1}"
    log "ERROR: $message"
    exit "$code"
}

port_open() {
    nc -z localhost "$1" >/dev/null 2>&1
}

wait_for_port() {
    local port="$1"
    local label="$2"
    local timeout="${3:-45}"
    local elapsed=0

    log "Waiting for $label on port $port..."
    while [ "$elapsed" -lt "$timeout" ]; do
        if port_open "$port"; then
            log "$label is responding on port $port."
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    return 1
}

check_command() {
    command -v "$1" >/dev/null 2>&1 || fail "$2" "$3"
}

check_drive_paths() {
    local missing=()
    local required_dirs=(
        "$BASE_DIR/Bases de cobranza y comisiones"
        "$BASE_DIR/Relaciones de cartera"
        "$BASE_DIR/Fechas de emision de Polizas y renovaciones"
        "$BASE_DIR/Correos de los clientes"
        "$BASE_DIR/Users"
    )

    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            missing+=("$dir")
        fi
    done

    if [ "${#missing[@]}" -gt 0 ]; then
        log "Google Drive validation failed. Missing expected CRM data folders:"
        printf ' - %s\n' "${missing[@]}" >&2
        fail "Google Drive is not mounted, not fully synced, or the repo is not next to the CRM data folders. Expected base folder: $BASE_DIR" 2
    fi
}

install_backend_dependencies() {
    if [ -d "$VENV_DIR" ] && ! "$VENV_DIR/bin/python" --version >/dev/null 2>&1; then
        log "Existing Python virtualenv is not usable. Recreating $VENV_DIR..."
        rm -rf "$VENV_DIR"
    fi

    if [ ! -d "$VENV_DIR" ]; then
        log "Creating Python virtualenv at $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
    fi

    local hash_file="$VENV_DIR/.requirements.hash"
    local current_hash
    current_hash="$(shasum "$REPO_ROOT/backend/requirements.txt" | awk '{print $1}')"

    if [ ! -f "$hash_file" ] || [ "$(cat "$hash_file")" != "$current_hash" ]; then
        log "Installing Python dependencies..."
        "$VENV_DIR/bin/python" -m pip install --upgrade pip
        "$VENV_DIR/bin/python" -m pip install -r "$REPO_ROOT/backend/requirements.txt"
        printf '%s\n' "$current_hash" > "$hash_file"
    else
        log "Python dependencies are already installed."
    fi
}

install_frontend_dependencies() {
    local hash_file="$REPO_ROOT/node_modules/.package-lock.hash"
    local current_hash

    if [ -f "$REPO_ROOT/package-lock.json" ]; then
        current_hash="$(shasum "$REPO_ROOT/package-lock.json" | awk '{print $1}')"
    else
        current_hash="$(shasum "$REPO_ROOT/package.json" | awk '{print $1}')"
    fi

    if [ ! -d "$REPO_ROOT/node_modules" ] || [ ! -f "$hash_file" ] || [ "$(cat "$hash_file")" != "$current_hash" ]; then
        log "Installing Node dependencies..."
        if [ -f "$REPO_ROOT/package-lock.json" ]; then
            npm install
        else
            npm install
        fi
        mkdir -p "$REPO_ROOT/node_modules"
        printf '%s\n' "$current_hash" > "$hash_file"
    else
        log "Node dependencies are already installed."
    fi

    chmod -R u+x "$REPO_ROOT/node_modules/.bin" 2>/dev/null || true
}

start_backend() {
    if port_open "$BACKEND_PORT"; then
        log "Backend already running on $BACKEND_URL."
        return 0
    fi

    log "Starting FastAPI backend on $BACKEND_URL..."
    cd "$REPO_ROOT/backend"
    nohup "$VENV_DIR/bin/python" -m uvicorn main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload > "$BACKEND_LOG" 2>&1 &
}

start_frontend() {
    if port_open "$FRONTEND_PORT"; then
        log "Frontend already running on $FRONTEND_URL."
        return 0
    fi

    log "Starting Next.js frontend on $FRONTEND_URL..."
    cd "$REPO_ROOT"
    PORT="$FRONTEND_PORT" nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
}

log "=========================================================================="
log "$APP_NAME launcher started"
log "Repo root: $REPO_ROOT"
log "Expected CRM data folder: $BASE_DIR"
log "Logs: $LOG_DIR"

check_command node "Node.js is not installed or is not available in PATH. Install Node.js 18 or newer." 4
check_command npm "npm is not installed or is not available in PATH. Install Node.js 18 or newer." 4
check_command python3 "Python 3 is not installed or is not available in PATH." 4
check_command nc "The macOS nc command is not available, so the launcher cannot check local ports." 4

check_drive_paths

if [ ! -f "$REPO_ROOT/backend/.env" ]; then
    log "backend/.env not found. Creating local fallback from backend/.env.example."
    cp "$REPO_ROOT/backend/.env.example" "$REPO_ROOT/backend/.env"
fi

if port_open "$BACKEND_PORT" && port_open "$FRONTEND_PORT"; then
    log "$APP_NAME is already running. Opening $FRONTEND_URL..."
    open "$FRONTEND_URL"
    exit 0
fi

install_backend_dependencies
install_frontend_dependencies
start_backend
start_frontend

wait_for_port "$BACKEND_PORT" "FastAPI backend" 45 || fail "Timed out waiting for backend on $BACKEND_URL. Check $BACKEND_LOG" 3
wait_for_port "$FRONTEND_PORT" "Next.js frontend" 45 || fail "Timed out waiting for frontend on $FRONTEND_URL. Check $FRONTEND_LOG" 3

log "Opening browser at $FRONTEND_URL..."
open "$FRONTEND_URL"
log "$APP_NAME launcher completed successfully."
