"""Lightweight plan/file validation for v0.1."""

import re

SAFE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
SAFE_PATH = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[a-zA-Z0-9._/-]+$")


def validate_plan(plan: dict) -> None:
    name = plan.get("project_name")
    files = plan.get("files")

    if not isinstance(name, str) or not SAFE_NAME.match(name):
        raise ValueError(f"Invalid project_name: {name!r}")

    if not isinstance(files, list) or not files:
        raise ValueError("Plan must include a non-empty files list")

    for path in files:
        if not isinstance(path, str) or not SAFE_PATH.match(path):
            raise ValueError(f"Unsafe or invalid file path: {path!r}")


def validate_files(files: dict) -> None:
    if not isinstance(files, dict) or not files:
        raise ValueError("Generated files must be a non-empty mapping")
    for path, content in files.items():
        if not isinstance(path, str) or not SAFE_PATH.match(path):
            raise ValueError(f"Unsafe or invalid file path: {path!r}")
        if not isinstance(content, str):
            raise ValueError(f"File content for {path!r} must be a string")
