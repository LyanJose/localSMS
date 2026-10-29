#!/usr/bin/env bash
# Développement (Linux/macOS/WSL) : API sur :8765 + interface Vite sur :5173 (proxy vers l'API).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d backend/.venv ] || python3 -m venv backend/.venv
backend/.venv/bin/pip install -q -r backend/requirements-dev.txt
(cd web && [ -d node_modules ] || npm install)
cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT
(cd backend && .venv/bin/python -m localsms --no-browser) &
sleep 1
TOKEN="$(cat "${LOCALSMS_DATA_DIR:-$HOME/.local/share/localsms}/admin_token")"
echo "Interface de dev : http://localhost:5173/#token=$TOKEN"
(cd web && npm run dev)
