#!/usr/bin/env bash
# Runs Alfred bound to 0.0.0.0 — reachable from other devices on your LAN.
# Make sure AI_SERVICE_API_KEY is set in .env before doing this, and that
# your firewall allows inbound TCP on the chosen port.
set -euo pipefail
cd "$(dirname "$0")"
export $(grep -v '^#' .env 2>/dev/null | xargs -d '\n' -I{} echo {} 2>/dev/null || true)

echo "Starting Alfred on 0.0.0.0:${PORT:-8000}"
echo "Reachable at http://<this-machine-LAN-IP>:${PORT:-8000} from other devices on the same network."
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
