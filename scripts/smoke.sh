#!/usr/bin/env bash
# Creer smoke checks against a running backend (does not start the server).
# Usage: ./scripts/smoke.sh
# Env: CREER_URL (default http://localhost:8000)
set -euo pipefail

BASE="${CREER_URL:-http://localhost:8000}"
BASE="${BASE%/}"
FAIL=0

ok() { printf '  OK  %s\n' "$1"; }
fail() { printf ' FAIL %s\n' "$1"; FAIL=1; }

echo "Creer smoke → $BASE"

# health
if HEALTH_JSON="$(curl -fsS --max-time 10 "$BASE/health" 2>/dev/null)"; then
  VERSION="$(printf '%s' "$HEALTH_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("version",""))' 2>/dev/null || true)"
  ok "GET /health (version=${VERSION:-?})"
else
  fail "GET /health"
fi

# doctor
if DOCTOR_JSON="$(curl -fsS --max-time 10 "$BASE/doctor" 2>/dev/null)"; then
  DOCTOR_OK="$(printf '%s' "$DOCTOR_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("ok"))' 2>/dev/null || true)"
  if [[ "$DOCTOR_OK" == "True" || "$DOCTOR_OK" == "true" ]]; then
    ok "GET /doctor (ok=true)"
  else
    fail "GET /doctor (ok=$DOCTOR_OK)"
  fi
else
  fail "GET /doctor"
fi

# templates
if TEMPLATES_JSON="$(curl -fsS --max-time 10 "$BASE/templates" 2>/dev/null)"; then
  HAS_MINIMAL="$(printf '%s' "$TEMPLATES_JSON" | python3 -c 'import sys,json; ids=[t.get("id") for t in json.load(sys.stdin).get("templates",[])]; print("fastapi-minimal" in ids)' 2>/dev/null || true)"
  if [[ "$HAS_MINIMAL" == "True" ]]; then
    ok "GET /templates (fastapi-minimal present)"
  else
    fail "GET /templates (fastapi-minimal missing)"
  fi
else
  fail "GET /templates"
fi

# packs
if curl -fsS --max-time 10 "$BASE/packs" >/dev/null 2>&1; then
  ok "GET /packs"
else
  fail "GET /packs"
fi

# bakeins
if curl -fsS --max-time 10 "$BASE/bakeins" >/dev/null 2>&1; then
  ok "GET /bakeins"
else
  fail "GET /bakeins"
fi

# plan with offline-friendly template
PLAN_BODY='{"idea":"smoke test minimal api","template_id":"fastapi-minimal"}'
if PLAN_JSON="$(curl -fsS --max-time 60 -H 'Content-Type: application/json' -d "$PLAN_BODY" "$BASE/plan" 2>/dev/null)"; then
  PROJECT="$(printf '%s' "$PLAN_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("project_name",""))' 2>/dev/null || true)"
  if [[ -n "$PROJECT" ]]; then
    ok "POST /plan template=fastapi-minimal (project=$PROJECT)"
  else
    fail "POST /plan (missing project_name)"
  fi
else
  fail "POST /plan template=fastapi-minimal"
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "Smoke FAILED"
  exit 1
fi
echo "Smoke OK"
exit 0
