"""Federated multi-host registry discovery — query peer Creer registries and merge."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urljoin, urlparse

from config import CREER_PUBLIC_BASE_URL, CREER_REGISTRY_PEERS
from app.auth import registry_auth_required
from app.peer_policy import (
    assert_peer_allowed,
    clamped_max_hops,
    normalize_peer_url,
    policy_summary,
)
from app.peer_trust import evaluate_peer_trust, sign_payload, trust_mode
from app.http_client import peer_httpx_client
from app.registry import list_registry, registry_count

FEDERATION_VERSION = "1.4.0"
_MAX_PEERS = 8
_DISCOVER_TIMEOUT = 3.0


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
        url = normalize_peer_url(part)
        if not url:
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


def discover_self() -> dict[str, Any]:
    """Local gossip-lite discovery payload (configured peers only)."""
    return sign_payload(
        {
            "version": FEDERATION_VERSION,
            "base_url": CREER_PUBLIC_BASE_URL or None,
            "packs_count": registry_count(),
            "peers": parse_peers(),
            "auth_required": registry_auth_required(),
            "policy": policy_summary(),
        }
    )


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


def _unpack_fetch_result(
    result: tuple[Any, ...],
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """Support both legacy (items, err) and (items, err, trust_status) returns."""
    if len(result) >= 3:
        return result[0], result[1], result[2]
    return result[0], result[1], None


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
    items, _err, _trust = _unpack_fetch_result(
        _fetch_peer_registry(base_url, q=q, source=source, timeout=timeout)
    )
    return items


def _fetch_peer_registry(
    base_url: str,
    *,
    q: str | None = None,
    source: str | None = None,
    timeout: float = 8.0,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """
    Fetch peer registry.

    Returns (items, error, trust_status). trust_status may be None on transport errors
    before JSON verification.
    """
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return [], "empty base_url", None

    try:
        assert_peer_allowed(base)
    except ValueError as exc:
        return [], str(exc), None

    params: dict[str, str] = {}
    if q:
        params["q"] = q
    if source:
        params["source"] = source

    url = f"{base}/registry"
    try:
        with peer_httpx_client(timeout=timeout) as client:
            resp = client.get(url, params=params or None)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 — federation must never crash
        return [], str(exc), None

    trust_status: str | None = None
    if isinstance(data, dict):
        trust_status, trust_err = evaluate_peer_trust(data)
        if trust_err is not None:
            return [], trust_err, trust_status
        raw_items = data.get("items") or []
    elif isinstance(data, list):
        # Bare list has no trust block — evaluate as unsigned empty object context
        trust_status, trust_err = evaluate_peer_trust({})
        if trust_err is not None:
            return [], trust_err, trust_status
        raw_items = data
    else:
        return [], "unexpected registry response shape", None

    if not isinstance(raw_items, list):
        return [], "unexpected registry items shape", trust_status

    return _tag_peer_items(base, raw_items), None, trust_status


def fetch_peer_discover(
    base_url: str,
    *,
    timeout: float = _DISCOVER_TIMEOUT,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    GET {base}/registry/discover.

    Returns (payload, None) on success or (None, error) on failure. Never raises.
    On success, payload may include trust_status from verification.
    """
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return None, "empty base_url"

    try:
        assert_peer_allowed(base)
    except ValueError as exc:
        return None, str(exc)

    url = f"{base}/registry/discover"
    try:
        with peer_httpx_client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)

    if not isinstance(data, dict):
        return None, "unexpected discover response shape"

    trust_status, trust_err = evaluate_peer_trust(data)
    if trust_err is not None:
        return None, trust_err

    out = dict(data)
    out["trust_status"] = trust_status
    return out, None


def expand_peers(
    seeds: list[str],
    max_hops: int | None = None,
    *,
    timeout: float = _DISCOVER_TIMEOUT,
) -> tuple[list[str], list[str]]:
    """
    Multi-hop gossip-lite discovery with cycle detection.

    max_hops 0 = no expansion (return seeds only; configured peers remain hop0).
    Cap total peers at _MAX_PEERS. Skips candidates blocked by peer policy.
    Returns (expanded_peers, discovered_peers_added).
    """
    hops = clamped_max_hops(max_hops)
    if not seeds:
        return [], []

    # Preserve seed order; cap immediately
    known: set[str] = set()
    all_peers: list[str] = []
    for s in seeds:
        url = normalize_peer_url(s) or (s.strip().rstrip("/") if s else "")
        if not url or url in known:
            continue
        known.add(url)
        all_peers.append(url)
        if len(all_peers) >= _MAX_PEERS:
            break

    if hops <= 0 or not all_peers:
        return all_peers, []

    discovered_all: list[str] = []
    frontier = list(all_peers)
    fetched: set[str] = set()

    for _ in range(hops):
        if len(all_peers) >= _MAX_PEERS:
            break
        to_query = [p for p in frontier if p not in fetched]
        if not to_query:
            break

        by_peer: dict[str, dict[str, Any] | None] = {}
        workers = min(8, len(to_query))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(fetch_peer_discover, p, timeout=timeout): p for p in to_query
            }
            for fut in as_completed(futures):
                peer = futures[fut]
                data, err = fut.result()
                by_peer[peer] = data if err is None else None
                fetched.add(peer)

        new_frontier: list[str] = []
        for peer in to_query:
            data = by_peer.get(peer)
            if not data:
                continue
            advertised = data.get("peers") or []
            if not isinstance(advertised, list):
                continue
            for raw in advertised:
                if not isinstance(raw, str):
                    continue
                for cand in parse_peers(raw):
                    if cand in known:
                        continue  # cycle / already have
                    try:
                        assert_peer_allowed(cand)
                    except ValueError:
                        continue
                    if len(all_peers) >= _MAX_PEERS:
                        return all_peers, discovered_all
                    known.add(cand)
                    all_peers.append(cand)
                    discovered_all.append(cand)
                    new_frontier.append(cand)
        frontier = new_frontier

    return all_peers, discovered_all


