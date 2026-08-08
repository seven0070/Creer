# Creer

AI-powered repo scaffolding inside your workspace.

Describe an idea → Creer plans a clean structure → optionally preview/confirm → writes files into your VS Code workspace → optionally initializes git and creates a GitHub remote.

**Current version: 0.4.0**

## Architecture

```
creer/
├── backend/     # Python FastAPI AI engine
└── extension/   # VS Code extension
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- OpenAI API key **or** a local OpenAI-compatible server (`OPENAI_BASE_URL`), unless using offline template mode (`CREER_OFFLINE=1`)
- VS Code / Cursor

## Backend (v0.4)

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# set OPENAI_API_KEY and/or OPENAI_BASE_URL in .env
uvicorn main:app --reload --port 8000
```

### Environment

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (optional if using `OPENAI_BASE_URL` or `CREER_OFFLINE=1`) |
| `OPENAI_BASE_URL` | OpenAI-compatible base URL (Ollama, LM Studio, etc.). Example: `http://127.0.0.1:11434/v1` |
| `CREER_MODEL` | Model name (default `gpt-4o-mini`) |
| `CREER_OFFLINE` | `1` / `true` / `yes` for template-only stubs (planning requires `template_id`) |

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Version `0.4.0`, offline flag, model |
| `GET` | `/templates` | Curated starter templates |
| `GET` | `/bakeins` | License + CI bake-in options |
| `POST` | `/plan` | Plan only (no file contents) |
| `POST` | `/generate` | Generate files (+ bake-ins + `quality`) |
| `POST` | `/generate/stream` | SSE progress; `start` includes `job_id` |
| `POST` | `/generate/cancel` | Cancel by `job_id` |
| `POST` | `/quality` | Dry-run quality gates |
| `POST` | `/github/create-repo` | Create GitHub repo |

#### Generate body (sync or stream)

```json
{
  "idea": "Build a FastAPI todo app",
  "template_id": "fastapi-minimal",
  "plan": null,
  "job_id": null,
  "bakeins": {
    "license": "mit",
    "ci": "auto",
    "include_readme": true
  }
}
```

`bakeins.license`: `mit` | `apache-2.0` | `none`  
`bakeins.ci`: `auto` | `python` | `node` | `none`

#### Stream events

| Event | Meaning |
|---|---|
| `start` | Includes `job_id`, `total`, `project_name` |
| `file` | Per-file `generating` / `done` |
| `done` | Full `files` map + `quality` |
| `cancelled` | Stopped via `/generate/cancel` |
| `error` | Failure detail |

```bash
curl -N -X POST http://localhost:8000/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"idea":"todo api","template_id":"fastapi-minimal"}'
```

## Extension (v0.4)

```bash
cd extension
npm install
npm run compile
```

1. Open `extension/` → **F5**
2. Open a workspace folder
3. **Creer: Create New Repo**
4. Pick template → license/CI → confirm preview → generate (cancellable while streaming)

### Commands

| Command | Title |
|---|---|
| `creer.createRepo` | Creer: Create New Repo |
| `creer.createRepoFromChat` | Creer: Create from Chat Prompt |
| `creer.setGitHubToken` | Creer: Set GitHub Token |
| `creer.clearGitHubToken` | Creer: Clear GitHub Token |

### Settings

| Setting | Default | Description |
|---|---|---|
| `creer.backendUrl` | `http://localhost:8000` | Backend base URL |
| `creer.initGit` | `true` | `git init` + initial commit |
| `creer.previewBeforeWrite` | `true` | Confirm plan before generate |
| `creer.useStreaming` | `true` | SSE progress (cancellable) |
| `creer.promptBakeins` | `true` | QuickPick license/CI each run |
| `creer.license` | `mit` | Used when not prompting |
| `creer.ciPreset` | `auto` | Used when not prompting |
| `creer.createGitHubRepo` | `false` | Create GitHub remote after scaffold |
| `creer.githubPrivate` | `true` | Private GitHub repos |
| `creer.githubToken` | `""` | **Deprecated** — use SecretStorage |

GitHub push uses `GIT_ASKPASS` (token never on argv/URL).

## License

MIT
