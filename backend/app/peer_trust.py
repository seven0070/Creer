"""Signed peer trust via shared HMAC-SHA256 (v1.2) — practical stand-in for mTLS."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from config import (
    CREER_PEER_TRUST_MODE as _MODE_FROM_CONFIG,
    CREER_PEER_TRUST_SECRET as _SECRET_FROM_CONFIG,
)

# Module-level bindings so tests can monkeypatch
CREER_PEER_TRUST_SECRET = _SECRET_FROM_CONFIG
CREER_PEER_TRUST_MODE = _MODE_FROM_CONFIG

_VALID_MODES = frozenset({"off", "optional", "required"})


def trust_enabled() -> bool:
    """True when a non-empty shared secret is configured."""
    return bool((CREER_PEER_TRUST_SECRET or "").strip())


def trust_mode() -> str:
    """Normalized peer trust mode: off | optional | required."""
    raw = (CREER_PEER_TRUST_MODE or "off").strip().lower()
    if raw not in _VALID_MODES:
        return "off"
    return raw


def canonical_payload(data: dict) -> bytes:
    """
    Canonical JSON bytes for HMAC: sorted keys, no whitespace, excluding top-level trust.
    """
    body = {k: v for k, v in data.items() if k != "trust"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _compute_sig(data: dict) -> str:
    secret = (CREER_PEER_TRUST_SECRET or "").encode("utf-8")
    digest = hmac.new(secret, canonical_payload(data), hashlib.sha256).hexdigest()
    return digest


def sign_payload(data: dict) -> dict:
    """
    Return a copy of data with trust signature attached when secret is set.

    trust: {"alg": "HMAC-SHA256", "kid": "default", "sig": "<hex>"}
    """
    if not isinstance(data, dict):
        return data
    if not trust_enabled():
        return data
    out = dict(data)
    out.pop("trust", None)
    sig = _compute_sig(out)
    out["trust"] = {"alg": "HMAC-SHA256", "kid": "default", "sig": sig}
    return out


def verify_payload(data: dict) -> tuple[str, str | None]:
    """
    Verify peer payload trust block.

    Returns (status, error) where status is:
      signed | unsigned | invalid | skipped
    """
    if trust_mode() == "off":
        return "skipped", None

    if not isinstance(data, dict):
        return "invalid", "payload is not an object"

    trust = data.get("trust")
    if trust is None:
        return "unsigned", None
    if not isinstance(trust, dict):
        return "invalid", "trust block must be an object"

    sig = trust.get("sig")
    if not sig or not isinstance(sig, str):
        return "unsigned", None

    if not trust_enabled():
        return "invalid", "peer trust secret not configured"

    expected = _compute_sig(data)
    provided = sig.strip().lower()
    if not hmac.compare_digest(expected, provided):
        return "invalid", "HMAC signature mismatch"
    return "signed", None


def evaluate_peer_trust(data: dict) -> tuple[str, str | None]:
    """
    Apply trust_mode policy to a parsed peer JSON payload.

    Returns (trust_status, error_or_none). Non-None error means treat as fetch failure.
    """
    status, verr = verify_payload(data if isinstance(data, dict) else {})
    mode = trust_mode()

    if mode == "off":
        return "skipped", None

    if mode == "required":
        if status in ("unsigned", "invalid"):
            return status, verr or f"peer trust {status}"
        return status, None

    # optional
    if status == "invalid":
        return status, verr or "peer trust invalid"
    return status, None
