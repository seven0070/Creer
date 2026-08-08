"""Tests for optional TLS/mTLS httpx client factory (v1.3)."""

from __future__ import annotations

import app.http_client as http_client
from app.http_client import peer_httpx_client


def test_peer_httpx_client_default(monkeypatch):
    monkeypatch.setattr(http_client, "CREER_SSL_VERIFY", True)
    monkeypatch.setattr(http_client, "CREER_SSL_CA_CERTS", None)
    monkeypatch.setattr(http_client, "CREER_SSL_CLIENT_CERT", None)
    monkeypatch.setattr(http_client, "CREER_SSL_CLIENT_KEY", None)
    with peer_httpx_client(timeout=1.0) as client:
        assert client is not None
        assert client.timeout.connect == 1.0


def test_peer_httpx_client_insecure_verify(monkeypatch):
    monkeypatch.setattr(http_client, "CREER_SSL_VERIFY", False)
    monkeypatch.setattr(http_client, "CREER_SSL_CA_CERTS", None)
    monkeypatch.setattr(http_client, "CREER_SSL_CLIENT_CERT", None)
    monkeypatch.setattr(http_client, "CREER_SSL_CLIENT_KEY", None)
    with peer_httpx_client(timeout=2.0) as client:
        assert client is not None


def test_health_tls_flags():
    from fastapi.testclient import TestClient
    import main

    c = TestClient(main.app)
    h = c.get("/health").json()
    assert h["version"] == "1.3.0"
    assert "tls_server_configured" in h
    assert "mtls_client_configured" in h
    assert h["tls_server_configured"] is False
    assert h["mtls_client_configured"] is False
