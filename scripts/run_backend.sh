#!/usr/bin/env bash
# Run Creer backend with optional TLS from env (CREER_SSL_*).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
elif [[ -f ../.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source ../.env
  set +a
fi

HOST="${CREER_HOST:-127.0.0.1}"
PORT="${CREER_PORT:-8000}"
ARGS=(uvicorn main:app --host "$HOST" --port "$PORT" --reload)

if [[ -n "${CREER_SSL_CERTFILE:-}" && -n "${CREER_SSL_KEYFILE:-}" ]]; then
  ARGS+=(--ssl-certfile "$CREER_SSL_CERTFILE" --ssl-keyfile "$CREER_SSL_KEYFILE")
  echo "TLS enabled: cert=$CREER_SSL_CERTFILE key=$CREER_SSL_KEYFILE"
else
  echo "TLS not configured (set CREER_SSL_CERTFILE + CREER_SSL_KEYFILE to enable)"
fi

export PYTHONPATH="${PYTHONPATH:-}:$ROOT/backend"
exec "${ARGS[@]}"
