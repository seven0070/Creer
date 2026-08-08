"""Production-grade plan/file validation for Creer v0.2."""

from __future__ import annotations

import re

# project_name: lowercase start, alphanumerics/hyphen/underscore/dot, no spaces
SAFE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")

# Relative paths only: no leading slash, no .. segments, safe chars
SAFE_PATH = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[a-zA-Z0-9._/-]+$")

# Windows drive / UNC-ish prefixes
WINDOWS_DRIVE = re.compile(r"^[a-zA-Z]:")

# Plan file cap; generated set may also include bake-ins (LICENSE, CI, optional README).
MAX_FILES = 45
MAX_CONTENT_BYTES_PER_FILE = 200_000
MAX_TOTAL_CONTENT_BYTES = 2_000_000


def _reject_unsafe_path(path: str, *, label: str = "file path") -> None:
    if not isinstance(path, str):
        raise ValueError(f"Invalid {label}: must be a string, got {type(path).__name__}")

    if "\x00" in path:
        raise ValueError(f"Unsafe {label}: contains null byte: {path!r}")

    if path.startswith("/") or path.startswith("\\"):
        raise ValueError(f"Unsafe {label}: absolute paths are not allowed: {path!r}")

    if WINDOWS_DRIVE.match(path) or path.startswith("\\\\"):
        raise ValueError(f"Unsafe {label}: Windows drive/UNC paths are not allowed: {path!r}")

    # Normalize separators for .. checks
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if ".." in parts or any(p == ".." for p in parts):
        raise ValueError(f"Unsafe {label}: path traversal ('..') is not allowed: {path!r}")

    if not SAFE_PATH.match(path):
        raise ValueError(f"Unsafe or invalid {label}: {path!r}")


def validate_plan(plan: dict) -> None:
    if not isinstance(plan, dict):
        raise ValueError("Plan must be a dictionary")

    name = plan.get("project_name")
    files = plan.get("files")

    if not isinstance(name, str) or not name:
        raise ValueError(f"Invalid project_name: {name!r}")

    if " " in name:
        raise ValueError(f"Invalid project_name: spaces are not allowed: {name!r}")

    if "\x00" in name:
        raise ValueError(f"Invalid project_name: contains null byte: {name!r}")

    if not SAFE_NAME.match(name):
        raise ValueError(
            f"Invalid project_name: must be 1–64 chars, start with alphanumeric, "
            f"and contain only [a-zA-Z0-9._-]: {name!r}"
        )

    if not isinstance(files, list) or not files:
        raise ValueError("Plan must include a non-empty files list")

    if len(files) > MAX_FILES:
        raise ValueError(f"Plan exceeds max file count ({MAX_FILES}): got {len(files)}")

    seen: set[str] = set()
    for path in files:
        _reject_unsafe_path(path)
        if path in seen:
            raise ValueError(f"Duplicate file path in plan: {path!r}")
        seen.add(path)


def validate_files(files: dict) -> None:
    if not isinstance(files, dict) or not files:
        raise ValueError("Generated files must be a non-empty mapping")

    if len(files) > MAX_FILES:
        raise ValueError(f"Generated files exceed max file count ({MAX_FILES}): got {len(files)}")

    total_bytes = 0
    for path, content in files.items():
        _reject_unsafe_path(path)

        if not isinstance(content, str):
            raise ValueError(f"File content for {path!r} must be a string")

        if "\x00" in content:
            raise ValueError(f"File content for {path!r} contains null bytes")

        size = len(content.encode("utf-8"))
        if size > MAX_CONTENT_BYTES_PER_FILE:
            raise ValueError(
                f"File {path!r} exceeds max content size "
                f"({MAX_CONTENT_BYTES_PER_FILE} bytes): {size} bytes"
            )
        total_bytes += size

    if total_bytes > MAX_TOTAL_CONTENT_BYTES:
        raise ValueError(
            f"Total content exceeds max ({MAX_TOTAL_CONTENT_BYTES} bytes): {total_bytes} bytes"
        )
