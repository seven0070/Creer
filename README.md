# Creer

AI-powered repo scaffolding inside your workspace.

**Current version: 1.4.0**

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
| DX | `GET /doctor`, **Creer: Doctor**, status bar, `scripts/smoke.sh` |
| Ops | Docker Compose, CI/release workflows, `RELEASE.md`, `CONTRIBUTING.md` |

## Doctor + smoke

```bash
curl -s http://localhost:8000/doctor | python -m json.tool
./scripts/smoke.sh   # assumes backend on localhost:8000 (or $CREER_URL)
```

In VS Code: **Creer: Doctor** — writes a report to the `Creer` Output channel.

## TLS / mTLS

See [`docs/MTLS.md`](docs/MTLS.md). Generate dev certs with `./scripts/gen-dev-certs.sh`, then set `CREER_SSL_*` and use `./scripts/run_backend.sh`.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Publishing

Human step for Marketplace / Open VSX tokens — [`RELEASE.md`](RELEASE.md).

## License

MIT
