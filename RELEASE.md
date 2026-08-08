# Releasing Creer v0.9.0

Exact steps for a human maintainer to cut a tagged release with GitHub Release + optional Marketplace / Open VSX publish.

## 1. Set repository secrets (once)

In GitHub → **Settings → Secrets and variables → Actions**, add:

| Secret | Purpose |
|---|---|
| `VSCE_PAT` | Azure DevOps PAT with Marketplace **Acquire** + **Publish** (publisher must match `extension/package.json` → `publisher`) |
| `OVSX_PAT` | Open VSX access token from [open-vsx.org](https://open-vsx.org/) |

Both are optional. If neither is set, the release workflow still builds the `.vsix`, uploads it as an artifact, and (on tag pushes) creates a **GitHub Release** with the `.vsix` attached. Marketplace / Open VSX publish is skipped with `No publish tokens configured — artifact only`.

Never commit PATs. Prefer repo secrets over exporting tokens in shared shells.

## 2. Bump & verify locally

```bash
# Confirm extension version is 0.9.0
grep '"version"' extension/package.json

cd extension
npm ci
npm run compile
npm run package
# → creer-0.9.0.vsix
```

Smoke-test: `code --install-extension creer-0.9.0.vsix` (or Cursor equivalent) against a running backend.

## 3. Tag v0.9.0 and push

From a clean `main` (or the release commit):

```bash
git tag -a v0.9.0 -m "Creer v0.9.0"
git push origin v0.9.0
```

Tag pattern `v*` triggers [`.github/workflows/release.yml`](.github/workflows/release.yml).

## 4. What the workflow does

1. **build** — `npm ci` → `compile` → `vsce package` → upload `creer-vsix` artifact  
2. **github-release** (tag pushes only) — create a GitHub Release and attach the `.vsix` (`contents: write`)  
3. **publish** — if `VSCE_PAT` / `OVSX_PAT` secrets exist, publish to Marketplace / Open VSX; otherwise artifact-only

You can also run the workflow via **Actions → Release → Run workflow** (`workflow_dispatch`) for a package/artifact without a tag (no GitHub Release job in that case).

## 5. After release

- Confirm the GitHub Release page lists `creer-0.9.0.vsix`
- If secrets were set, confirm Marketplace / Open VSX listing updated to 0.9.0
- See [`extension/PUBLISH.md`](extension/PUBLISH.md) for manual `vsce` / `ovsx` publish from a laptop
