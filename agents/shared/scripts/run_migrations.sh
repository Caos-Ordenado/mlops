#!/bin/bash
set -e

# Script's own directory
_SCRIPT_DIR_TEMP="$(dirname "$0")"
cd "$_SCRIPT_DIR_TEMP" # Ensure we are in the script's directory first
SCRIPT_DIR="$(pwd)"      # Get absolute path to script's dir
cd - > /dev/null         # Go back to original CWD before script was called (optional, for safety)

# Project root (two levels up from scripts directory)
PROJECT_ROOT="$(realpath "$SCRIPT_DIR/../..")"
# Path to alembic.ini directory
ALEMBIC_DIR="$(realpath "$SCRIPT_DIR/..")"
# Potential virtual environment path at project root
VENV_PATH="$PROJECT_ROOT/.venv"

# Activate virtual environment if it exists
if [ -d "$VENV_PATH/bin" ]; then
  echo "Activating virtual environment from $VENV_PATH..."
  source "$VENV_PATH/bin/activate"
  ALEMBIC_EXEC="$VENV_PATH/bin/alembic"
else
  echo "Warning: Virtual environment not found at $VENV_PATH. Assuming alembic is in system PATH."
  ALEMBIC_EXEC="alembic"
fi

# Define path to the .env file (expected to be in ALEMBIC_DIR, i.e., agents/shared/.env)
ROOT_ENV_FILE="$ALEMBIC_DIR/.env"

# Load environment variables from root .env file if it exists
if [ -f "$ROOT_ENV_FILE" ]; then
  echo "Loading environment variables from $ROOT_ENV_FILE..."
  set -a
  source "$ROOT_ENV_FILE"
  set +a
else
  echo "Warning: Root .env file not found at $ROOT_ENV_FILE. Make sure DB_CONNECTION_STRING is set manually."
fi

# Ensure DB_CONNECTION_STRING is set
if [ -z "$DB_CONNECTION_STRING" ]; then
  echo "Error: DB_CONNECTION_STRING is not set. Please set it in $ROOT_ENV_FILE or export it manually." >&2
  exit 1
fi

# Convert DB_CONNECTION_STRING to use a synchronous driver
if [[ "$DB_CONNECTION_STRING" == postgresql+asyncpg* ]]; then
  echo "Found asyncpg driver, converting to synchronous for Alembic..."
  SYNCHRONOUS_DB_URL=$(echo "$DB_CONNECTION_STRING" | sed 's/postgresql+asyncpg/postgresql/')
else
  SYNCHRONOUS_DB_URL="$DB_CONNECTION_STRING"
fi
echo "Using synchronous URL for Alembic: $SYNCHRONOUS_DB_URL"
export DB_CONNECTION_STRING="$SYNCHRONOUS_DB_URL" # Export as DB_CONNECTION_STRING for env.py

# Check if Alembic commands are provided
if [ $# -eq 0 ]; then
  echo "Usage: $0 <alembic_command> [alembic_options]"
  echo "Example: $0 revision -m 'add_new_column'"
  exit 1
fi

# Store current directory and then change to the Alembic directory
ORIGINAL_DIR=$(pwd)
cd "$ALEMBIC_DIR"
echo "Changed directory to $(pwd) for Alembic execution."

# Run Alembic
echo "Running: $ALEMBIC_EXEC -c alembic.ini "$@""
"$ALEMBIC_EXEC" -c alembic.ini "$@"

# Return to the original directory
cd "$ORIGINAL_DIR"
echo "Returned to directory $(pwd)."
echo "Alembic command finished." 