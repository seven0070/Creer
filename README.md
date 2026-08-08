# Creer

AI-powered repo scaffolding inside your workspace.

Describe an idea → Creer plans a clean structure → writes files into your VS Code workspace → optionally initializes git.

## Architecture

```
creer/
├── backend/     # Python FastAPI AI engine
└── extension/   # VS Code extension
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- OpenAI API key
- VS Code / Cursor

## Backend (v0.1)

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# set OPENAI_API_KEY in .env
uvicorn main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Generate:

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"idea":"Build a FastAPI todo app"}'
```

## Extension (v0.1)

```bash
cd extension
npm install
npm run compile
```

In VS Code / Cursor:

1. Open the `extension/` folder
2. Press **F5** (Run Extension)
3. In the Extension Development Host, open a workspace folder
4. Command Palette → **Creer: Create New Repo**
5. Enter an idea

Settings:

| Setting | Default | Description |
|---|---|---|
| `creer.backendUrl` | `http://localhost:8000` | Backend base URL |
| `creer.initGit` | `true` | Run `git init` + initial commit after scaffolding |

## License

MIT
