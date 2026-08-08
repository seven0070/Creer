# Release checklist (Creer)

Use this before tagging. Marketplace/Open VSX publish still needs human secrets.

## Pre-flight

- [ ] `make check` passes (pytest + extension compile/bundle)
- [ ] `CREER_OFFLINE=1` backend up; `make smoke` / `make doctor` OK
- [ ] `extension/package.json` version matches intended tag (e.g. `1.5.0`)
- [ ] `CHANGELOG.md` has a section for this version
- [ ] `npm run package` produces a small bundled `.vsix` (axios inlined; no `node_modules` tree)

## Tag + GitHub Release

- [ ] Merge the release PR to `main`
- [ ] `git tag -a v1.5.0 -m "Creer v1.5.0" && git push origin v1.5.0`
- [ ] Confirm Actions → Release built the artifact and attached it to the GitHub Release

## Optional Marketplace / Open VSX

- [ ] Repo secrets `VSCE_PAT` / `OVSX_PAT` configured (human only)
- [ ] Confirm listings updated

See also: [`RELEASE.md`](../RELEASE.md), [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`docs/MTLS.md`](MTLS.md).
