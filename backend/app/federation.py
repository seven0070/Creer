"""Federated multi-host registry discovery — query peer Creer registries and merge."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from config import CREER_REGISTRY_PEERS
from app.registry import list_registry

FEDERATION_VERSION = "0.8.0"
_MAX_PEERS = 8


def parse_peers(raw: str | None = None) -> list[str]:
    """
    Normalize peer base URLs from CREER_REGISTRY_PEERS (or raw override).

    Strips whitespace/trailing slash, dedupes (order preserved), keeps http/https only.
    """
    text = CREER_REGISTRY_PEERS if raw is None else raw
    if not text:
        return []

    seen: set[str] = set()
    out: list[str] = []
    for part in text.split(","):
        url = part.strip().rstrip("/")
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            continue
        if not parsed.netloc:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def _absolutize_url(base_url: str, value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    if value.startswith("http://") or value.startswith("https://"):
        return value
    # Relative path → absolute against peer base
    return urljoin(base_url.rstrip("/") + "/", value.lstrip("/"))


def _tag_peer_items(base_url: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item["peer"] = base_url
        if "download_url" in item:
            item["download_url"] = _absolutize_url(base_url, item.get("download_url"))
        if "install_url" in item:
            item["install_url"] = _absolutize_url(base_url, item.get("install_url"))
        if "url" in item and isinstance(item.get("url"), str):
            item["url"] = _absolutize_url(base_url, item["url"])
        tagged.append(item)
    return tagged


def fetch_peer_registry(
    base_url: str,
    *,
    q: str | None = None,
    source: str | None = None,
    timeout: float = 8.0,
) -> list[dict[str, Any]]:
    """
    GET {base}/registry and return tagged items.

    On any failure returns [] (never raises for federation callers).
    """
    items, _err = _fetch_peer_registry(base_url, q=q, source=source, timeout=timeout)
    return items


def _fetch_peer_registry(
    base_url: str,
    *,
    q: str | None = None,
    source: str | None = None,
    timeout: float = 8.0,
) -> tuple[list[dict[str, Any]], str | None]:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return [], "empty base_url"

    params: dict[str, str] = {}
    if q:
        params["q"] = q
    if source:
        params["source"] = source

    url = f"{base}/registry"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, params=params or None)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 — federation must never crash
        return [], str(exc)

    if isinstance(data, dict):
        raw_items = data.get("items") or []
    elif isinstance(data, list):
        raw_items = data
    else:
        return [], "unexpected registry response shape"

    if not isinstance(raw_items, list):
        return [], "unexpected registry items shape"

    return _tag_peer_items(base, raw_items), None


def list_federated(
    *,
    q: str | None = None,
    source: str | None = None,
    include_local: bool = True,
) -> dict[str, Any]:
    """Merge local registry with peer registries (local ids win on collision)."""
    local = list_registry(q=q, source=source or "all") if include_local else {
        "version": FEDERATION_VERSION,
        "base_url": None,
        "items": [],
    }

    peers = parse_peers()[:_MAX_PEERS]
    peer_meta: list[dict[str, Any]] = []
    peer_items_by_url: dict[str, list[dict[str, Any]]] = {}

    def _one(peer: str) -> tuple[str, list[dict[str, Any]], str | None]:
        items, err = _fetch_peer_registry(peer, q=q, source=source)
        return peer, items, err

    if peers:
        workers = min(8, len(peers))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_one, p): p for p in peers}
            for fut in as_completed(futures):
                peer, items, err = fut.result()
                peer_items_by_url[peer] = items
                peer_meta.append(
                    {
                        "base_url": peer,
                        "ok": err is None,
                        "count": len(items) if err is None else 0,
                        "error": err,
                    }
                )
        # Stable peer order matching parse_peers()
        order = {p: i for i, p in enumerate(peers)}
        peer_meta.sort(key=lambda m: order.get(m["base_url"], 0))

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for item in local.get("items") or []:
        pid = item.get("id")
        if isinstance(pid, str) and pid:
            seen_ids.add(pid)
        merged.append(item)

    for peer in peers:
        for item in peer_items_by_url.get(peer, []):
            pid = item.get("id")
            if isinstance(pid, str) and pid in seen_ids:
                continue
            if isinstance(pid, str) and pid:
                seen_ids.add(pid)
            merged.append(item)

    return {
        "version": FEDERATION_VERSION,
        "local": local,
        "peers": peer_meta,
        "items": merged,
    }
