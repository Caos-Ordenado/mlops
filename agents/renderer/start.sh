#!/bin/bash
set -e

# Move to script dir
cd "$(dirname "$0")"

# Load .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Prepare PYTHONPATH to include shared package
export PYTHONPATH=$(realpath ../shared):$PYTHONPATH
echo "PYTHONPATH: $PYTHONPATH"

# Activate repo-level venv if present
if [ -d "../../.venv" ]; then
  source ../../.venv/bin/activate
fi

pip install --upgrade pip setuptools wheel

# Install shared package (editable)
pip install -e ../shared

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
python -m uvicorn src.main:app --host $HOST --port $PORT --reload


