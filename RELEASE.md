# Releasing Creer

Human maintainer steps for a tagged release + optional Marketplace / Open VSX publish.

## 1. Secrets (once)

GitHub → **Settings → Secrets and variables → Actions**:

| Secret | Purpose |
|---|---|
| `VSCE_PAT` | VS Marketplace publish |
| `OVSX_PAT` | Open VSX publish |

Optional — without them, the workflow still builds a `.vsix` and (on tags) a GitHub Release.

**Agents cannot set these secrets.**

## 2. Verify

```bash
make check
# with backend up:
CREER_OFFLINE=1 make backend-run &
make smoke
make extension-package   # → creer-1.5.0.vsix
```

Follow [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md).

## 3. Tag

```bash
git tag -a v1.5.0 -m "Creer v1.5.0"
git push origin v1.5.0
```

## 4. After

Confirm GitHub Release has the `.vsix`. If secrets are set, confirm Marketplace / Open VSX.
