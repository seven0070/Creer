# Creer

AI-powered repo scaffolding inside your workspace.

**Current version: 1.3.0**

## Quick start

```bash
# Backend (local)
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn main:app --reload --port 8000

# Or Docker multi-peer demo
docker compose up --build
# A: http://localhost:8000  B: http://localhost:8001
curl -s http://localhost:8000/registry/federated | head

# Extension
cd extension && npm install && npm run compile
```

## Highlights

| Area | Features |
|---|---|
| Scaffold | Plan → preview → stream generate → content/conflict diffs → write |
| Packs | Templates, JSON/YAML packs, marketplace, registry download |
| Federation | Peers, discover, hop budget, SSRF policy, HMAC trust, optional mTLS |
| Ops | Docker Compose, CI/release workflows, `RELEASE.md` |

## TLS / mTLS

See [`docs/MTLS.md`](docs/MTLS.md). Generate dev certs with `./scripts/gen-dev-certs.sh`, then set `CREER_SSL_*` and use `./scripts/run_backend.sh`.

## Publishing

Human step for Marketplace / Open VSX tokens — [`RELEASE.md`](RELEASE.md).

## License

MIT
