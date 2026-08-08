# Creer

AI-powered repo scaffolding inside your workspace.

**Current version: 0.6.0**

## Architecture

```
creer/
├── backend/     # Python FastAPI AI engine (+ packs/)
└── extension/   # VS Code extension
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- OpenAI API key **or** `OPENAI_BASE_URL` **or** `CREER_OFFLINE=1` (with template/pack)
- VS Code / Cursor

## Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

### Environment

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_BASE_URL` | OpenAI-compatible base URL (Ollama, etc.) |
| `CREER_MODEL` | Model name (default `gpt-4o-mini`) |
| `CREER_OFFLINE` | Template/pack-only stubs |
| `CREER_PACKS_DIR` | Extra packs directory (overrides same ids) |

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health / version |
| `GET` | `/templates` | Built-in templates |
| `GET` | `/packs` | Installable JSON/YAML packs |
| `GET` | `/packs/{id}` | Single pack |
| `POST` | `/packs/install` | Install pack from URL (`{ url, overwrite? }`) |
| `DELETE` | `/packs/{id}` | Delete installed pack |
| `GET` | `/marketplace` | Remote/bundled marketplace items |
| `GET` | `/bakeins` | License/CI options |
| `POST` | `/plan` | Plan (`template_id` **or** `pack_id`) |
| `POST` | `/generate` | Generate + bake-ins + quality |
| `POST` | `/generate/stream` | SSE progress (`job_id`) |
| `POST` | `/generate/cancel` | Cancel job |
| `POST` | `/quality` | Dry-run gates |
| `POST` | `/github/create-repo` | Create GitHub repo |

Marketplace and pack install/delete may be absent on older backends; the extension handles that gracefully.

### Packs

Drop `.json` / `.yaml` files into `backend/packs/` (or `CREER_PACKS_DIR`):

```json
{
  "id": "fastapi-crud",
  "name": "FastAPI CRUD",
  "description": "CRUD API starter",
  "stack": "FastAPI + Uvicorn",
  "version": "1.0.0",
  "files": ["main.py", "requirements.txt", "README.md"]
}
```

Shipped examples: `fastapi-crud`, `express-ts`, `python-lib`.

## Extension (v0.6)

```bash
cd extension && npm install && npm run compile
```

Flow: idea → template/pack → bake-ins → plan preview → generate (cancellable) → content diff preview → **conflict review diffs** → write → optional git/GitHub.

Multi-root: QuickPick workspace folder (or `creer.defaultWorkspaceFolder`).

### Commands

| Command | Title |
|---|---|
| `creer.createRepo` | Creer: Create New Repo |
| `creer.createRepoFromChat` | Creer: Create from Chat Prompt |
| `creer.setGitHubToken` | Creer: Set GitHub Token |
| `creer.clearGitHubToken` | Creer: Clear GitHub Token |
| `creer.installPackFromUrl` | Creer: Install Pack from URL |
| `creer.browseMarketplace` | Creer: Browse Pack Marketplace |

### Settings

| Setting | Default | Description |
|---|---|---|
| `creer.backendUrl` | `http://localhost:8000` | Backend URL |
| `creer.contentPreview` | `true` | Diff/content preview before write |
| `creer.showConflictDiffs` | `true` | Offer side-by-side Review diffs on conflicts |
| `creer.defaultWorkspaceFolder` | `""` | Multi-root folder name/path hint |
| `creer.previewBeforeWrite` | `true` | Plan tree confirm before generate |
| `creer.useStreaming` | `true` | SSE progress |
| `creer.promptBakeins` | `true` | QuickPick license/CI |
| `creer.license` / `creer.ciPreset` | `mit` / `auto` | Defaults when not prompting |
| `creer.initGit` | `true` | git init + commit |
| `creer.createGitHubRepo` | `false` | Create remote |
| `creer.githubPrivate` | `true` | Private repos |

## Publishing

The extension is ready to package for the **VS Marketplace** and **Open VSX** (no credentials in-repo).

```bash
cd extension
npm run compile
npm run package          # → creer-0.6.0.vsix via npx @vscode/vsce
```

Full steps (tokens, `ovsx publish`, checklist): see [`extension/PUBLISH.md`](extension/PUBLISH.md).

## License

MIT
