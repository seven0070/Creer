# Creer — Final Plan (post v0.1)

v0.1 delivered the foundation: FastAPI planner/generator + VS Code command that writes a generated repo into the workspace (optional git init).

## v0.2 — done

1. **Preview before writing** — plan preview markdown + confirm before generate/write (`creer.previewBeforeWrite`).
2. **GitHub repo creation** — `POST /github/create-repo` + extension remote add/push (`creer.createGitHubRepo`, token settings).
3. **Curated templates** — `GET /templates` + template-anchored `/plan` & `/generate` (`backend/app/templates.py`).
4. **Overwrite protection** — per-file conflict detection with overwrite / skip / cancel.
5. **Chat command `/creer`** — `creer.createRepoFromChat` + `@creer` chat participant (feature-detected).

Also in v0.2: modular extension layout (`api` / `scaffold` / `git` / `writeFiles` / `preview`), backend path/content validation, lazy OpenAI clients, extension path sandbox on write.

## v0.3 priorities (next)

- Streaming generation progress to the extension UI
- Local/offline model backends
- Open-source README / LICENSE / CI templates baked into every scaffold
- Hardening: avoid putting GitHub tokens on `git push` argv (credential helper / askpass); SecretStorage instead of plaintext `creer.githubToken` setting

## Non-goals (keep out of early versions)

- Multi-agent orchestration
- Memory graphs
- Overengineered plugin frameworks

Stay power-focused: idea → plan → files → workspace.
