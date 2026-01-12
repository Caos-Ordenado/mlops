#!/bin/bash
set -e

cd "$(dirname "$0")"

export PYTHONPATH=$(realpath ../../shared/shared):$PYTHONPATH

# Activate repo-level venv if present
if [ -d "../../.venv" ]; then
  source ../../.venv/bin/activate
fi

pip install --upgrade pip setuptools wheel
pip install -e ../../shared/shared
pip install -e .

HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

echo "Starting openwebui-tools on $HOST:$PORT"
python -m uvicorn src.main:app --host $HOST --port $PORT --reload


