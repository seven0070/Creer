"""Curated starter templates for Creer v0.2."""

from __future__ import annotations

import re

TEMPLATES: dict[str, dict] = {
    "fastapi-minimal": {
        "id": "fastapi-minimal",
        "name": "FastAPI Minimal",
        "description": "Minimal FastAPI API with uvicorn, health check, and env config.",
        "stack": "FastAPI + Uvicorn",
        "files": [
            "main.py",
            "requirements.txt",
            "README.md",
            ".env.example",
            ".gitignore",
        ],
    },
    "express-api": {
        "id": "express-api",
        "name": "Express API",
        "description": "Node.js Express REST API with a basic router and scripts.",
        "stack": "Node.js + Express",
        "files": [
            "package.json",
            "src/index.js",
            "src/routes/health.js",
            "README.md",
            ".gitignore",
            ".env.example",
        ],
    },
    "nextjs-app": {
        "id": "nextjs-app",
        "name": "Next.js App",
        "description": "Next.js App Router starter with a home page and package manifest.",
        "stack": "Next.js + React",
        "files": [
            "package.json",
            "next.config.js",
            "tsconfig.json",
            "app/layout.tsx",
            "app/page.tsx",
            "app/globals.css",
            "README.md",
            ".gitignore",
        ],
    },
    "python-cli": {
        "id": "python-cli",
        "name": "Python CLI",
        "description": "Python command-line tool with argparse entrypoint and packaging basics.",
        "stack": "Python CLI",
        "files": [
            "pyproject.toml",
            "src/__init__.py",
            "src/cli.py",
            "src/__main__.py",
            "README.md",
            ".gitignore",
        ],
    },
    "static-site": {
        "id": "static-site",
        "name": "Static Site",
        "description": "Simple static HTML/CSS/JS site ready to open in a browser.",
        "stack": "HTML + CSS + JavaScript",
        "files": [
            "index.html",
            "styles.css",
            "script.js",
            "README.md",
        ],
    },
}


def slugify(text: str) -> str:
    """Derive a filesystem-safe project name from free text."""
    slug = text.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = "project"
    return slug[:64]


def list_templates() -> list[dict]:
    """Return all curated templates as a list of dicts."""
    return [dict(t) for t in TEMPLATES.values()]


def get_template(template_id: str) -> dict | None:
    """Look up a template by id."""
    tmpl = TEMPLATES.get(template_id)
    return dict(tmpl) if tmpl else None


def apply_template(template_id: str, idea: str) -> dict:
    """
    Build a plan from a curated template.

    Uses the template's files and stack. Derives project_name by slugifying
    the idea (deterministic — no API key required).
    """
    tmpl = get_template(template_id)
    if tmpl is None:
        raise ValueError(f"Unknown template_id: {template_id!r}")

    project_name = slugify(idea)
    return {
        "project_name": project_name,
        "stack": tmpl["stack"],
        "files": list(tmpl["files"]),
        "template_id": tmpl["id"],
        "description": tmpl.get("description", ""),
    }
