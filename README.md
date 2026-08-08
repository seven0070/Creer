# Creer — AI-powered repo scaffolding in VS Code

> Describe an idea → get a clean, ready-to-run project inside your workspace.

Creer is a minimal, open-source foundation (v0.1): a **FastAPI Python backend** that plans & generates code via OpenAI, and a **VS Code extension** that writes the files into your workspace.

No agents. No graphs. Just prompt → plan → files.

```
creer/
├── backend/     # FastAPI AI engine (planner, generator, validator)
└── extension/   # VS Code extension (Creer: Create New Repo)
```

---

## ✨ v0.1 Features

- **Backend**
  - `POST /generate` — takes `{ idea: string }`, returns `{ project_name, files: {path: content} }`
  - `GET /health` — liveness check
  - `GET /` — info
  - Lazy OpenAI client (server boots without key, fails clearly on generate)
  - Path/plan validation (prevents `..`, absolute paths, hidden files, limits 60 files)
  - CORS enabled

- **Extension**
  - Command: **Creer: Create New Repo**
  - InputBox for idea, progress notification
  - Writes files to `<workspace>/<project_name>/`
  - Overwrite confirmation, git init + initial commit (configurable)
  - Config: `creer.backendUrl` (default `http://localhost:8000`), `creer.initGit`

---

## 🚀 Quickstart

### 1) Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # add your OPENAI_API_KEY
# OR export OPENAI_API_KEY=sk-...
uvicorn main:app --reload --port 8000
```

Test:
```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}

curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"idea":"Build a FastAPI todo app with JWT auth and SQLite"}'
```

### 2) Extension

```bash
cd extension
npm install
npm run compile   # or npm run watch
```

Then **F5** (Run Extension) → new VS Code window → **File → Open Folder** → `Cmd/Ctrl+Shift+P` → `Creer: Create New Repo` → describe idea.

Files land in `<workspace>/<project_name>/`. If `creer.initGit` is true, `git init && git add . && git commit` runs automatically.

---

## ⚙️ Configuration

| Setting | Default | Desc |
|---|---|---|
| `creer.backendUrl` | `http://localhost:8000` | Backend URL |
| `creer.initGit` | `true` | Auto git init |

Edit in `Settings (JSON)` or VS Code Settings UI.

---

## 🏗️ Architecture

**Backend flow:** `idea` → `planner.plan_project` (LLM → JSON `{project_name, stack, files}` + validate) → `generator.generate_files` (LLM per file → validated dict) → return.

```
Client (extension)
  -> POST /generate { idea }
  -> LLM planner (gpt-4o-mini, temp 0.2)
  -> validator.validate_plan
  -> LLM generator per file (temp 0.3)
  -> { project_name, files }
  -> extension writes to disk
```

Modules:
- `backend/config.py` — env loading
- `backend/app/planner.py` — JSON planning
- `backend/app/generator.py` — file generation
- `backend/app/validator.py` — path safety
- `backend/app/templates.py` — stub for v0.2 curated templates
- `backend/main.py` — FastAPI app

---

## 🔒 Security (v0.1)

- No `..`, no absolute paths, no `//`, no `\`
- Blocks `.git`, `node_modules`, hidden folders
- `project_name` slugified, `files` limited to 60, each path max 200 chars
- Extension double-checks `path.relative` stays inside project

---

## 🧪 Validate Install

Backend boots without key:
```bash
curl http://localhost:8000/health  # should be ok even if OPENAI_API_KEY missing
```

Missing key error on generate:
```bash
curl -X POST http://localhost:8000/generate -H "Content-Type: application/json" -d '{"idea":"test hello world app"}'
# 400 {"detail":"OPENAI_API_KEY not set..."}
```

---

## 🗺️ Roadmap

**v0.1 ✅** — Foundation (this release)
**v0.2** — Preview before write, curated templates, overwrite diff, GitHub push, `/creer` chat command

See [PLAN.md](PLAN.md) for full v0.2 spec.

---

## 🤝 Contributing

- `backend`: `pip install -r requirements.txt && uvicorn main:app --reload`
- `extension`: `npm install && npm run compile` → F5

PRs welcome. Keep it simple, production-ready.

---

## 📄 License

MIT — see [LICENSE](LICENSE)
