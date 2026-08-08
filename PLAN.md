# PLAN.md — Creer v0.2 and beyond

## v0.1 DONE ✅
- FastAPI backend: planner, generator, validator, lazy OpenAI client
- VS Code extension: `creer.createRepo`, writes files, git init
- Validation, error handling, CORS, health

## v0.2 — Preview, Templates, GitHub, Safety, Chat
**Goal:** ship “preview before write” + guardrails.

1. **Preview before write**
   - Extension: tree view / webview showing `project_name` + file list + diff vs existing
   - Confirm / Cancel, per-file checkboxes
   - Reuses same `/generate` payload

2. **Curated templates (`backend/app/templates.py`)**
   - `fastapi-crud`, `nextjs-starter`, `python-cli`, `express-ts`
   - `GET /templates` + `POST /generate` with `template` field (optional)
   - If template hit → seed plan instead of pure LLM (deterministic start)

3. **Overwrite protection v2**
   - Content diff, `conflict` handling
   - Show unified diff for existing files
   - Options: overwrite / skip / rename

4. **GitHub auto-push**
   - `backend/app/github.py` — create repo via GitHub API + push
   - Extension: GitHub PAT input (secretStorage), `creer.githubToken` setting
   - Checkbox “Create GitHub repo”

5. **Chat command `/creer`**
   - Contribute `vscode.chat` participant (if available) or inline chat fallback
   - Same backend, streaming response stub

6. **Quality**
   - `backend/tests/` (planner mock, validator unit)
   - `make check`, `make run`

## v0.3+ — Streaming, Offline, Bake-ins, Hardening
- Streaming generation (SSE), cancel, selectable bake-ins (eslint, prettier, docker), quality gates.
