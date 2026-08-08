# Creer

AI-powered repo scaffolding inside your workspace.

Describe an idea → Creer plans a clean structure → optionally preview/confirm → writes files into your VS Code workspace → optionally initializes git and creates a GitHub remote.

**Current version: 0.3.0**

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

## Backend (v0.3)

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
| `OPENAI_API_KEY` | OpenAI API key (optional if using a local server via `OPENAI_BASE_URL`, or `CREER_OFFLINE=1`) |
| `OPENAI_BASE_URL` | Optional OpenAI-compatible base URL for local/offline backends (Ollama, LM Studio, vLLM, etc.). Example: `http://127.0.0.1:11434/v1` |
| `CREER_MODEL` | Model name (default `gpt-4o-mini`) |
| `CREER_OFFLINE` | Set to `1`, `true`, or `yes` for template-only / stub generation — never calls the LLM. Offline planning requires a `template_id`. |

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness + version (`0.3.0`), offline flag, base URL status |
| `GET` | `/templates` | List curated starter templates |
| `POST` | `/plan` | Return a project plan (no file contents) |
| `POST` | `/generate` | Plan (or accept a plan) and generate file contents |
| `POST` | `/generate/stream` | Same as `/generate`, streamed as SSE with per-file progress |
| `POST` | `/github/create-repo` | Create a GitHub repo for the authenticated user |

#### `POST /plan`

```json
{ "idea": "Build a FastAPI todo app", "template_id": "fastapi-minimal" }
```

`template_id` is optional (required when `CREER_OFFLINE=1`). Response includes `project_name`, `stack`, `files`, and optionally `template_id` / `description`.

#### `POST /generate`

```json
{
  "idea": "Build a FastAPI todo app",
  "template_id": "fastapi-minimal",
  "plan": null
}
```

Omit `plan` to plan then generate, or pass a prior `/plan` body to skip re-planning. Response includes `project_name`, `stack`, and `files` (path → content map).

Every scaffold is merged with **bake-ins** after generation:

- `LICENSE` — MIT (always ensured if missing)
- `README.md` — only if the plan did not already produce one
- `.github/workflows/ci.yml` — stack-heuristic CI workflow if missing

#### `POST /generate/stream`

Same request body as `/generate`. Response is `text/event-stream` with JSON payloads on `data:` lines:

| Event | Fields | Meaning |
|---|---|---|
| `start` | `project_name`, `total`, `stack` | Generation started |
| `file` | `index`, `total`, `path`, `status` (`generating` \| `done`), optional `bytes` | Per-file progress |
| `done` | `project_name`, `stack`, `files`, optional `template_id` | Final file map (includes bake-ins) |
| `error` | `detail` | Failure |

Example:

```bash
curl -N -X POST http://localhost:8000/generate/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"idea":"Build a FastAPI todo app","template_id":"fastapi-minimal"}'
```

#### `POST /github/create-repo`

Prefer `Authorization: Bearer <token>`; `body.token` is also accepted.

```json
{ "name": "my-app", "private": true, "description": "optional" }
```

Returns `html_url`, `clone_url`, `full_name`.

Health check:

```bash
curl http://localhost:8000/health
```

List templates:

```bash
curl http://localhost:8000/templates
```

Generate:

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"idea":"Build a FastAPI todo app"}'
```

## Extension (v0.3)

```bash
cd extension
npm install
npm run compile
```

In VS Code / Cursor:

1. Open the `extension/` folder
2. Press **F5** (Run Extension)
3. In the Extension Development Host, open a workspace folder
4. Command Palette → **Creer: Create New Repo** (or **Creer: Create from Chat Prompt**)
5. Enter an idea, pick a template or AI plan, confirm the preview, and write files

### Commands

| Command | Title |
|---|---|
| `creer.createRepo` | Creer: Create New Repo |
| `creer.createRepoFromChat` | Creer: Create from Chat Prompt |
| `creer.setGitHubToken` | Creer: Set GitHub Token (SecretStorage) |
| `creer.clearGitHubToken` | Creer: Clear GitHub Token |

Chat: `@creer <idea>` (when the host supports chat participants) or run **Create from Chat Prompt** with a `/creer …` style input.

### Settings

| Setting | Default | Description |
|---|---|---|
| `creer.backendUrl` | `http://localhost:8000` | Backend base URL |
| `creer.initGit` | `true` | Run `git init` + initial commit after scaffolding |
| `creer.previewBeforeWrite` | `true` | Show plan preview and confirm before generating/writing |
| `creer.useStreaming` | `true` | Use SSE `/generate/stream` with per-file progress; falls back to `/generate` on failure |
| `creer.createGitHubRepo` | `false` | After scaffolding, create a GitHub remote repository |
| `creer.githubPrivate` | `true` | Create GitHub repositories as private |
| `creer.githubToken` | `""` | **Deprecated.** Prefer SecretStorage via **Creer: Set GitHub Token**. Used only as a fallback when SecretStorage is empty. |

### GitHub token (SecretStorage)

Tokens are stored in VS Code **SecretStorage**, not in plaintext settings:

1. **Creer: Set GitHub Token** — prompt and store
2. **Creer: Clear GitHub Token** — remove from SecretStorage

When creating/pushing a GitHub repo, Creer resolves the token as: SecretStorage → deprecated `creer.githubToken` setting → one-time prompt (optionally save). Push uses `GIT_ASKPASS` so the token is never embedded in the remote URL or git argv.

## License

MIT
