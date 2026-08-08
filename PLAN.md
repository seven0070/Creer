# Creer — Final Plan

## Done

- **v0.1–v1.0** — Core scaffold, templates/packs, streaming, GitHub, marketplace, federation, auth, discovery
- **v1.1** — Discovery hardening (SSRF / allow-deny / hop budget)
- **v1.2** — HMAC signed peer trust
- **v1.3** — Optional TLS/mTLS transport for peers + Docker Compose multi-peer demo (`docs/MTLS.md`)
- **v1.4** — DX polish: `GET /doctor`, extension Doctor command + status bar, `scripts/smoke.sh`, `CONTRIBUTING.md`

## Optional next (human)

- Configure `VSCE_PAT` / `OVSX_PAT` and tag a release ([`RELEASE.md`](RELEASE.md)) — agents cannot set GitHub Actions secrets
- Production CA / cert rotation for mTLS deployments

## Non-goals

- Multi-agent orchestration
- Memory graphs
- Overengineered plugin frameworks

Stay power-focused: idea → plan → files → workspace.
