# Releasing Creer

Exact steps for a human maintainer to cut a tagged release with GitHub Release + optional Marketplace / Open VSX publish.

## 1. Set repository secrets (once)

In GitHub → **Settings → Secrets and variables → Actions**, add:

| Secret | Purpose |
|---|---|
| `VSCE_PAT` | Azure DevOps PAT with Marketplace **Acquire** + **Publish** |
| `OVSX_PAT` | Open VSX access token |

Both optional. Without them the workflow still builds a `.vsix` artifact and (on tags) a GitHub Release.

**Cloud agents cannot configure these secrets.**

## 2. Verify locally

```bash
grep '"version"' extension/package.json   # e.g. 1.4.0
cd extension && npm ci && npm run compile && npm run package
# → creer-1.4.0.vsix
```

## 3. Tag and push

```bash
git tag -a v1.4.0 -m "Creer v1.4.0"
git push origin v1.4.0
```

## 4. Workflow

See `.github/workflows/release.yml` — build → GitHub Release on tags → optional Marketplace/Open VSX when secrets exist.

## 5. After release

Confirm the GitHub Release lists the `.vsix`. If secrets were set, confirm Marketplace / Open VSX listings.
