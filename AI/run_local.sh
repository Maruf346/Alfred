#!/usr/bin/env bash
# Runs Alfred bound to localhost only — not reachable from other devices.
set -euo pipefail
cd "$(dirname "$0")"
export $(grep -v '^#' .env 2>/dev/null | xargs -d '\n' -I{} echo {} 2>/dev/null || true)
uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}" --reload
