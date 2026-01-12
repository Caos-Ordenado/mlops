#!/bin/bash
set -e
set -o pipefail

# Move to script dir
cd "$(dirname "$0")"

# Load .env if present
if [ -f .env ]; then
  # In some environments (e.g. restricted sandboxes), sourcing .env may fail.
  # Treat it as optional and continue with defaults/env already present.
  set +e
  set -a
  source .env
  ENV_RC=$?
  set +a
  set -e
  if [ "$ENV_RC" != "0" ]; then
    echo "Warning: failed to load .env (rc=$ENV_RC). Continuing without it."
  fi
fi

# Prepare PYTHONPATH to include shared package
export PYTHONPATH=$(realpath ../../shared/shared):$PYTHONPATH
echo "PYTHONPATH: $PYTHONPATH"

# Activate repo-level venv if present
if [ -d "../../.venv" ]; then
  source ../../.venv/bin/activate
fi

pip install --upgrade pip setuptools wheel

# Install shared package (editable)
pip install -e ../../shared/shared

# Install renderer (editable)
pip install -e .

# Optionally ensure Playwright browsers are installed for local dev
RENDERER_INSTALL_BROWSERS=${RENDERER_INSTALL_BROWSERS:-true}
if [ "$RENDERER_INSTALL_BROWSERS" = "true" ]; then
  echo "Installing Playwright Chromium browser (local dev)..."
  python -m playwright install chromium || true
fi

HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8002}

echo "Starting renderer on $HOST:$PORT"
LOG_FILE=${LOG_FILE:-server.log}
if [ -f "$LOG_FILE" ]; then
  rm -f "$LOG_FILE"
fi
touch "$LOG_FILE"

# Mirror logs to console and persist to file (consistent with other agents)
python -m uvicorn src.main:app --host $HOST --port $PORT --reload 2>&1 | tee -a "$LOG_FILE"


