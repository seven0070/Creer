"""Federated multi-host registry discovery — query peer Creer registries and merge."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from config import CREER_REGISTRY_PEERS
from app.registry import list_registry

FEDERATION_VERSION = "0.9.0"
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


def resolve_peers(extra_peers: list[str] | None = None) -> list[str]:
    """
    Merge configured peers with optional ad-hoc extras.

    Dedupes (configured first), http/https only, capped at _MAX_PEERS.
    """
    configured = parse_peers()
    extras: list[str] = []
    if extra_peers:
        # Normalize each entry (allow raw URLs or comma-joined strings)
        for raw in extra_peers:
            if not raw:
                continue
            extras.extend(parse_peers(raw))

    seen: set[str] = set()
    out: list[str] = []
    for url in configured + extras:
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= _MAX_PEERS:
            break
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


def probe_peer(base_url: str, timeout: float = 5.0) -> dict[str, Any]:
    """
    Probe a peer host via /health (preferred) and/or /registry for pack count.

    Never raises — returns a status dict with ok/latency/count/version/error.
    """
    base = (base_url or "").strip().rstrip("/")
    result: dict[str, Any] = {
        "base_url": base,
        "ok": False,
        "latency_ms": None,
        "count": None,
        "version": None,
        "error": None,
    }
    if not base:
        result["error"] = "empty base_url"
        return result

    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        result["error"] = "url must use http or https with a host"
        return result

    started = time.perf_counter()
    version: str | None = None
    count: int | None = None
    health_ok = False
    last_error: str | None = None

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            # Prefer /health for liveness + version (+ registry_count when present)
            try:
                hresp = client.get(f"{base}/health")
                hresp.raise_for_status()
                hdata = hresp.json()
                health_ok = True
                if isinstance(hdata, dict):
                    ver = hdata.get("version")
                    if isinstance(ver, str):
                        version = ver
                    if "registry_count" in hdata and hdata["registry_count"] is not None:
                        try:
                            count = int(hdata["registry_count"])
                        except (TypeError, ValueError):
                            pass
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)

            # Use /registry for count (and version fallback) when needed
            if count is None or version is None:
                try:
                    rresp = client.get(f"{base}/registry")
                    rresp.raise_for_status()
                    rdata = rresp.json()
                    if isinstance(rdata, dict):
                        if version is None:
                            ver = rdata.get("version")
                            if isinstance(ver, str):
                                version = ver
                        if count is None:
                            raw_items = rdata.get("items") or []
                            count = len(raw_items) if isinstance(raw_items, list) else 0
                    elif isinstance(rdata, list) and count is None:
                        count = len(rdata)
                except Exception as exc:  # noqa: BLE001
                    if not health_ok:
                        last_error = str(exc)
                    elif last_error is None:
                        last_error = str(exc)

            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            result["latency_ms"] = latency_ms

            if health_ok or count is not None:
                result["ok"] = True
                result["count"] = count if count is not None else 0
                result["version"] = version
                result["error"] = None
                return result

            result["error"] = last_error or "unreachable"
            return result
    except Exception as exc:  # noqa: BLE001
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        result["error"] = str(exc)
        return result


def list_peer_status() -> list[dict[str, Any]]:
    """Probe all configured peers concurrently; preserve configured order."""
    peers = parse_peers()[:_MAX_PEERS]
    if not peers:
        return []

    by_url: dict[str, dict[str, Any]] = {}
    workers = min(8, len(peers))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(probe_peer, p): p for p in peers}
        for fut in as_completed(futures):
            peer = futures[fut]
            by_url[peer] = fut.result()
    return [by_url[p] for p in peers]


def list_federated(
    *,
    q: str | None = None,
    source: str | None = None,
    include_local: bool = True,
    extra_peers: list[str] | None = None,
) -> dict[str, Any]:
    """Merge local registry with peer registries (local ids win on collision)."""
    local = list_registry(q=q, source=source or "all") if include_local else {
        "version": FEDERATION_VERSION,
        "base_url": None,
        "items": [],
    }

    peers = resolve_peers(extra_peers)
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
        # Stable peer order matching resolve_peers()
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
