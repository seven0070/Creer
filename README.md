# Creer

AI-powered repo scaffolding inside your workspace.

Describe an idea → Creer plans a clean structure → optionally preview/confirm → writes files into your VS Code workspace → optionally initializes git and creates a GitHub remote.

**Current version: 0.2.0**

## Architecture

```
creer/
├── backend/     # Python FastAPI AI engine
└── extension/   # VS Code extension
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- OpenAI API key (required for AI planning/generation; template-only planning can run without it)
- VS Code / Cursor

## Backend (v0.2)

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# set OPENAI_API_KEY in .env
uvicorn main:app --reload --port 8000
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness + version (`0.2.0`) |
| `GET` | `/templates` | List curated starter templates |
| `POST` | `/plan` | Return a project plan (no file contents) |
| `POST` | `/generate` | Plan (or accept a plan) and generate file contents |
| `POST` | `/github/create-repo` | Create a GitHub repo for the authenticated user |

#### `POST /plan`

```json
{ "idea": "Build a FastAPI todo app", "template_id": "fastapi-minimal" }
```

`template_id` is optional. Response includes `project_name`, `stack`, `files`, and optionally `template_id` / `description`.

#### `POST /generate`

```json
{
  "idea": "Build a FastAPI todo app",
  "template_id": "fastapi-minimal",
  "plan": null
}
```

Omit `plan` to plan then generate, or pass a prior `/plan` body to skip re-planning. Response includes `project_name`, `stack`, and `files` (path → content map).

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

## Extension (v0.2)

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

Chat: `@creer <idea>` (when the host supports chat participants) or run **Create from Chat Prompt** with a `/creer …` style input.

### Settings

| Setting | Default | Description |
|---|---|---|
| `creer.backendUrl` | `http://localhost:8000` | Backend base URL |
| `creer.initGit` | `true` | Run `git init` + initial commit after scaffolding |
| `creer.previewBeforeWrite` | `true` | Show plan preview and confirm before generating/writing |
| `creer.createGitHubRepo` | `false` | After scaffolding, create a GitHub remote repository |
| `creer.githubPrivate` | `true` | Create GitHub repositories as private |
| `creer.githubToken` | `""` | GitHub PAT for create/push (prompted if empty when needed) |

## License

MIT
