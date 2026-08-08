# Contributing to Creer

Power-focused scaffolding: idea → plan → files → workspace. Keep changes small and avoid new orchestration frameworks.

## Setup

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# For offline/template work without an LLM key:
#   CREER_OFFLINE=1
uvicorn main:app --reload --port 8000
# Or: ../scripts/run_backend.sh  (honors CREER_SSL_* for TLS)
```

### Extension

```bash
cd extension
npm install
npm run compile          # tsc --noEmit + esbuild → dist/extension.js
# F5 in VS Code to launch the Extension Development Host
npm run package          # minified bundled .vsix
```

Or from repo root: `make extension-install extension-compile check`.

## Tests

```bash
# Backend
cd backend && source venv/bin/activate
pytest

# Extension typecheck / compile
cd extension && npm run compile
```

## Smoke

Assumes a backend already listening (default `http://localhost:8000`):

```bash
# optional: export CREER_URL=http://127.0.0.1:8000
./scripts/smoke.sh
```

Checks `/health`, `/doctor`, `/templates`, `/packs`, `/bakeins`, and an offline-friendly `POST /plan` with `fastapi-minimal`.

## Doctor

- Backend: `GET /doctor` — structured diagnostics (no secrets)
- Extension: command **Creer: Doctor** (`creer.doctor`) — Output channel `Creer` + status summary

## PR tips

- Prefer focused diffs; match existing module style
- Bump version only when cutting a release slice (see [`RELEASE.md`](RELEASE.md))
- Include or update tests for API/behavior changes
- For TLS/mTLS peer demos see [`docs/MTLS.md`](docs/MTLS.md)
- Do not add multi-agent orchestration, memory graphs, or heavy plugin frameworks

## License

MIT
