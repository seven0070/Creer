# Creer

AI-powered repo scaffolding inside your workspace.

**Current version: 1.5.0**

## Quick start

```bash
make backend-install backend-run          # :8000
make extension-install extension-compile  # F5 in extension/
make smoke                                # backend must be up
make extension-package                    # → creer-1.5.0.vsix (bundled)
```

Or Docker: `make docker-up` (peers on 8000/8001).

## Docs

| Doc | Purpose |
|---|---|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Dev setup |
| [`RELEASE.md`](RELEASE.md) | Tag + publish |
| [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) | Pre-flight checklist |
| [`docs/MTLS.md`](docs/MTLS.md) | Optional peer TLS |

## License

MIT
