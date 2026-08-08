# Creer

AI-powered repo scaffolding inside your workspace.

**Current version: 0.8.0**

## Architecture

```
creer/
├── backend/     # Python FastAPI AI engine (+ packs/ + registry)
├── extension/   # VS Code extension (icon in media/)
└── .github/     # CI + release workflows
```

## Quick start

```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn main:app --reload --port 8000

# Extension
cd extension && npm install && npm run compile
# F5 → Creer: Create New Repo
```

## Registry & federation (v0.7–v0.8)

Self-hosted pack catalog plus optional multi-host federation:

| Method | Path | Description |
|---|---|---|
| `GET` | `/registry?q=&source=` | Searchable pack list |
| `GET` | `/registry/federated?q=&source=` | Local + peer merge |
| `GET` | `/registry/packs/{id}` | Pack metadata |
| `GET` | `/registry/packs/{id}/download` | Portable JSON pack (installable URL) |
| `GET` | `/marketplace` | Curated featured view |

Extension: **Creer: Browse Federated Registry** searches the federated catalog and installs via absolute `download_url` / `install_url`.

Install from another Creer host:

```bash
curl -X POST http://localhost:8000/packs/install \
  -H 'Content-Type: application/json' \
  -d '{"url":"http://other-host:8000/registry/packs/fastapi-crud/download"}'
```

Set `CREER_PUBLIC_BASE_URL` for absolute download links in registry responses.
Set `CREER_REGISTRY_PEERS` (comma-separated base URLs) for federated discovery.

## Extension commands

| Command | Title |
|---|---|
| `creer.createRepo` | Create New Repo |
| `creer.createRepoFromChat` | Create from Chat Prompt |
| `creer.browseMarketplace` | Browse Pack Marketplace |
| `creer.browseRegistry` | Browse Pack Registry |
| `creer.browseFederatedRegistry` | Browse Federated Registry |
| `creer.installPackFromUrl` | Install Pack from URL |
| `creer.setGitHubToken` / `clearGitHubToken` | SecretStorage token |

## CI & publishing

- **CI** (`.github/workflows/ci.yml`): pytest + extension compile on push/PR
- **Release** (`.github/workflows/release.yml`): tag `v*` or `workflow_dispatch` → package `.vsix` artifact; publish only when `VSCE_PAT` / `OVSX_PAT` secrets are set

See [`extension/PUBLISH.md`](extension/PUBLISH.md). Package locally:

```bash
cd extension && npm run compile && npm run package
# → creer-0.8.0.vsix (includes media/icon.png)
```

Signed Marketplace / Open VSX publish requires your own `VSCE_PAT` / `OVSX_PAT` (never commit tokens).

## License

MIT
