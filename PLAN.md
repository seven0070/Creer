# Creer — Final Plan

v0.1 delivered the foundation: FastAPI planner/generator + VS Code command that writes a generated repo into the workspace (optional git init).

## v0.2 — done

1. **Preview before writing** — plan preview markdown + confirm before generate/write (`creer.previewBeforeWrite`).
2. **GitHub repo creation** — `POST /github/create-repo` + extension remote add/push.
3. **Curated templates** — `GET /templates` + template-anchored `/plan` & `/generate`.
4. **Overwrite protection** — per-file conflict detection with overwrite / skip / cancel.
5. **Chat command `/creer`** — `creer.createRepoFromChat` + `@creer` chat participant.

## v0.3 — done

1. **Streaming generation** — `POST /generate/stream` (SSE) + extension progress UI.
2. **Local / offline backends** — `OPENAI_BASE_URL`, `CREER_OFFLINE`.
3. **Open-source bake-ins** — LICENSE / README / CI via `bakeins.py`.
4. **Hardening** — `GIT_ASKPASS` + SecretStorage for GitHub tokens.

## v0.4 — done

1. **Cancellation** — `job_id` on stream + `POST /generate/cancel`; extension AbortSignal + cancellable progress.
2. **Selectable bake-ins** — license (`mit` / `apache-2.0` / `none`) and CI presets (`auto` / `python` / `node` / `none`); `GET /bakeins`.
3. **Quality gates** — telemetry-free tree checks (`quality` on generate/done; `POST /quality`).

## v0.5 (optional next)

- Diff preview of generated file contents before write
- Multi-root workspace targeting
- Template packs as installable JSON/YAML

## Non-goals

- Multi-agent orchestration
- Memory graphs
- Overengineered plugin frameworks

Stay power-focused: idea → plan → files → workspace.
