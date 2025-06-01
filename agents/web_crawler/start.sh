#!/bin/bash

# Exit on error
set -e

# Navigate to the script's directory
cd "$(dirname "$0")"

# Check for required commands
command -v python >/dev/null 2>&1 || { echo >&2 "Python is not installed. Aborting."; exit 1; }
command -v pip >/dev/null 2>&1 || { echo >&2 "pip is not installed. Aborting."; exit 1; }

# Load environment variables if .env file exists
if [ -f .env ]; then
  set -a
  source .env
  set +a
else
  echo "Warning: .env file not found. Proceeding without environment variables."
fi

export PYTHONPATH=$(realpath ../shared):$PYTHONPATH

echo "PYTHONPATH is: $PYTHONPATH"

# Activate virtual environment if it exists
if [ -d "../../.venv" ]; then
  source ../../.venv/bin/activate
fi

# Upgrade pip and setuptools for modern build support
pip install --upgrade pip setuptools wheel

# Install shared package in editable mode
pip install -e ../shared

# Install this agent in editable mode
pip install -e .

echo "Starting at $(date)"
echo "Python version: $(python --version)"

HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

# Delete the server log if it exists
if [ -f server.log ]; then
  rm server.log
fi
touch server.log

echo "Cleaning server.log..."

python -m uvicorn src.main:app --host $HOST --port $PORT --reload 