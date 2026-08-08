# Creer — Final Plan (post v0.1)

v0.1 delivers the foundation: FastAPI planner/generator + VS Code command that writes a generated repo into the workspace (optional git init).

## v0.2 priorities

1. **Preview before writing** — show planned file tree / diffs and require confirm before disk writes.
2. **GitHub repo creation** — create remote repo and push the scaffolded project.
3. **Curated templates** — expand `backend/app/templates.py` into a real template system (stack presets + AI fill).
4. **Overwrite protection** — stronger conflict detection per-file (not only folder-level).
5. **Chat command `/creer`** — invoke scaffolding from chat / agent surface.

## Stretch (v0.3+)

- Production-grade validation layer (schema, path sandbox, content size limits)
- Streaming generation progress to the extension UI
- Local/offline model backends
- Open-source README / LICENSE / CI templates baked into every scaffold

## Non-goals (keep out of early versions)

- Multi-agent orchestration
- Memory graphs
- Overengineered plugin frameworks

Stay power-focused: idea → plan → files → workspace.
