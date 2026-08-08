# Creer — Final Plan (post v0.1)

v0.1 delivered the foundation: FastAPI planner/generator + VS Code command that writes a generated repo into the workspace (optional git init).

## v0.2 — done

1. **Preview before writing** — plan preview markdown + confirm before generate/write (`creer.previewBeforeWrite`).
2. **GitHub repo creation** — `POST /github/create-repo` + extension remote add/push (`creer.createGitHubRepo`, token settings).
3. **Curated templates** — `GET /templates` + template-anchored `/plan` & `/generate` (`backend/app/templates.py`).
4. **Overwrite protection** — per-file conflict detection with overwrite / skip / cancel.
5. **Chat command `/creer`** — `creer.createRepoFromChat` + `@creer` chat participant (feature-detected).

Also in v0.2: modular extension layout (`api` / `scaffold` / `git` / `writeFiles` / `preview`), backend path/content validation, lazy OpenAI clients, extension path sandbox on write.

## v0.3 — done

1. **Streaming generation** — `POST /generate/stream` (SSE) + extension `creer.useStreaming` with per-file progress and fallback to `/generate`.
2. **Local / offline backends** — `OPENAI_BASE_URL` for OpenAI-compatible servers; `CREER_OFFLINE` for template/stub-only generation.
3. **Open-source bake-ins** — every scaffold gets `LICENSE` (MIT), optional default `README.md`, and `.github/workflows/ci.yml` when missing (`backend/app/bakeins.py`).
4. **Hardening** — `GIT_ASKPASS` for push (no token on argv/URL); GitHub token in SecretStorage (`creer.setGitHubToken` / `creer.clearGitHubToken`) with deprecated settings fallback.

## v0.4 (optional next)

- Cancellation for long streaming generates
- Richer bake-in / template composition (user-selectable license, CI presets)
- Light telemetry-free quality gates on generated trees

## Non-goals (keep out of early versions)

- Multi-agent orchestration
- Memory graphs
- Overengineered plugin frameworks

Stay power-focused: idea → plan → files → workspace.
