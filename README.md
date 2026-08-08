# Creer

AI-powered repo scaffolding inside your workspace.

**Current version: 1.0.0** (stable foundation)

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

## Registry & federation (v0.7–v1.0)

Self-hosted pack catalog plus optional multi-host federation and write auth:

| Method | Path | Description |
|---|---|---|
| `GET` | `/registry?q=&source=` | Searchable pack list |
| `GET` | `/registry/federated?q=&source=&peers=&discover=` | Local + peer merge; `discover=true` expands one hop |
| `GET` | `/registry/discover` | One-hop peer discovery |
| `GET` | `/registry/peers` | Peer health + configured URLs |
| `POST` | `/registry/peers/probe` | Probe one peer `{ url }` (auth when configured) |
| `GET` | `/registry/packs/{id}` | Pack metadata |
| `GET` | `/registry/packs/{id}/download` | Portable JSON pack (installable URL) |
| `GET` | `/marketplace` | Curated featured view |
| `POST` | `/packs/install` | Install pack from URL (auth when configured) |
| `DELETE` | `/packs/{id}` | Delete installed pack (auth when configured) |

When the backend sets `CREER_REGISTRY_TOKEN`, mutating routes expect `Authorization: Bearer <token>` and/or `X-Creer-Token`.

Extension settings: `creer.registryPeers`, `creer.showPeerStatus`, `creer.federatedDiscover` (pass `discover=true`), `creer.registryToken` (deprecated plaintext — prefer SecretStorage).

Commands: **Browse Federated Registry**, **Manage Registry Peers** (includes Discover peers), **Set / Clear Registry Token**.

Install from another Creer host:

```bash
curl -X POST http://localhost:8000/packs/install \
  -H 'Content-Type: application/json' \
  -d '{"url":"http://other-host:8000/registry/packs/fastapi-crud/download"}'
```

Set `CREER_PUBLIC_BASE_URL` for absolute download links in registry responses.
Set `CREER_REGISTRY_PEERS` for backend-configured federated discovery.
Set `CREER_REGISTRY_TOKEN` to require write auth on install/delete/probe.
Use `creer.registryPeers` in the extension for client-side extra peers when browsing.

## Extension commands

| Command | Title |
|---|---|
| `creer.createRepo` | Create New Repo |
| `creer.createRepoFromChat` | Create from Chat Prompt |
| `creer.browseMarketplace` | Browse Pack Marketplace |
| `creer.browseRegistry` | Browse Pack Registry |
| `creer.browseFederatedRegistry` | Browse Federated Registry |
| `creer.manageRegistryPeers` | Manage Registry Peers |
| `creer.installPackFromUrl` | Install Pack from URL |
| `creer.setGitHubToken` / `clearGitHubToken` | GitHub SecretStorage token |
| `creer.setRegistryToken` / `clearRegistryToken` | Registry write SecretStorage token |

## CI & publishing

- **CI** (`.github/workflows/ci.yml`): pytest + extension compile on push/PR
- **Release** (`.github/workflows/release.yml`): tag `v*` → package `.vsix`, create GitHub Release with attachment; publish to Marketplace / Open VSX only when `VSCE_PAT` / `OVSX_PAT` secrets are set

See [`RELEASE.md`](RELEASE.md) and [`extension/PUBLISH.md`](extension/PUBLISH.md). Package locally:

```bash
cd extension && npm run compile && npm run package
# → creer-1.0.0.vsix (includes media/icon.png)
```

Signed Marketplace / Open VSX publish requires your own `VSCE_PAT` / `OVSX_PAT` (never commit tokens). Agents cannot set GitHub Actions secrets — that remains a human step.

## License

MIT
