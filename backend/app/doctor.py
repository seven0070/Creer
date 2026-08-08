"""Doctor diagnostics — structured no-secrets health report (v1.4)."""

from __future__ import annotations

from typing import Any

from config import (
    CREER_ALLOW_PRIVATE_PEERS,
    CREER_FEDERATION_MAX_HOPS,
    CREER_OFFLINE,
    CREER_PUBLIC_BASE_URL,
    MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    mtls_client_configured,
    tls_server_configured,
)
from app.auth import registry_auth_required
from app.federation import parse_peers
from app.packs import list_packs
from app.peer_trust import trust_enabled, trust_mode
from app.registry import registry_count


def build_health(version: str) -> dict[str, Any]:
    """Same payload as GET /health (reused by doctor)."""
    return {
        "status": "ok",
        "version": version,
        "offline": CREER_OFFLINE,
        "base_url_set": bool(OPENAI_BASE_URL),
        "model": MODEL,
        "packs_count": len(list_packs()),
        "registry_count": registry_count(),
        "public_base_url_set": bool(CREER_PUBLIC_BASE_URL),
        "peers_configured": len(parse_peers()),
        "auth_required": registry_auth_required(),
        "federation_max_hops": CREER_FEDERATION_MAX_HOPS,
        "allow_private_peers": CREER_ALLOW_PRIVATE_PEERS,
        "peer_trust_mode": trust_mode(),
        "peer_trust_signing": trust_enabled(),
        "tls_server_configured": tls_server_configured(),
        "mtls_client_configured": mtls_client_configured(),
    }


def _llm_check() -> dict[str, Any]:
    """ok if offline OR API key OR base_url."""
    offline = CREER_OFFLINE
    key_set = bool(OPENAI_API_KEY)
    base_set = bool(OPENAI_BASE_URL)
    ok = offline or key_set or base_set
    parts: list[str] = []
    if offline:
        parts.append("offline stubs")
    if key_set:
        parts.append("OPENAI_API_KEY set")
    if base_set:
        parts.append("BASE_URL set")
    if not parts:
        parts.append("no OPENAI_API_KEY, no BASE_URL, not offline")
    return {"id": "llm", "ok": ok, "detail": " / ".join(parts)}


def run_doctor(version: str) -> dict[str, Any]:
    """
    Build a structured diagnostics report with no secrets.

    Top-level ok is true when every check is ok.
    """
    health = build_health(version)
    packs_n = int(health.get("packs_count") or 0)
    peers_n = int(health.get("peers_configured") or 0)
    auth_detail = (
        "registry write auth required"
        if health.get("auth_required")
        else "registry write auth open"
    )
    signing = "on" if health.get("peer_trust_signing") else "off"
    server = "yes" if health.get("tls_server_configured") else "no"
    client = "yes" if health.get("mtls_client_configured") else "no"

    checks: list[dict[str, Any]] = [
        {
            "id": "health",
            "ok": True,
            "detail": f"status={health.get('status')} version={version}",
        },
        {
            "id": "offline",
            "ok": True,
            "detail": f"CREER_OFFLINE={'true' if CREER_OFFLINE else 'false'}",
        },
        _llm_check(),
        {"id": "packs", "ok": True, "detail": f"{packs_n} packs"},
        {"id": "peers", "ok": True, "detail": f"{peers_n} configured"},
        {"id": "auth", "ok": True, "detail": auth_detail},
        {
            "id": "trust",
            "ok": True,
            "detail": f"mode={trust_mode()} signing={signing}",
        },
        {
            "id": "tls",
            "ok": True,
            "detail": f"server={server} client_mtls={client}",
        },
    ]

    return {
        "version": version,
        "ok": all(bool(c.get("ok")) for c in checks),
        "checks": checks,
        "health": health,
    }
