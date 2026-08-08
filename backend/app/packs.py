"""Installable template packs (JSON/YAML) for Creer v0.5."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import yaml

from app.templates import slugify
from app.validator import _reject_unsafe_path

# backend/packs — resolved relative to backend root (parent of app/)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
PACKS_DIR = _BACKEND_ROOT / "packs"

_PACK_FILE_SUFFIXES = (".json", ".yaml", ".yml")
_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


def _extra_packs_dir() -> Path | None:
    """Optional user packs directory via CREER_PACKS_DIR."""
    raw = os.getenv("CREER_PACKS_DIR", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def load_pack_file(path: Path | str) -> dict:
    """
    Load and validate a pack from a JSON or YAML file.

    Required: id, name, non-empty files list with safe relative paths.
    Optional: description, stack, version.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Pack file not found: {path}")

    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read pack file {path}: {exc}") from exc

    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in pack {path}: {exc}") from exc
    elif suffix in (".yaml", ".yml"):
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in pack {path}: {exc}") from exc
    else:
        raise ValueError(f"Unsupported pack file type: {path.suffix!r}")

    if not isinstance(data, dict):
        raise ValueError(f"Pack must be a mapping/object: {path}")

    pack_id = data.get("id")
    name = data.get("name")
    files = data.get("files")

    if not isinstance(pack_id, str) or not pack_id.strip():
        raise ValueError(f"Pack missing valid id: {path}")
    pack_id = pack_id.strip()
    if not _SAFE_ID.match(pack_id):
        raise ValueError(f"Invalid pack id {pack_id!r} in {path}")

    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Pack missing valid name: {path}")

    if not isinstance(files, list) or not files:
        raise ValueError(f"Pack must include a non-empty files list: {path}")

    validated_files: list[str] = []
    seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(f"Invalid file path in pack {path}: {entry!r}")
        fpath = entry.strip().replace("\\", "/")
        _reject_unsafe_path(fpath, label="pack file path")
        if fpath in seen:
            raise ValueError(f"Duplicate file path in pack {path}: {fpath!r}")
        seen.add(fpath)
        validated_files.append(fpath)

    version = data.get("version", "1.0.0")
    if version is not None and not isinstance(version, str):
        raise ValueError(f"Pack version must be a string: {path}")

    stack = data.get("stack", "")
    if stack is not None and not isinstance(stack, str):
        raise ValueError(f"Pack stack must be a string: {path}")

    description = data.get("description", "")
    if description is not None and not isinstance(description, str):
        raise ValueError(f"Pack description must be a string: {path}")

    return {
        "id": pack_id,
        "name": name.strip(),
        "description": (description or "").strip(),
        "stack": (stack or "").strip(),
        "version": (version or "1.0.0").strip(),
        "files": validated_files,
    }


def _load_packs_from_dir(directory: Path) -> dict[str, dict]:
    """Load all valid pack files from a directory (non-recursive)."""
    result: dict[str, dict] = {}
    if not directory.is_dir():
        return result

    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _PACK_FILE_SUFFIXES:
            continue
        try:
            pack = load_pack_file(path)
        except ValueError:
            # Skip invalid packs rather than failing the whole listing
            continue
        result[pack["id"]] = pack
    return result


def _all_packs() -> dict[str, dict]:
    """
    Merge built-in packs with optional CREER_PACKS_DIR.

    User packs override built-in packs on id collision.
    """
    packs = _load_packs_from_dir(PACKS_DIR)
    extra = _extra_packs_dir()
    if extra is not None:
        packs.update(_load_packs_from_dir(extra))
    return packs


def list_packs() -> list[dict]:
    """Return all available packs (built-in + user), sorted by id."""
    packs = _all_packs()
    return [dict(packs[k]) for k in sorted(packs.keys())]


def get_pack(pack_id: str) -> dict | None:
    """Look up a pack by id."""
    if not pack_id:
        return None
    pack = _all_packs().get(pack_id)
    return dict(pack) if pack else None


def apply_pack(pack_id: str, idea: str) -> dict:
    """
    Build a plan from an installable pack.

    Uses the pack's files and stack. Derives project_name by slugifying
    the idea (deterministic — no API key required).
    """
    pack = get_pack(pack_id)
    if pack is None:
        raise ValueError(f"Unknown pack_id: {pack_id!r}")

    project_name = slugify(idea)
    return {
        "project_name": project_name,
        "stack": pack["stack"],
        "files": list(pack["files"]),
        "pack_id": pack["id"],
        "description": pack.get("description", ""),
    }
