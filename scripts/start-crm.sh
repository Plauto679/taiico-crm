#!/usr/bin/env bash
# ==============================================================================
# TAIICO CRM Startup Launcher Script
# ==============================================================================
# This script handles verification of dependencies, checking that Google Drive
# is mounted, auto-setup of environment files, python venv and node packages, and
# starts both the FastAPI backend and Next.js frontend in the background.
# ==============================================================================

set -euo pipefail

# Add common macOS path locations to PATH (essential for double-click environments)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Load NVM (Node Version Manager) if present in the user's home directory
if [ -d "$HOME/.nvm" ]; then
    export NVM_DIR="$HOME/.nvm"
    # shellcheck disable=SC1090
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
elif [ -s "/opt/homebrew/opt/nvm/nvm.sh" ]; then
    # shellcheck disable=SC1091
    . "/opt/homebrew/opt/nvm/nvm.sh"
fi

# Resolve paths
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BASE_DIR="$(dirname "$REPO_ROOT")"

# Logger Configuration
LOG_DIR="$HOME/Library/Logs/TAIICO CRM"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/launcher.log"

# Redirect stdout and stderr to launcher.log
exec >> "$LOG_FILE" 2>&1

echo "=========================================================================="
echo "TAIICO CRM Startup Initiated: $(date)"
echo "=========================================================================="

# 1. Verify Google Drive Mount
# Verify key directories from the Google Drive shared path exist
GD_CHECK_DIR1="$BASE_DIR/Bases de cobranza y comisiones"
GD_CHECK_DIR2="$BASE_DIR/Users"

if [ ! -d "$GD_CHECK_DIR1" ] || [ ! -d "$GD_CHECK_DIR2" ]; then
    echo "Error: Google Drive is not mounted or the repository is not in the correct Shared Drive path." >&2
    echo "Expected Base Directory: $BASE_DIR" >&2
    exit 2
fi

# 2. Check for pre-existing running instances
BACKEND_RUNNING=false
FRONTEND_RUNNING=false

if nc -z localhost 7777; then
    BACKEND_RUNNING=true
fi

if nc -z localhost 3000; then
    FRONTEND_RUNNING=true
fi

if [ "$BACKEND_RUNNING" = true ] && [ "$FRONTEND_RUNNING" = true ]; then
    echo "TAIICO CRM is already running on ports 7777 and 3000. Opening browser..."
    open http://localhost:3000
    exit 0
fi

# 3. Check for essential binary dependencies
if ! command -v node &>/dev/null; then
    echo "Error: Node.js is not installed or not available in the PATH." >&2
    exit 4
fi

if ! command -v npm &>/dev/null; then
    echo "Error: npm is not installed or not available in the PATH." >&2
    exit 4
fi

if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3 is not installed or not available in the PATH." >&2
    exit 4
fi

# 4. Handle backend env settings (.env fallback creation)
if [ ! -f "backend/.env" ]; then
    echo "Creating backend/.env fallback file from .env.example..."
    cp "backend/.env.example" "backend/.env"
fi

# 5. Initialize & verify Python Virtual Environment
VENV_DIR="$REPO_ROOT/backend/venv"

# Detect if the virtual environment is broken (e.g., broken absolute symlinks from sync)
if [ -d "$VENV_DIR" ] && ! "$VENV_DIR/bin/python" --version &>/dev/null; then
    echo "Warning: Python virtual environment is broken or has invalid links. Recreating..."
    rm -rf "$VENV_DIR"
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Python virtual environment not found in backend/venv. Creating..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Check if Python requirements need updating
HASH_FILE="$VENV_DIR/.requirements.hash"
CURRENT_HASH=$(shasum "$REPO_ROOT/backend/requirements.txt" | awk '{print $1}')
if [ ! -f "$HASH_FILE" ] || [ "$(cat "$HASH_FILE")" != "$CURRENT_HASH" ]; then
    echo "Installing/updating Python dependencies inside virtual environment..."
    "$VENV_DIR/bin/python" -m pip install --upgrade pip
    "$VENV_DIR/bin/python" -m pip install -r "$REPO_ROOT/backend/requirements.txt"
    echo "$CURRENT_HASH" > "$HASH_FILE"
else
    echo "Python dependencies are already up to date."
fi

# 6. Verify/Install Node.js dependencies
HASH_FILE_NODE="$REPO_ROOT/node_modules/.package.hash"
CURRENT_HASH_NODE=$(shasum "$REPO_ROOT/package.json" | awk '{print $1}')
if [ ! -d "node_modules" ] || [ ! -f "$HASH_FILE_NODE" ] || [ "$(cat "$HASH_FILE_NODE")" != "$CURRENT_HASH_NODE" ]; then
    echo "Installing/updating Node.js dependencies..."
    npm install
    echo "$CURRENT_HASH_NODE" > "$HASH_FILE_NODE"
else
    echo "Node.js dependencies are already up to date."
fi

# Ensure node binaries are executable (solves the Next.js permission denied issue)
echo "Setting executable permissions on node binaries..."
chmod -R u+x "$REPO_ROOT/node_modules/.bin" 2>/dev/null || true
chmod +x "$REPO_ROOT/node_modules/.bin/next" 2>/dev/null || true

# 7. Start FastAPI Backend if not running
if [ "$BACKEND_RUNNING" = false ]; then
    echo "Starting FastAPI backend on port 7777..."
    cd "$REPO_ROOT/backend"
    # uvicorn runs FastAPI; uvicorn.run inside main.py is how the project starts backend
    nohup "$VENV_DIR/bin/python" main.py > "$LOG_DIR/backend.log" 2>&1 &
    echo "FastAPI backend started in background."
fi

# 8. Start Next.js Frontend if not running
if [ "$FRONTEND_RUNNING" = false ]; then
    echo "Starting Next.js frontend on port 3000..."
    cd "$REPO_ROOT"
    nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
    echo "Next.js frontend started in background."
fi

# 9. Wait for ports to respond
echo "Waiting for ports 7777 and 3000 to become active..."
TIMEOUT=30
COUNTER=0
while [ $COUNTER -lt $TIMEOUT ]; do
    if nc -z localhost 7777 && nc -z localhost 3000; then
        echo "All TAIICO CRM services are active!"
        break
    fi
    sleep 1
    COUNTER=$((COUNTER + 1))
done

if [ $COUNTER -eq $TIMEOUT ]; then
    echo "Error: Timeout exceeded waiting for ports 7777 and 3000 to become active." >&2
    exit 3
fi

# 10. Launch browser to the CRM client UI
echo "Opening TAIICO CRM in browser (http://localhost:3000)..."
open http://localhost:3000
echo "Launch sequence complete!"
echo ""
