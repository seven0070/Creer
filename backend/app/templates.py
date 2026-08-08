"""Curated starter templates (stub for v0.2 template system)."""

TEMPLATES: dict[str, dict] = {
    "fastapi-minimal": {
        "stack": "FastAPI + Uvicorn",
        "files": [
            "main.py",
            "requirements.txt",
            "README.md",
            ".env.example",
        ],
    },
}


def get_template(name: str) -> dict | None:
    return TEMPLATES.get(name)
