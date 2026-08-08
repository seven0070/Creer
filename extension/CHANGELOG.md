# Changelog

## 1.4.0

DX polish: diagnostics Doctor, smoke script, contributing guide.

- Backend: `GET /doctor` structured checks (health, offline, llm, packs, peers, auth, trust, tls) — no secrets
- Extension: **Creer: Doctor** (`creer.doctor`) — Output channel `Creer` + Information/Warning summary; falls back to composing from `/health` on 404
- Status bar: lightweight `/health` probe on activate (`Creer $(check)` / `Creer $(warning)`); click runs Doctor
- `scripts/smoke.sh` — health/doctor/templates/packs/bakeins + offline-friendly plan (`fastapi-minimal`)
- Docs: `CONTRIBUTING.md`; PLAN/README/RELEASE updated for 1.4.0

## 1.3.0

- Optional TLS/mTLS for peer HTTP (`CREER_SSL_*`, `peer_httpx_client`)
- Docker Compose multi-peer demo + `scripts/gen-dev-certs.sh` / `run_backend.sh`
- Docs: `docs/MTLS.md`

## 1.2.0

HMAC peer trust UX: surface backend `trust` / `trust_status` and optionally hide unsigned peers.

- Setting: `creer.requireSignedPeers` (default false) — client-side filter hides federated packs from peers whose `trust_status` is `unsigned`, `invalid`, or `skipped` (local packs always kept)
- API types: optional `trust` blocks on discover/registry; federated `peer_meta` / probe `trust_status`: `signed` | `unsigned` | `invalid` | `skipped`
- **Browse Federated Registry** — peer trust summary (e.g. “2 signed, 1 unsigned”); QuickPick descriptions append a trust badge from peer meta
- **Manage Registry Peers** / probe — show trust info when the probe/status response includes it
- When `requireSignedPeers` filters out all peer packs, explain HMAC trust / `CREER_PEER_TRUST_SECRET` (+ mode)
- Keeps `max_hops` / federated discover wiring from v1.1

## 1.1.0

Discovery hardening: surface backend peer policy (SSRF / private IP / allow-deny / max hops) cleanly in the extension.

- Settings: `creer.federationMaxHops` (0–2, default 1) passed as `max_hops` on federated browse; `creer.warnPrivatePeers` (default true)
- Federated fetch types include optional `policy` / peer `blocked` fields; `formatAxiosError` surfaces FastAPI 400 policy `detail`
- **Manage Registry Peers** — modal warning before adding/probing localhost or private-looking hosts; discover shows policy-blocked suggestions as blocked (skipped on add)
- **Browse Federated Registry** — brief status when peers are ok / blocked by policy / failed (e.g. “2 peers ok, 1 blocked by policy”)
- Keeps `creer.federatedDiscover` (`discover=true`) alongside `max_hops`

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
