#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting FastAPI backend on http://127.0.0.1:8000 ..."
(
  cd "$ROOT_DIR/backend"
  ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

trap "kill $BACKEND_PID 2>/dev/null || true" EXIT

echo "Starting React Vite frontend on http://localhost:5173 ..."
cd "$ROOT_DIR/frontend"
npm run dev
