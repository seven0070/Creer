"""Open-source bake-ins merged into every scaffold (LICENSE, README, CI)."""

from __future__ import annotations


def _mit_license(project_name: str) -> str:
    holder = project_name.strip() if project_name and project_name.strip() else "Creer Scaffold"
    return f"""MIT License

Copyright (c) 2026 {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _default_readme(plan: dict) -> str:
    name = plan.get("project_name") or "project"
    stack = plan.get("stack") or ""
    desc = plan.get("description") or f"Scaffolded by Creer for {name}."
    lines = [
        f"# {name}",
        "",
        desc,
        "",
    ]
    if stack:
        lines.extend([f"**Stack:** {stack}", ""])
    lines.extend(
        [
            "## Getting started",
            "",
            "This project was generated with [Creer](https://github.com/).",
            "Install dependencies and follow stack-specific docs in this repo.",
            "",
        ]
    )
    return "\n".join(lines)


def _ci_workflow(plan: dict) -> str:
    stack = (plan.get("stack") or "").lower()
    paths = " ".join(plan.get("files") or []).lower()
    blob = f"{stack} {paths}"

    is_python = any(
        tok in blob
        for tok in ("python", "fastapi", "uvicorn", "pytest", "requirements.txt", "pyproject.toml")
    )
    is_node = any(
        tok in blob
        for tok in ("node", "express", "next", "npm", "package.json", "react")
    )

    if is_python:
        return """name: CI

on:
  push:
    branches: [main, master]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if [ -f pyproject.toml ]; then pip install -e ".[dev]" || pip install -e .; fi
          pip install pytest
      - name: Run tests
        run: pytest -q || echo "No tests yet — scaffold CI ok"
"""

    if is_node:
        return """name: CI

on:
  push:
    branches: [main, master]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
      - name: Install
        run: npm ci || npm install
      - name: Test
        run: npm test --if-present
"""

    return """name: CI

on:
  push:
    branches: [main, master]
  pull_request:

jobs:
  scaffold:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Scaffold CI
        run: echo "Creer scaffold CI — add stack-specific checks as the project grows"
"""


def apply_bakeins(plan: dict, files: dict[str, str]) -> dict[str, str]:
    """
    Merge open-source bake-ins into generated files.

    - LICENSE is always ensured (MIT, 2026).
    - README.md is created only if missing (never overwrite AI/template README).
    - .github/workflows/ci.yml is added if missing (stack heuristics).
    """
    out = dict(files)
    project_name = plan.get("project_name") or "Creer Scaffold"

    if "LICENSE" not in out:
        out["LICENSE"] = _mit_license(project_name)

    if "README.md" not in out:
        out["README.md"] = _default_readme(plan)

    ci_path = ".github/workflows/ci.yml"
    if ci_path not in out:
        out[ci_path] = _ci_workflow(plan)

    return out
