"""Outbound peer SSRF / allow-deny policy for federation (v1.1)."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

from config import (
    CREER_ALLOW_PRIVATE_PEERS as _ALLOW_PRIVATE_FROM_CONFIG,
    CREER_FEDERATION_MAX_HOPS as _MAX_HOPS_FROM_CONFIG,
    CREER_PEER_ALLOWLIST as _ALLOWLIST_FROM_CONFIG,
    CREER_PEER_DENYLIST as _DENYLIST_FROM_CONFIG,
)

# Module-level bindings so tests can monkeypatch
CREER_ALLOW_PRIVATE_PEERS = _ALLOW_PRIVATE_FROM_CONFIG
CREER_FEDERATION_MAX_HOPS = _MAX_HOPS_FROM_CONFIG
CREER_PEER_ALLOWLIST = _ALLOWLIST_FROM_CONFIG
CREER_PEER_DENYLIST = _DENYLIST_FROM_CONFIG


def normalize_peer_url(url: str | None) -> str | None:
    """Strip, drop trailing slash; return http(s) base URL or None if invalid."""
    if not url or not isinstance(url, str):
        return None
    text = url.strip().rstrip("/")
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None
    return text


def host_of(url: str) -> str:
    """Extract lowercase hostname from a URL or bare host string."""
    if not url or not isinstance(url, str):
        return ""
    text = url.strip()
    if "://" not in text:
        text = f"http://{text}"
    parsed = urlparse(text)
    host = parsed.hostname or ""
    return host.lower().rstrip(".")


def _hosts_from_csv(raw: str | None) -> set[str]:
    """Parse comma-separated hostnames/URLs into a set of lowercase hosts."""
    if not raw or not str(raw).strip():
        return set()
    out: set[str] = set()
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        h = host_of(part)
        if h:
            out.add(h)
    return out


def allowlist_hosts() -> set[str]:
    return _hosts_from_csv(CREER_PEER_ALLOWLIST)


def denylist_hosts() -> set[str]:
    return _hosts_from_csv(CREER_PEER_DENYLIST)


def allowlist_active() -> bool:
    return bool(allowlist_hosts())


def is_blocked_host(host: str) -> bool:
    """
    True if host is denylisted, or allowlist is active and host is not listed.
    """
    h = (host or "").lower().rstrip(".")
    if not h:
        return True
    if h in denylist_hosts():
        return True
    allow = allowlist_hosts()
    if allow and h not in allow:
        return True
    return False


def _ip_is_private_or_unsafe(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Block private, loopback, link-local, unspecified, multicast, reserved."""
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_multicast
        or ip.is_reserved
    ):
        return True
    # Explicit metadata IP (also link-local, but keep visible intent)
    if ip.version == 4 and str(ip) == "169.254.169.254":
        return True
    return False


def is_private_or_unsafe_host(host: str) -> bool:
    """
    True if host is a private/unsafe literal IP, or any resolved address is.

    On DNS failure, treat as unsafe (blocked for outbound).
    """
    h = (host or "").lower().rstrip(".")
    if not h:
        return True

    # Literal IP (IPv4 / IPv6)
    try:
        ip = ipaddress.ip_address(h)
        return _ip_is_private_or_unsafe(ip)
    except ValueError:
        pass

    # Hostname → resolve all addresses
    try:
        infos = socket.getaddrinfo(h, None)
    except OSError:
        return True

    if not infos:
        return True

    for info in infos:
        sockaddr = info[4]
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _ip_is_private_or_unsafe(ip):
            return True
    return False


def assert_peer_allowed(url: str) -> None:
    """
    Raise ValueError with a clear message when the peer URL is not allowed.

    Loopback/private hosts are allowed when CREER_ALLOW_PRIVATE_PEERS is true,
    or when the host is explicitly present on CREER_PEER_ALLOWLIST (testing).
    """
    normalized = normalize_peer_url(url)
    if not normalized:
        raise ValueError("peer url must use http or https with a host")

    host = host_of(normalized)
    if not host:
        raise ValueError("peer url missing host")

    if is_blocked_host(host):
        if host in denylist_hosts():
            raise ValueError(f"peer host denied by denylist: {host}")
        raise ValueError(f"peer host not on allowlist: {host}")

    if not CREER_ALLOW_PRIVATE_PEERS:
        # Explicit allowlist entry may opt into private/loopback for local testing
        if host not in allowlist_hosts():
            if is_private_or_unsafe_host(host):
                raise ValueError(
                    f"peer host is private or unsafe (set CREER_ALLOW_PRIVATE_PEERS=1 "
                    f"or allowlist the host to permit): {host}"
                )


def policy_summary() -> dict[str, Any]:
    """Compact policy snapshot for discover / federated responses."""
    return {
        "max_hops": int(CREER_FEDERATION_MAX_HOPS),
        "allow_private": bool(CREER_ALLOW_PRIVATE_PEERS),
        "allowlist_active": allowlist_active(),
    }


def clamped_max_hops(override: int | None = None) -> int:
    """Return max hops clamped to 0–2."""
    raw = CREER_FEDERATION_MAX_HOPS if override is None else override
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 1
    return max(0, min(2, value))
