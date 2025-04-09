#!/bin/bash

# Exit on error
set -e

# Navigate to the script's directory
cd "$(dirname "$0")"

# Clean the log file
echo "Cleaning server.log..."
if [ -f "server.log" ]; then
    rm server.log
fi
touch server.log

# Verify Python path
echo "Using Python from: $(which python)"
echo "Python version: $(python --version)"

# Install package in development mode
echo "Installing package in development mode..."
pip install -e .

# Load environment variables
if [ -f ".env" ]; then
    echo "Loading environment variables..."
    set -a
    source .env
    set +a
fi

# Verify required package installation
echo "Checking required packages..."
pip show fastapi
pip show agent-utils

# Set the Python path to include the project root
export PYTHONPATH=$PYTHONPATH:$(pwd)/..

# Start the FastAPI application with hot reload
echo "Starting Research Agent server with hot reload..."
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000