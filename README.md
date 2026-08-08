# Creer

AI-powered repo scaffolding inside your workspace.

**Current version: 0.7.0**

## Architecture

```
creer/
├── backend/     # Python FastAPI AI engine (+ packs/ + registry)
└── extension/   # VS Code extension (icon in media/)
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

## Registry (v0.7)

Self-hosted pack catalog:

| Method | Path | Description |
|---|---|---|
| `GET` | `/registry?q=&source=` | Searchable pack list |
| `GET` | `/registry/packs/{id}` | Pack metadata |
| `GET` | `/registry/packs/{id}/download` | Portable JSON pack (installable URL) |
| `GET` | `/marketplace` | Curated featured view |

Install from another Creer host:

```bash
curl -X POST http://localhost:8000/packs/install \
  -H 'Content-Type: application/json' \
  -d '{"url":"http://other-host:8000/registry/packs/fastapi-crud/download"}'
```

Set `CREER_PUBLIC_BASE_URL` for absolute download links in registry responses.

## Extension commands

| Command | Title |
|---|---|
| `creer.createRepo` | Create New Repo |
| `creer.createRepoFromChat` | Create from Chat Prompt |
| `creer.browseMarketplace` | Browse Pack Marketplace |
| `creer.browseRegistry` | Browse Pack Registry |
| `creer.installPackFromUrl` | Install Pack from URL |
| `creer.setGitHubToken` / `clearGitHubToken` | SecretStorage token |

## Publishing

See [`extension/PUBLISH.md`](extension/PUBLISH.md). Package:

```bash
cd extension && npm run compile && npm run package
# → creer-0.7.0.vsix (includes media/icon.png)
```

Signed Marketplace / Open VSX publish requires your own `VSCE_PAT` / `OVSX_PAT` (never commit tokens).

## License

MIT
