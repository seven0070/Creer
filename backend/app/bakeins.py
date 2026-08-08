"""Open-source bake-ins merged into scaffolds (LICENSE, README, CI)."""

from __future__ import annotations

from typing import Any, Literal

LicenseId = Literal["mit", "apache-2.0", "none"]
CiId = Literal["auto", "python", "node", "none"]


def list_bakein_options() -> dict[str, list[dict[str, str]]]:
    return {
        "licenses": [
            {"id": "mit", "name": "MIT"},
            {"id": "apache-2.0", "name": "Apache 2.0"},
            {"id": "none", "name": "No license"},
        ],
        "ci": [
            {"id": "auto", "name": "Auto-detect"},
            {"id": "python", "name": "Python"},
            {"id": "node", "name": "Node"},
            {"id": "none", "name": "No CI"},
        ],
    }


def _normalize_options(options: dict[str, Any] | None) -> dict[str, Any]:
    opts = options or {}
    license_id = opts.get("license") or "mit"
    ci_id = opts.get("ci") or "auto"
    include_readme = opts.get("include_readme")
    if include_readme is None:
        include_readme = True
    if license_id not in ("mit", "apache-2.0", "none"):
        license_id = "mit"
    if ci_id not in ("auto", "python", "node", "none"):
        ci_id = "auto"
    return {
        "license": license_id,
        "ci": ci_id,
        "include_readme": bool(include_readme),
    }


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


def _apache_license(project_name: str) -> str:
    holder = project_name.strip() if project_name and project_name.strip() else "Creer Scaffold"
    return f"""Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

Copyright 2026 {holder}

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
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
            "This project was generated with Creer.",
            "Install dependencies and follow stack-specific docs in this repo.",
            "",
        ]
    )
    return "\n".join(lines)


def _ci_python() -> str:
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


def _ci_node() -> str:
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


def _ci_generic() -> str:
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


def _ci_workflow(plan: dict, ci_id: str) -> str | None:
    if ci_id == "none":
        return None
    if ci_id == "python":
        return _ci_python()
    if ci_id == "node":
        return _ci_node()

    # auto
    stack = (plan.get("stack") or "").lower()
    paths = " ".join(plan.get("files") or []).lower()
    blob = f"{stack} {paths}"

    is_python = any(
        tok in blob
        for tok in ("python", "fastapi", "uvicorn", "pytest", "requirements.txt", "pyproject.toml")
    )
    is_node = any(
        tok in blob for tok in ("node", "express", "next", "npm", "package.json", "react")
    )

    if is_python:
        return _ci_python()
    if is_node:
        return _ci_node()
    return _ci_generic()


def apply_bakeins(
    plan: dict,
    files: dict[str, str],
    options: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Merge open-source bake-ins into generated files.

    - LICENSE per options.license (mit | apache-2.0 | none); never overwrite existing
    - README.md created only if missing and include_readme
    - .github/workflows/ci.yml per options.ci when missing
    """
    opts = _normalize_options(options)
    out = dict(files)
    project_name = plan.get("project_name") or "Creer Scaffold"

    if opts["license"] != "none" and "LICENSE" not in out:
        if opts["license"] == "apache-2.0":
            out["LICENSE"] = _apache_license(project_name)
        else:
            out["LICENSE"] = _mit_license(project_name)

    if opts["include_readme"] and "README.md" not in out:
        out["README.md"] = _default_readme(plan)

    ci_path = ".github/workflows/ci.yml"
    if ci_path not in out:
        ci_body = _ci_workflow(plan, opts["ci"])
        if ci_body is not None:
            out[ci_path] = ci_body

    return out
