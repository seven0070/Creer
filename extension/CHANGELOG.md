# Changelog

## 1.0.0

Stable foundation release: optional registry write auth, one-hop peer discovery, and federated discover browse.

- Optional registry write auth: `creer.registryToken` (deprecated plaintext) + SecretStorage via **Creer: Set / Clear Registry Token**
- Mutating API calls (`installPack`, `deletePack`, `probePeer`) send `Authorization: Bearer` and `X-Creer-Token` when a token is available
- `GET /registry/discover` client + `fetchFederatedRegistry({ discover })` for one-hop peer expansion
- Setting `creer.federatedDiscover` (default false) passes `discover=true` on federated browse
- **Creer: Manage Registry Peers** — Discover peers (one hop); probe/install/delete honor registry token
- Human publish step unchanged: set `VSCE_PAT` / `OVSX_PAT` yourself (agents cannot configure GitHub Actions secrets)

## 0.9.0

- Richer federation UX: `creer.registryPeers` + `creer.showPeerStatus` settings
- API: `fetchPeerStatus`, `probePeer`; federated fetch passes `peers` query
- **Creer: Browse Federated Registry** — peer health summary, local/`$(cloud)` labels
- **Creer: Manage Registry Peers** — add/remove setting peers, probe all (soft-fail)
- Release polish: GitHub Release on tag with `.vsix` attached; [`RELEASE.md`](../RELEASE.md)

## 0.8.0

- Federated multi-host registry: `GET /registry/federated`, `CREER_REGISTRY_PEERS`
- Extension: **Creer: Browse Federated Registry** (search + install via absolute download/install URLs)
- GitHub Actions release workflow (`.vsix` artifact; optional Marketplace / Open VSX publish when secrets exist)
- Lightweight CI (backend pytest + extension compile)

## 0.7.0

- Self-hosted pack registry: `GET /registry`, pack detail + JSON download
- Extension icon (`media/icon.png`) for Marketplace / Open VSX packaging
- **Creer: Browse Pack Registry** command (search + install via download URL)
- `CREER_PUBLIC_BASE_URL` for absolute registry links
- Marketplace items enriched with local download URLs when available

## 0.6.0

- Pack marketplace + remote URL install/delete
- Side-by-side conflict diffs (`creer-generated`)
- Publish packaging (`PUBLISH.md`, vsce/ovsx scripts)

## 0.5.0

- Content diff preview before write
- Multi-root workspace targeting
- Installable JSON/YAML template packs

## 0.4.0

- Stream cancellation
- Selectable license/CI bake-ins
- Quality gates

## 0.3.0

- Streaming generation
- Offline / local model backends
- OSS bake-ins + token hardening

## 0.2.0

- Plan preview, templates, overwrite protection, GitHub push, `/creer` chat

## 0.1.0

- Initial FastAPI backend + VS Code scaffold command
