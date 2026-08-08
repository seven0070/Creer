# Creer — Final Plan

## Done

- **v0.1–v1.0** — Core scaffold, packs, streaming, GitHub, marketplace, federation, auth, discovery
- **v1.1** — Discovery hardening (SSRF / allow-deny / hop budget)
- **v1.2** — HMAC signed peer trust
- **v1.3** — Optional TLS/mTLS + Docker Compose
- **v1.4** — Doctor diagnostics + smoke/CONTRIBUTING DX
- **v1.5** — Release readiness: esbuild-bundled `.vsix`, Makefile, release checklist

## Optional next (human)

- Configure `VSCE_PAT` / `OVSX_PAT` and tag a release ([`RELEASE.md`](RELEASE.md) / [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md))
- Production CA / cert rotation for mTLS

## Non-goals

- Multi-agent orchestration
- Memory graphs
- Overengineered plugin frameworks

Stay power-focused: idea → plan → files → workspace.
