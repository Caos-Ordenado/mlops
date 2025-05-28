#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

# Load environment variables if .env file exists
if [ -f .env ]; then
  export $(cat .env | sed 's/#.*//g' | xargs)
fi

# Run the application using python -m uvicorn
# This is generally preferred over directly running the main.py for uvicorn apps
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload 