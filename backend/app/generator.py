"""File content generation — LLM-driven or offline stubs."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from config import CREER_OFFLINE, MODEL, OPENAI_API_KEY, OPENAI_BASE_URL
from app.llm import _get_client


def _use_offline(plan: dict) -> bool:
    """True when CREER_OFFLINE, or when no LLM endpoint is configured and a plan exists."""
    if CREER_OFFLINE:
        return True
    # Local OpenAI-compatible servers (Ollama, etc.) may omit a real API key.
    if OPENAI_BASE_URL:
        return False
    if not OPENAI_API_KEY and plan.get("files"):
        return True
    return False


def _stub_content(file_path: str, plan: dict) -> str:
    """Deterministic stub content for offline / template-only generation."""
    name = plan.get("project_name") or "project"
    stack = plan.get("stack") or ""
    desc = plan.get("description") or f"Scaffolded project: {name}."
    base = file_path.rsplit("/", 1)[-1]
    base_lower = base.lower()
    ext = base_lower.rsplit(".", 1)[-1] if "." in base_lower else ""

    if base_lower == "readme.md":
        lines = [f"# {name}", "", desc, ""]
        if stack:
            lines.extend([f"**Stack:** {stack}", ""])
        lines.extend(
            [
                "## Status",
                "",
                "Generated in offline / template-only mode. Replace stubs with real implementation.",
                "",
            ]
        )
        return "\n".join(lines)

    if base_lower == "requirements.txt":
        if "fastapi" in stack.lower() or "uvicorn" in stack.lower():
            return "fastapi>=0.115.0\nuvicorn[standard]>=0.32.0\npython-dotenv>=1.0.0\n"
        return "# TODO: add dependencies\n"

    if base_lower == "package.json":
        pkg = {
            "name": name,
            "version": "0.1.0",
            "private": True,
            "scripts": {
                "start": "node src/index.js",
                "test": "echo \"No tests yet\" && exit 0",
            },
            "dependencies": {},
        }
        if "express" in stack.lower():
            pkg["dependencies"]["express"] = "^4.21.0"
            pkg["scripts"]["start"] = "node src/index.js"
        if "next" in stack.lower():
            pkg["dependencies"]["next"] = "^14.2.0"
            pkg["dependencies"]["react"] = "^18.3.0"
            pkg["dependencies"]["react-dom"] = "^18.3.0"
            pkg["scripts"] = {
                "dev": "next dev",
                "build": "next build",
                "start": "next start",
                "test": "echo \"No tests yet\" && exit 0",
            }
        return json.dumps(pkg, indent=2) + "\n"

    if base_lower == "pyproject.toml":
        return f"""[project]
name = "{name}"
version = "0.1.0"
description = "{desc.replace(chr(34), "'")}"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
{name} = "src.cli:main"
"""

    if base_lower in (".gitignore",):
        return (
            "__pycache__/\n*.py[cod]\n.venv/\nvenv/\n.env\n"
            "node_modules/\ndist/\nbuild/\n.DS_Store\n"
        )

    if base_lower in (".env.example",):
        return "# Example environment variables\n# KEY=value\n"

    if base_lower == "tsconfig.json":
        return json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2017",
                    "lib": ["dom", "dom.iterable", "esnext"],
                    "allowJs": True,
                    "skipLibCheck": True,
                    "strict": True,
                    "module": "esnext",
                    "moduleResolution": "bundler",
                    "jsx": "preserve",
                    "noEmit": True,
                    "incremental": True,
                },
                "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
                "exclude": ["node_modules"],
            },
            indent=2,
        ) + "\n"

    if base_lower == "next.config.js":
        return "/** @type {import('next').NextConfig} */\nconst nextConfig = {};\nmodule.exports = nextConfig;\n"

    if ext in ("py",):
        if base_lower == "main.py" and "fastapi" in stack.lower():
            return (
                '"""Application entrypoint."""\n\n'
                "from fastapi import FastAPI\n\n"
                f'app = FastAPI(title="{name}")\n\n\n'
                '@app.get("/health")\n'
                "def health():\n"
                '    return {"status": "ok"}\n\n\n'
                "# TODO: implement\n"
            )
        return f'"""{file_path}"""\n\n# TODO: implement\n'

    if ext in ("js", "mjs", "cjs"):
        return f"// {file_path}\n// TODO: implement\n"

    if ext in ("ts", "tsx"):
        return f"// {file_path}\n// TODO: implement\n"

    if ext == "css":
        return f"/* {file_path} */\n/* TODO: implement */\n"

    if ext in ("html", "htm"):
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="utf-8" />\n'
            f"  <title>{name}</title>\n"
            '  <link rel="stylesheet" href="styles.css" />\n'
            "</head>\n"
            "<body>\n"
            f"  <h1>{name}</h1>\n"
            "  <!-- TODO: implement -->\n"
            '  <script src="script.js"></script>\n'
            "</body>\n"
            "</html>\n"
        )

    if ext in ("yml", "yaml"):
        return f"# {file_path}\n# TODO: implement\n"

    if ext == "json":
        return "{}\n"

    if ext == "toml":
        return f"# {file_path}\n# TODO: implement\n"

    # Default: comment-style stub
    return f"# TODO: implement ({file_path})\n"


def _strip_fences(content: str) -> str:
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    return content


def _generate_one_llm(file_path: str, plan: dict) -> str:
    prompt = f"""
Generate the full content for file: {file_path}

Project Stack: {plan.get("stack", "")}
Project Name: {plan.get("project_name", "")}

Follow best practices.
Return ONLY the file content — no markdown fences, no explanation.
"""
    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    content = response.choices[0].message.content or ""
    return _strip_fences(content)


def generate_files_iter(plan: dict) -> Iterator[tuple[dict[str, Any], dict[str, str]]]:
    """
    Yield (event_dict, partial_files) progress while generating.

    Events:
      - file / generating
      - file / done (with bytes)
    Does not yield start/done/error — caller owns those.
    """
    files_output: dict[str, str] = {}
    file_list = list(plan["files"])
    total = len(file_list)
    offline = _use_offline(plan)

    for index, file_path in enumerate(file_list, start=1):
        yield (
            {
                "event": "file",
                "index": index,
                "total": total,
                "path": file_path,
                "status": "generating",
            },
            dict(files_output),
        )

        if offline:
            content = _stub_content(file_path, plan)
        else:
            content = _generate_one_llm(file_path, plan)

        files_output[file_path] = content
        yield (
            {
                "event": "file",
                "index": index,
                "total": total,
                "path": file_path,
                "status": "done",
                "bytes": len(content.encode("utf-8")),
            },
            dict(files_output),
        )


def generate_files(plan: dict) -> dict[str, str]:
    """Generate file contents one-by-one from a project plan."""
    files_output: dict[str, str] = {}
    for _event, partial in generate_files_iter(plan):
        files_output = partial
    return files_output
