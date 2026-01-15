#!/bin/bash

set -e

cd "$(dirname "$0")"

command -v node >/dev/null 2>&1 || { echo >&2 "Node.js is not installed. Aborting."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo >&2 "npm is not installed. Aborting."; exit 1; }

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

echo "Starting Nuxt dev server..."
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-3000}

npm install
HOST=$HOST PORT=$PORT npm run dev
