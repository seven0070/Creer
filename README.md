# Creer

AI-powered repo scaffolding inside your workspace.

**Current version: 1.1.0** (discovery hardening)

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

## Registry & federation (v0.7–v1.1)

Self-hosted pack catalog plus optional multi-host federation, write auth, and peer policy:

| Method | Path | Description |
|---|---|---|
| `GET` | `/registry?q=&source=` | Searchable pack list |
| `GET` | `/registry/federated?q=&source=&peers=&discover=&max_hops=` | Local + peer merge; `discover=true` expands peers; `max_hops` caps hop depth (0–2) |
| `GET` | `/registry/discover` | Peer discovery (policy-filtered in v1.1+) |
| `GET` | `/registry/peers` | Peer health + configured URLs |
| `POST` | `/registry/peers/probe` | Probe one peer `{ url }` (auth when configured; may 400 on policy) |
| `GET` | `/registry/packs/{id}` | Pack metadata |
| `GET` | `/registry/packs/{id}/download` | Portable JSON pack (installable URL) |
| `GET` | `/marketplace` | Curated featured view |
| `POST` | `/packs/install` | Install pack from URL (auth when configured) |
| `DELETE` | `/packs/{id}` | Delete installed pack (auth when configured) |

When the backend sets `CREER_REGISTRY_TOKEN`, mutating routes expect `Authorization: Bearer <token>` and/or `X-Creer-Token`.

### Peer policy env vars (v1.1)

Backend peer/federation policy (SSRF and private-IP hardening). The extension surfaces 400 `detail` strings and per-peer `error` / optional `policy` fields.

| Env | Purpose |
|---|---|
| `CREER_FEDERATION_MAX_HOPS` | Default max discovery hops (0–2; default 1). Extension may also send `max_hops` on federated browse when the backend accepts it. |
| `CREER_PEER_ALLOWLIST` | Comma-separated hostnames/URLs; if non-empty, only these peers may be contacted |
| `CREER_PEER_DENYLIST` | Comma-separated hostnames/URLs always blocked |
| `CREER_ALLOW_PRIVATE_PEERS` | When true (`1`/`true`/`yes`), allow loopback/private/link-local peers (default off) |

Extension settings: `creer.registryPeers`, `creer.showPeerStatus`, `creer.federatedDiscover` (`discover=true`), `creer.federationMaxHops` (`max_hops`), `creer.warnPrivatePeers`, `creer.registryToken` (deprecated plaintext — prefer SecretStorage).

Commands: **Browse Federated Registry**, **Manage Registry Peers** (Discover peers; private-host warning; policy-blocked suggestions), **Set / Clear Registry Token**.

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
# → creer-1.1.0.vsix (includes media/icon.png)
```

Signed Marketplace / Open VSX publish requires your own `VSCE_PAT` / `OVSX_PAT` (never commit tokens). Agents cannot set GitHub Actions secrets — that remains a human step.

## License

MIT
