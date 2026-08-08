"""Telemetry-free quality gates for generated project trees."""

from __future__ import annotations

from typing import Any

MANIFEST_NAMES = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "Pipfile",
    "go.mod",
    "Cargo.toml",
    "composer.json",
}


def run_quality_gates(
    plan: dict,
    files: dict[str, str],
    *,
    expect_license: bool = True,
) -> list[dict[str, Any]]:
    """
    Return light static issues for a generated tree.

    Severities: error | warning | info
    """
    issues: list[dict[str, Any]] = []

    paths = list(files.keys())
    seen: set[str] = set()
    for path in paths:
        if path in seen:
            issues.append(
                {
                    "code": "path_duplicate",
                    "severity": "error",
                    "path": path,
                    "message": f"Duplicate path in generated tree: {path}",
                }
            )
        seen.add(path)

    for path, content in files.items():
        if not isinstance(content, str) or not content.strip():
            issues.append(
                {
                    "code": "empty_file",
                    "severity": "warning",
                    "path": path,
                    "message": f"File is empty or whitespace-only: {path}",
                }
            )

    if "README.md" not in files and "README" not in files:
        issues.append(
            {
                "code": "missing_readme",
                "severity": "warning",
                "message": "No README.md in generated tree",
            }
        )

    if expect_license and "LICENSE" not in files:
        issues.append(
            {
                "code": "missing_license",
                "severity": "warning",
                "message": "LICENSE missing after bake-ins",
            }
        )

    lower_names = {p.split("/")[-1] for p in files}
    if not (lower_names & MANIFEST_NAMES):
        issues.append(
            {
                "code": "no_manifest",
                "severity": "info",
                "message": "No dependency manifest (requirements.txt / package.json / …)",
            }
        )

    # Plan vs files: warn if plan listed paths that weren't generated
    planned = plan.get("files") or []
    if isinstance(planned, list):
        missing = [p for p in planned if isinstance(p, str) and p not in files]
        for path in missing[:20]:
            issues.append(
                {
                    "code": "missing_planned_file",
                    "severity": "warning",
                    "path": path,
                    "message": f"Planned file was not generated: {path}",
                }
            )

    return issues


def has_errors(issues: list[dict[str, Any]]) -> bool:
    return any(i.get("severity") == "error" for i in issues)
