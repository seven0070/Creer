"""Installable template packs (JSON/YAML) for Creer v0.6 — including remote install."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

from app.templates import slugify
from app.validator import _reject_unsafe_path

# backend/packs — resolved relative to backend root (parent of app/)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
PACKS_DIR = _BACKEND_ROOT / "packs"
INSTALLED_DIR = PACKS_DIR / "installed"

_PACK_FILE_SUFFIXES = (".json", ".yaml", ".yml")
_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")

MAX_DOWNLOAD_BYTES = 1_000_000
FETCH_TIMEOUT_SECONDS = 30.0


class PackConflictError(Exception):
    """Raised when installing a pack id that already exists and overwrite is false."""


class PackNotInstalledError(Exception):
    """Raised when uninstall targets a pack that is not in the writable install dir."""


def _extra_packs_dir() -> Path | None:
    """Optional user packs directory via CREER_PACKS_DIR."""
    raw = os.getenv("CREER_PACKS_DIR", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def writable_packs_dir() -> Path:
    """
    Directory where remotely installed packs are written.

    Prefer CREER_PACKS_DIR when set; otherwise backend/packs/installed/.
    """
    extra = _extra_packs_dir()
    if extra is not None:
        return extra
    return INSTALLED_DIR


def validate_pack_dict(data: dict, *, source: str = "<pack>") -> dict:
    """
    Validate a pack mapping and return a normalized dict.

    Required: id, name, non-empty files list with safe relative paths.
    Optional: description, stack, version.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Pack must be a mapping/object: {source}")

    pack_id = data.get("id")
    name = data.get("name")
    files = data.get("files")

    if not isinstance(pack_id, str) or not pack_id.strip():
        raise ValueError(f"Pack missing valid id: {source}")
    pack_id = pack_id.strip()
    if not _SAFE_ID.match(pack_id):
        raise ValueError(f"Invalid pack id {pack_id!r} in {source}")

    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Pack missing valid name: {source}")

    if not isinstance(files, list) or not files:
        raise ValueError(f"Pack must include a non-empty files list: {source}")

    validated_files: list[str] = []
    seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(f"Invalid file path in pack {source}: {entry!r}")
        fpath = entry.strip().replace("\\", "/")
        _reject_unsafe_path(fpath, label="pack file path")
        if fpath in seen:
            raise ValueError(f"Duplicate file path in pack {source}: {fpath!r}")
        seen.add(fpath)
        validated_files.append(fpath)

    version = data.get("version", "1.0.0")
    if version is not None and not isinstance(version, str):
        raise ValueError(f"Pack version must be a string: {source}")

    stack = data.get("stack", "")
    if stack is not None and not isinstance(stack, str):
        raise ValueError(f"Pack stack must be a string: {source}")

    description = data.get("description", "")
    if description is not None and not isinstance(description, str):
        raise ValueError(f"Pack description must be a string: {source}")

    return {
        "id": pack_id,
        "name": name.strip(),
        "description": (description or "").strip(),
        "stack": (stack or "").strip(),
        "version": (version or "1.0.0").strip(),
        "files": validated_files,
    }


def _detect_pack_format(
    hint_filename: str | None = None,
    content_type: str | None = None,
    text: str | None = None,
) -> str:
    """Return 'json' or 'yaml' based on filename, Content-Type, and/or body sniff."""
    if hint_filename:
        lower = hint_filename.lower().split("?", 1)[0]
        if lower.endswith(".json"):
            return "json"
        if lower.endswith(".yaml") or lower.endswith(".yml"):
            return "yaml"

    if content_type:
        ct = content_type.split(";", 1)[0].strip().lower()
        if ct in ("application/json", "text/json"):
            return "json"
        if ct in (
            "application/yaml",
            "application/x-yaml",
            "text/yaml",
            "text/x-yaml",
        ):
            return "yaml"

    if text is not None:
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            return "json"

    # Default: try JSON first via caller; prefer yaml when ambiguous after sniff
    return "yaml" if text is not None else "json"


