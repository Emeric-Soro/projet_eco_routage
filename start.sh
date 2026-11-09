#!/usr/bin/env bash
# Lance le backend (API FastAPI :8000) et le frontend (Vite :5173) ensemble.
# Usage : ./start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo
  echo "Arrêt de la plateforme…"
  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  echo "Terminé."
}
trap cleanup EXIT INT TERM

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
  echo "Attention : .venv introuvable, utilisation de $PYTHON"
else
  echo "Erreur : Python introuvable. Créez d'abord l'environnement :"
  echo "  python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt -r api/requirements.txt"
  exit 1
fi

if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Installation des dépendances frontend…"
  (cd "$ROOT/frontend" && npm install)
fi

echo "Backend  → http://127.0.0.1:8000  (docs : /docs)"
echo "Frontend → http://127.0.0.1:5173"
echo "Ctrl+C pour tout arrêter."
echo

"$PYTHON" -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

(cd "$ROOT/frontend" && npm run dev -- --host 127.0.0.1 --port 5173) &
FRONTEND_PID=$!

wait