def expand_peers_one_hop(
    peers: list[str],
    *,
    timeout: float = _DISCOVER_TIMEOUT,
) -> tuple[list[str], list[str]]:
    """Backward-compatible one-hop expand (ignores CREER_FEDERATION_MAX_HOPS)."""
    return expand_peers(peers, max_hops=1, timeout=timeout)


def probe_peer(base_url: str, timeout: float = 5.0) -> dict[str, Any]:
    """
    Probe a peer host via /health (preferred) and/or /registry for pack count.

    Never raises — returns a status dict with ok/latency/count/version/error.
    Includes trust_status when /registry JSON is available for verification.
    """
    base = (base_url or "").strip().rstrip("/")
    result: dict[str, Any] = {
        "base_url": base,
        "ok": False,
        "latency_ms": None,
        "count": None,
        "version": None,
        "error": None,
        "trust_status": None,
    }
    if not base:
        result["error"] = "empty base_url"
        return result

    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        result["error"] = "url must use http or https with a host"
        return result

    try:
        assert_peer_allowed(base)
    except ValueError as exc:
        result["error"] = str(exc)
        return result

    started = time.perf_counter()
    version: str | None = None
    count: int | None = None
    health_ok = False
    last_error: str | None = None
    trust_status: str | None = None

    try:
        with peer_httpx_client(timeout=timeout) as client:
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

            # Use /registry for count/version fallback; also when trust mode needs verify.
            need_registry = count is None or version is None or trust_mode() != "off"
            if need_registry:
                try:
                    rresp = client.get(f"{base}/registry")
                    rresp.raise_for_status()
                    rdata = rresp.json()
                    if isinstance(rdata, dict):
                        trust_status, trust_err = evaluate_peer_trust(rdata)
                        if trust_err is not None:
                            latency_ms = round((time.perf_counter() - started) * 1000, 1)
                            result["latency_ms"] = latency_ms
                            result["ok"] = False
                            result["trust_status"] = trust_status
                            result["error"] = trust_err
                            result["version"] = version
                            return result
                        if version is None:
                            ver = rdata.get("version")
                            if isinstance(ver, str):
                                version = ver
                        if count is None:
                            raw_items = rdata.get("items") or []
                            count = len(raw_items) if isinstance(raw_items, list) else 0
                    elif isinstance(rdata, list):
                        trust_status, trust_err = evaluate_peer_trust({})
                        if trust_err is not None:
                            latency_ms = round((time.perf_counter() - started) * 1000, 1)
                            result["latency_ms"] = latency_ms
                            result["ok"] = False
                            result["trust_status"] = trust_status
                            result["error"] = trust_err
                            result["version"] = version
                            return result
                        if count is None:
                            count = len(rdata)
                except Exception as exc:  # noqa: BLE001
                    if not health_ok:
                        last_error = str(exc)
                    elif last_error is None:
                        last_error = str(exc)

            if trust_status is None and trust_mode() == "off":
                trust_status = "skipped"

            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            result["latency_ms"] = latency_ms
            result["trust_status"] = trust_status

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
    discover: bool = False,
    max_hops: int | None = None,
) -> dict[str, Any]:
    """Merge local registry with peer registries (local ids win on collision)."""
    local = list_registry(q=q, source=source or "all") if include_local else {
        "version": FEDERATION_VERSION,
        "base_url": None,
        "items": [],
    }

    peers = resolve_peers(extra_peers)
    discovered_peers: list[str] = []
    if discover and peers:
        peers, discovered_peers = expand_peers(peers, max_hops=max_hops)

    peer_meta: list[dict[str, Any]] = []
    peer_items_by_url: dict[str, list[dict[str, Any]]] = {}

    def _one(peer: str) -> tuple[str, list[dict[str, Any]], str | None, str | None]:
        items, err, trust_status = _unpack_fetch_result(
            _fetch_peer_registry(peer, q=q, source=source)
        )
        return peer, items, err, trust_status

    if peers:
        workers = min(8, len(peers))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_one, p): p for p in peers}
            for fut in as_completed(futures):
                peer, items, err, trust_status = fut.result()
                peer_items_by_url[peer] = items
                peer_meta.append(
                    {
                        "base_url": peer,
                        "ok": err is None,
                        "count": len(items) if err is None else 0,
                        "error": err,
                        "trust_status": trust_status,
                    }
                )
        # Stable peer order matching resolve_peers() / expand order
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

    summary = policy_summary()
    if max_hops is not None:
        summary = dict(summary)
        summary["request_max_hops"] = clamped_max_hops(max_hops)

    return {
        "version": FEDERATION_VERSION,
        "local": local,
        "peers": peer_meta,
        "items": merged,
        "discovered_peers": discovered_peers,
        "policy": summary,
    }
