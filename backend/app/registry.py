"""Self-hosted pack registry — searchable catalog + downloadable pack JSON."""

from __future__ import annotations

import json
from typing import Any

from config import CREER_PUBLIC_BASE_URL
from app.packs import (
    INSTALLED_DIR,
    PACKS_DIR,
    _extra_packs_dir,
    _load_packs_from_dir,
    get_pack,
    list_packs,
    marketplace_catalog,
)
from app.peer_trust import sign_payload


def _download_path(pack_id: str) -> str:
    return f"/registry/packs/{pack_id}/download"


def _absolute_or_relative(path: str) -> str:
    base = (CREER_PUBLIC_BASE_URL or "").rstrip("/")
    if base:
        return f"{base}{path}"
    return path


def _packs_with_source() -> list[dict[str, Any]]:
    """
    Build pack list with source tags.

    Precedence matches list_packs merge: built-in → installed → CREER_PACKS_DIR.
    Final source reflects the winning file location.
    """
    sources: dict[str, str] = {}
    packs: dict[str, dict] = {}

    for pack_id, pack in _load_packs_from_dir(PACKS_DIR).items():
        packs[pack_id] = pack
        sources[pack_id] = "bundled"

    for pack_id, pack in _load_packs_from_dir(INSTALLED_DIR).items():
        packs[pack_id] = pack
        sources[pack_id] = "installed"

    extra = _extra_packs_dir()
    if extra is not None and extra.resolve() != INSTALLED_DIR.resolve():
        for pack_id, pack in _load_packs_from_dir(extra).items():
            packs[pack_id] = pack
            sources[pack_id] = "installed"

    items: list[dict[str, Any]] = []
    for pack_id in sorted(packs.keys()):
        pack = dict(packs[pack_id])
        download = _absolute_or_relative(_download_path(pack_id))
        items.append(
            {
                "id": pack["id"],
                "name": pack.get("name") or pack["id"],
                "description": pack.get("description") or "",
                "stack": pack.get("stack") or "",
                "version": pack.get("version") or "1.0.0",
                "source": sources.get(pack_id, "bundled"),
                "files": list(pack.get("files") or []),
                "download_url": download,
                "install_url": download,
            }
        )
    return items


def list_registry(
    *,
    q: str | None = None,
    source: str = "all",
) -> dict[str, Any]:
    """Searchable registry listing."""
    source_filter = (source or "all").lower().strip()
    if source_filter not in ("all", "bundled", "installed"):
        source_filter = "all"

    items = _packs_with_source()
    if source_filter != "all":
        items = [i for i in items if i["source"] == source_filter]

    query = (q or "").strip().lower()
    if query:
        def matches(item: dict[str, Any]) -> bool:
            blob = " ".join(
                [
                    str(item.get("id") or ""),
                    str(item.get("name") or ""),
                    str(item.get("description") or ""),
                    str(item.get("stack") or ""),
                ]
            ).lower()
            return query in blob

        items = [i for i in items if matches(i)]

    return sign_payload(
        {
            "version": "1.4.0",
            "base_url": CREER_PUBLIC_BASE_URL or None,
            "items": items,
        }
    )


def get_registry_pack(pack_id: str) -> dict[str, Any] | None:
    for item in _packs_with_source():
        if item["id"] == pack_id:
            # Include full pack body fields
            pack = get_pack(pack_id)
            if pack is None:
                return None
            out = dict(item)
            out["files"] = list(pack.get("files") or [])
            out["stack"] = pack.get("stack") or out.get("stack") or ""
            out["description"] = pack.get("description") or out.get("description") or ""
            return out
    return None


def pack_download_bytes(pack_id: str) -> tuple[bytes, str] | None:
    """Return (json_bytes, filename) for a pack, or None."""
    pack = get_pack(pack_id)
    if pack is None:
        return None
    # Portable JSON export
    payload = {
        "id": pack["id"],
        "name": pack.get("name") or pack["id"],
        "description": pack.get("description") or "",
        "stack": pack.get("stack") or "",
        "version": pack.get("version") or "1.0.0",
        "files": list(pack.get("files") or []),
    }
    data = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return data, f"{pack['id']}.json"


def featured_marketplace() -> list[dict[str, Any]]:
    """
    Backward-compatible marketplace view.

    Bundled catalog entries plus locally available packs as installable via registry download.
    Remote placeholder URLs from the static catalog are preserved.
    """
    featured = marketplace_catalog()
    # Enrich bundled items that exist locally with download/install URLs
    local = {i["id"]: i for i in _packs_with_source()}
    out: list[dict[str, Any]] = []
    for item in featured:
        entry = dict(item)
        local_item = local.get(item["id"])
        if local_item and not entry.get("url"):
            entry["url"] = local_item["download_url"]
            entry["download_url"] = local_item["download_url"]
        out.append(entry)
    return out


def registry_count() -> int:
    return len(list_packs())
