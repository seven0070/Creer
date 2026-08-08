"""Shared httpx client for outbound peer calls (optional TLS / mTLS)."""

from __future__ import annotations

from typing import Any

import httpx

from config import (
    CREER_SSL_CA_CERTS,
    CREER_SSL_CLIENT_CERT,
    CREER_SSL_CLIENT_KEY,
    CREER_SSL_VERIFY,
)


def peer_httpx_client(timeout: float = 8.0) -> httpx.Client:
    """
    Build an httpx.Client for federation/peer requests.

    - verify: CA bundle path, True, or False (CREER_SSL_VERIFY)
    - cert: client cert/key tuple when both CREER_SSL_CLIENT_* are set
    """
    verify: Any
    if not CREER_SSL_VERIFY:
        verify = False
    elif CREER_SSL_CA_CERTS:
        verify = CREER_SSL_CA_CERTS
    else:
        verify = True

    kwargs: dict[str, Any] = {
        "timeout": timeout,
        "follow_redirects": True,
        "verify": verify,
    }
    if CREER_SSL_CLIENT_CERT and CREER_SSL_CLIENT_KEY:
        kwargs["cert"] = (CREER_SSL_CLIENT_CERT, CREER_SSL_CLIENT_KEY)

    return httpx.Client(**kwargs)