def parse_pack_content(
    text_or_bytes: str | bytes,
    hint_filename: str | None = None,
    *,
    content_type: str | None = None,
) -> dict:
    """Parse and validate pack content from text or bytes."""
    if isinstance(text_or_bytes, bytes):
        try:
            text = text_or_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Pack content is not valid UTF-8: {exc}") from exc
    else:
        text = text_or_bytes

    source = hint_filename or "<pack>"
    fmt = _detect_pack_format(hint_filename, content_type, text)

    data: object
    if fmt == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            # Fallback: maybe mis-detected YAML
            if hint_filename and hint_filename.lower().endswith(".json"):
                raise ValueError(f"Invalid JSON in pack {source}: {exc}") from exc
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as yexc:
                raise ValueError(f"Invalid pack content {source}: {exc}") from yexc
    else:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in pack {source}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Pack must be a mapping/object: {source}")

    return validate_pack_dict(data, source=source)


def parse_pack_bytes(
    data: bytes,
    hint_filename: str | None = None,
    *,
    content_type: str | None = None,
) -> dict:
    """Parse pack bytes (alias of parse_pack_content for bytes)."""
    return parse_pack_content(data, hint_filename, content_type=content_type)


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
    if suffix not in _PACK_FILE_SUFFIXES:
        raise ValueError(f"Unsupported pack file type: {path.suffix!r}")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read pack file {path}: {exc}") from exc

    return parse_pack_content(text, hint_filename=path.name)


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
    Merge built-in packs, installed packs, and optional CREER_PACKS_DIR.

    Later sources override earlier ones on id collision:
    built-in → installed/ → CREER_PACKS_DIR.
    """
    packs = _load_packs_from_dir(PACKS_DIR)
    packs.update(_load_packs_from_dir(INSTALLED_DIR))
    extra = _extra_packs_dir()
    if extra is not None and extra.resolve() != INSTALLED_DIR.resolve():
        packs.update(_load_packs_from_dir(extra))
    return packs


def list_packs() -> list[dict]:
    """Return all available packs (built-in + installed + user), sorted by id."""
    packs = _all_packs()
    return [dict(packs[k]) for k in sorted(packs.keys())]


def get_pack(pack_id: str) -> dict | None:
    """Look up a pack by id."""
    if not pack_id:
        return None
    pack = _all_packs().get(pack_id)
    return dict(pack) if pack else None


def install_pack(pack: dict, *, overwrite: bool = False) -> dict:
    """
    Write a validated pack dict as ``{id}.json`` into the writable packs dir.

    Raises PackConflictError if the id already exists and overwrite is False.
    """
    validated = validate_pack_dict(pack, source="<install>")
    pack_id = validated["id"]

    if get_pack(pack_id) is not None and not overwrite:
        raise PackConflictError(f"Pack already exists: {pack_id!r}")

    target_dir = writable_packs_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{pack_id}.json"
    target.write_text(
        json.dumps(validated, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return dict(validated)


def install_pack_from_bytes(
    data: bytes,
    *,
    hint_filename: str = "pack.json",
    content_type: str | None = None,
    overwrite: bool = False,
) -> dict:
    """Parse pack bytes and install into the writable packs dir."""
    pack = parse_pack_bytes(data, hint_filename, content_type=content_type)
    return install_pack(pack, overwrite=overwrite)


def uninstall_pack(pack_id: str) -> bool:
    """
    Remove an installed pack from the writable dir only.

    Returns True if a file was deleted.
    Raises PackNotInstalledError if the pack is not present under the writable dir
    (built-in shipped packs cannot be deleted this way).
    """
    if not pack_id or not _SAFE_ID.match(pack_id):
        raise ValueError(f"Invalid pack id: {pack_id!r}")

    target_dir = writable_packs_dir()
    if not target_dir.is_dir():
        raise PackNotInstalledError(f"Pack not installed (writable): {pack_id!r}")

    candidates = [
        target_dir / f"{pack_id}.json",
        target_dir / f"{pack_id}.yaml",
        target_dir / f"{pack_id}.yml",
    ]
    deleted = False
    for path in candidates:
        if path.is_file():
            path.unlink()
            deleted = True

    if not deleted:
        raise PackNotInstalledError(f"Pack not installed (writable): {pack_id!r}")
    return True


def validate_remote_pack_url(url: str) -> str:
    """Allow only http/https URLs with a host. Returns the stripped URL."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url is required")
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Only http/https URLs are allowed, got scheme {parsed.scheme!r}"
        )
    if not parsed.hostname:
        raise ValueError("URL must include a host")
    return url


