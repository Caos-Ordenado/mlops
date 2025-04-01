#!/bin/bash

# Exit on error
set -e

# Navigate to the script's directory
cd "$(dirname "$0")"

# Clean the log file
echo "Cleaning crawler.log..."
if [ -f "crawler.log" ]; then
    rm crawler.log
fi
touch crawler.log

# Verify Python path
echo "Using Python from: $(which python)"
echo "Python version: $(python --version)"

# Install requirements if needed
echo "Installing/Updating requirements..."
pip install -r requirements.txt

# Load environment variables
if [ -f ".env" ]; then
    echo "Loading environment variables..."
    set -a
    source .env
    set +a
fi

# Verify redis installation
echo "Checking redis package..."
pip show redis

# Start the FastAPI application
echo "Starting FastAPI server..."
PYTHONPATH=$PYTHONPATH:$(pwd)/src python src/main.py 