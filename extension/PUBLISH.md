# Publishing Creer (VS Code / Open VSX)

The extension is packaged from compiled `out/` JavaScript. **Do not commit secrets** (personal access tokens). Tokens stay in your environment only.

## Prerequisites

- Node.js 18+
- Compiled extension: `cd extension && npm install && npm run compile`
- Publisher identity:
  - **VS Marketplace:** Azure DevOps PAT with Marketplace (Acquire / Publish) scopes, and a [publisher](https://marketplace.visualstudio.com/manage) matching `package.json` → `publisher`
  - **Open VSX:** account + token from [open-vsx.org](https://open-vsx.org/)

## Package a `.vsix` (no publish)

```bash
cd extension
npm run compile
npm run package
# or: npx --yes @vscode/vsce package
```

This runs `vsce package`, respects `.vscodeignore`, and includes production dependencies (e.g. `axios`) plus `media/icon.png`. Output: `creer-1.0.0.vsix` (version from `package.json`).

### Publisher signing (human step)

vsce/ovsx publish with a PAT **signs the release to your publisher identity**. This repo is packaging-ready (icon, changelog, license, repository metadata). Actual signing/publish requires:

1. Create publisher `creer` (or change `package.json` → `publisher`)
2. Export `VSCE_PAT` / `OVSX_PAT` in your shell only
3. Run `npx @vscode/vsce publish` or `npx ovsx publish`

No tokens are stored in this repository.

## GitHub Actions release

Workflow: [`.github/workflows/release.yml`](../.github/workflows/release.yml)

| Trigger | Behavior |
|---|---|
| Tag `v*` (e.g. `v1.0.0`) | Build + package `.vsix`, upload artifact, create GitHub Release with `.vsix` attached |
| `workflow_dispatch` | Build + package + artifact (no GitHub Release); publish only if secrets set |

**Publish job** downloads the artifact and:

1. If repository secret `VSCE_PAT` is set → `npx @vscode/vsce publish --packagePath *.vsix -p "$VSCE_PAT"`
2. If repository secret `OVSX_PAT` is set → `npx ovsx publish *.vsix -p "$OVSX_PAT"`
3. If neither → logs `No publish tokens configured — artifact only` (signed publish is skipped)

Configure secrets under **Settings → Secrets and variables → Actions** (never commit PATs). CI (`.github/workflows/ci.yml`) runs backend pytest + extension compile on push/PR and does not publish.

Install locally for a smoke test:

```bash
code --install-extension creer-1.0.0.vsix
# or Cursor: cursor --install-extension creer-1.0.0.vsix
```

## Publish to VS Marketplace

1. Create a publisher if needed and ensure `package.json` `publisher` matches.
2. Export a PAT (do not paste into git or chat logs):

   ```bash
   export VSCE_PAT=your_marketplace_pat
   ```

3. Publish:

   ```bash
   cd extension
   npx --yes @vscode/vsce publish
   # or: npm run publish:marketplace  # prints the command reminder
   ```

Optional: `npx @vscode/vsce publish -p "$VSCE_PAT"`.

## Publish to Open VSX

1. Create an Open VSX token.
2. Export it:

   ```bash
   export OVSX_PAT=your_open_vsx_token
   ```

3. Publish the same extension (package first if you want a local `.vsix`):

   ```bash
   cd extension
   npx --yes ovsx publish
   # with an existing vsix:
   # npx --yes ovsx publish creer-1.0.0.vsix
   ```

`npm run publish:ovsx` only documents this flow (exits non-zero so CI does not publish by accident).

## Checklist before publish

- [ ] `version` bumped in `extension/package.json`
- [ ] `npm run compile` succeeds
- [ ] `license`, `repository`, `homepage`, `bugs` fields look correct
- [ ] `.vscodeignore` excludes `src/`, maps, and tooling (ships `out/`)
- [ ] Manual smoke: Create New Repo + Install Pack from URL against a running backend
- [ ] No tokens in repo files or commit history

## Notes

- Icon: add `icon.png` and `"icon": "icon.png"` in `package.json` when you have artwork.
- Prefer `npx @vscode/vsce` / `npx ovsx` so `@vscode/vsce` need not be a permanent `devDependency`.