def _hint_filename_from_url(url: str) -> str:
    path = urlparse(url).path or ""
    name = Path(path).name
    if name and any(name.lower().endswith(s) for s in _PACK_FILE_SUFFIXES):
        return name
    return "pack.json"


def fetch_pack_bytes(url: str) -> tuple[bytes, str | None, str]:
    """
    Download pack content from a remote URL.

    Returns (body, content_type, hint_filename).
    Enforces http(s), ~30s timeout, and 1MB max size.
    """
    url = validate_remote_pack_url(url)
    hint = _hint_filename_from_url(url)

    try:
        with httpx.Client(
            timeout=FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            with client.stream("GET", url) as resp:
                if resp.status_code >= 400:
                    raise ValueError(
                        f"Failed to fetch pack ({resp.status_code}): {url}"
                    )
                content_type = resp.headers.get("content-type")
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise ValueError(
                            f"Pack download exceeds {MAX_DOWNLOAD_BYTES} byte limit"
                        )
                    chunks.append(chunk)
                body = b"".join(chunks)
    except httpx.HTTPError as exc:
        raise ValueError(f"Failed to fetch pack URL: {exc}") from exc

    if not body:
        raise ValueError("Pack download was empty")

    return body, content_type, hint


def install_pack_from_url(url: str, *, overwrite: bool = False) -> dict:
    """Fetch a remote pack URL, validate, and install."""
    body, content_type, hint = fetch_pack_bytes(url)
    return install_pack_from_bytes(
        body,
        hint_filename=hint,
        content_type=content_type,
        overwrite=overwrite,
    )


def marketplace_catalog() -> list[dict]:
    """
    Static curated marketplace catalog.

    Bundled entries mirror the three shipped packs (offline/demo).
    Remote entries are illustrative placeholders — do not require network in tests.
    """
    return [
        {
            "id": "fastapi-crud",
            "name": "FastAPI CRUD",
            "description": "FastAPI starter with models, CRUD routes, and uvicorn entrypoint.",
            "source": "bundled",
            "url": None,
        },
        {
            "id": "python-lib",
            "name": "Python Library",
            "description": "Publishable Python library with pyproject, package layout, and tests.",
            "source": "bundled",
            "url": None,
        },
        {
            "id": "express-ts",
            "name": "Express TypeScript",
            "description": "Express API in TypeScript with tsconfig and basic router.",
            "source": "bundled",
            "url": None,
        },
        {
            "id": "demo-remote",
            "name": "Demo Remote Pack",
            "description": (
                "Example remote pack URL (placeholder). Install via POST /packs/install "
                "with this url — for demos/docs only; tests should mock the fetch."
            ),
            "url": (
                "https://raw.githubusercontent.com/example/creer-packs/main/"
                "demo-remote.json"
            ),
            "source": "remote",
        },
        {
            "id": "hello-cli",
            "name": "Hello CLI Pack",
            "description": (
                "Example remote CLI starter pack URL (placeholder for marketplace demos)."
            ),
            "url": (
                "https://raw.githubusercontent.com/example/creer-packs/main/"
                "hello-cli.yaml"
            ),
            "source": "remote",
        },
    ]


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
