#!/usr/bin/env sh
# Start the API on port 8800 (override: PORT=9000 ./run.sh)
cd "$(dirname "$0")"
exec python -m uvicorn app.main:app --reload --port "${PORT:-8800}"
