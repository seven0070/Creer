# Creer — Final Plan

## Done

- **v0.1** — FastAPI planner/generator + VS Code write-to-workspace (+ optional git)
- **v0.2** — Preview, GitHub create/push, templates, overwrite protection, `/creer` chat
- **v0.3** — Streaming, offline/local models, bake-ins, SecretStorage + GIT_ASKPASS
- **v0.4** — Stream cancel, selectable license/CI bake-ins, quality gates
- **v0.5** — Content diff preview before write, multi-root workspace targeting, installable JSON/YAML template packs
- **v0.6** — Pack marketplace + remote URL install/delete, side-by-side conflict diffs, publish packaging
- **v0.7** — Self-hosted pack registry (`/registry` + download), extension icon, Browse Pack Registry, release changelog
- **v0.8** — Federated registry (`/registry/federated` + peers), Browse Federated Registry UI, GitHub Actions release + CI (artifact-first; signed publish when secrets exist)
- **v0.9** — Peer status/probe UX (`creer.registryPeers`, Manage Registry Peers), federated browse enrichment, GitHub Release on tag + `RELEASE.md`
- **v1.0** — Stable foundation: optional registry write auth (Bearer / `X-Creer-Token`), `GET /registry/discover`, federated `discover=true`, SecretStorage registry token + Discover peers UX
- **v1.1** — Discovery hardening: peer policy (SSRF / private IP blocks, allow/deny, max hops); extension surfaces policy errors, `creer.federationMaxHops` / `creer.warnPrivatePeers`, blocked-discover UX
- **v1.2** — HMAC peer trust: backend `trust` blocks + peer_meta `trust_status` (`signed` | `unsigned` | `invalid` | `skipped`); extension `creer.requireSignedPeers`, trust badges/summaries; env `CREER_PEER_TRUST_SECRET` + `CREER_PEER_TRUST_MODE`

## Optional next

- Human: configure `VSCE_PAT` / `OVSX_PAT` repository secrets; tag `v1.2.0` (see [`RELEASE.md`](RELEASE.md)) — agents cannot set GitHub Actions secrets
- Mutual TLS between registries (optional future / human infra — not required for HMAC peer trust)

## Non-goals

- Multi-agent orchestration
- Memory graphs
- Overengineered plugin frameworks

Stay power-focused: idea → plan → files → workspace.
