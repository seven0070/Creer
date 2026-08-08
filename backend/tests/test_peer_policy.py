"""Tests for peer SSRF / allow-deny policy + multi-hop discovery (v1.1)."""

from __future__ import annotations

import socket

from fastapi.testclient import TestClient

import main
from app import federation as fed
from app import peer_policy as policy
from app.federation import expand_peers, list_federated
from main import VERSION


def _public_addrinfo(host, *args, **kwargs):
    """Fake DNS: all hostnames resolve to a public IP."""
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0)),
    ]


def test_block_loopback_when_private_not_allowed(monkeypatch):
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", False)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "")

    try:
        policy.assert_peer_allowed("http://127.0.0.1:8001")
        raised = False
    except ValueError as exc:
        raised = True
        assert "private or unsafe" in str(exc).lower() or "127.0.0.1" in str(exc)
    assert raised is True

    assert policy.is_private_or_unsafe_host("127.0.0.1") is True
    assert policy.is_private_or_unsafe_host("10.0.0.5") is True
    assert policy.is_private_or_unsafe_host("192.168.1.1") is True
    assert policy.is_private_or_unsafe_host("169.254.169.254") is True
    assert policy.is_private_or_unsafe_host("::1") is True


def test_allow_private_when_flag_set(monkeypatch):
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", True)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "")

    policy.assert_peer_allowed("http://127.0.0.1:8001")
    policy.assert_peer_allowed("http://10.1.2.3:9000")


def test_allowlist_permits_loopback_when_private_off(monkeypatch):
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", False)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "127.0.0.1,localhost")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "")

    policy.assert_peer_allowed("http://127.0.0.1:8001")


def test_denylist_blocks(monkeypatch):
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", True)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "evil.example,http://bad.peer:8000")

    try:
        policy.assert_peer_allowed("http://evil.example")
        raised = False
    except ValueError as exc:
        raised = True
        assert "denylist" in str(exc).lower() or "denied" in str(exc).lower()
    assert raised is True

    try:
        policy.assert_peer_allowed("http://bad.peer:8000")
        raised2 = False
    except ValueError:
        raised2 = True
    assert raised2 is True


def test_allowlist_restricts(monkeypatch):
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", True)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "ok.example")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "")
    monkeypatch.setattr(policy.socket, "getaddrinfo", _public_addrinfo)

    policy.assert_peer_allowed("https://ok.example")
    try:
        policy.assert_peer_allowed("https://other.example")
        raised = False
    except ValueError as exc:
        raised = True
        assert "allowlist" in str(exc).lower()
    assert raised is True
    assert policy.allowlist_active() is True
    assert policy.is_blocked_host("other.example") is True
    assert policy.is_blocked_host("ok.example") is False


def test_dns_failure_treated_as_unsafe(monkeypatch):
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", False)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "")

    def boom(*a, **k):
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(policy.socket, "getaddrinfo", boom)
    assert policy.is_private_or_unsafe_host("no-such-host.invalid") is True


def test_max_hops_cycle_no_infinite_loop(monkeypatch):
    """A discovers B, B discovers A → cycle detected, no infinite loop."""
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", True)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "")
    monkeypatch.setattr(policy, "CREER_FEDERATION_MAX_HOPS", 2)
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "http://a.example")

    def fake_discover(base_url, *, timeout=3.0):
        if base_url == "http://a.example":
            return {"peers": ["http://b.example"]}, None
        if base_url == "http://b.example":
            return {"peers": ["http://a.example"]}, None
        return None, "unknown"

    monkeypatch.setattr(fed, "fetch_peer_discover", fake_discover)

    expanded, discovered = expand_peers(["http://a.example"], max_hops=2)
    assert expanded == ["http://a.example", "http://b.example"]
    assert discovered == ["http://b.example"]
    # Second hop sees A again but does not re-add or loop
    assert expanded.count("http://a.example") == 1
    assert expanded.count("http://b.example") == 1


def test_max_hops_zero_no_expansion(monkeypatch):
    monkeypatch.setattr(policy, "CREER_FEDERATION_MAX_HOPS", 0)

    def boom(*a, **k):
        raise AssertionError("discover must not be called when max_hops=0")

    monkeypatch.setattr(fed, "fetch_peer_discover", boom)
    expanded, discovered = expand_peers(["http://seed.example"], max_hops=0)
    assert expanded == ["http://seed.example"]
    assert discovered == []


def test_list_federated_includes_policy(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "")
    monkeypatch.setattr(policy, "CREER_FEDERATION_MAX_HOPS", 1)
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", False)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "")

    result = list_federated(discover=False)
    assert result["version"] == "1.4.0"
    assert result["policy"] == {
        "max_hops": 1,
        "allow_private": False,
        "allowlist_active": False,
    }


def test_discover_includes_policy(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "")
    monkeypatch.setattr(policy, "CREER_FEDERATION_MAX_HOPS", 2)
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", True)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "x.example")

    c = TestClient(main.app)
    body = c.get("/registry/discover").json()
    assert body["version"] == "1.4.0"
    assert body["policy"]["max_hops"] == 2
    assert body["policy"]["allow_private"] is True
    assert body["policy"]["allowlist_active"] is True


def test_probe_endpoint_400_when_policy_blocks(monkeypatch):
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", False)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "")

    c = TestClient(main.app)
    r = c.post("/registry/peers/probe", json={"url": "http://127.0.0.1:8001"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "private" in detail.lower() or "unsafe" in detail.lower()


def test_probe_peer_returns_error_when_blocked(monkeypatch):
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", False)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "")

    result = fed.probe_peer("http://127.0.0.1:9")
    assert result["ok"] is False
    assert result["error"]
    assert "private" in result["error"].lower() or "unsafe" in result["error"].lower()


def test_health_1_1(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "https://a.example")
    c = TestClient(main.app)
    h = c.get("/health").json()
    assert h["version"] == "1.4.0"
    assert VERSION == "1.4.0"
    assert "federation_max_hops" in h
    assert h["federation_max_hops"] in (0, 1, 2)
    assert "allow_private_peers" in h
    assert isinstance(h["allow_private_peers"], bool)
    assert h["status"] == "ok"


def test_normalize_and_host_of():
    assert policy.normalize_peer_url("https://Peer.Example:8443/") == "https://Peer.Example:8443"
    assert policy.normalize_peer_url("ftp://x") is None
    assert policy.normalize_peer_url("") is None
    assert policy.host_of("https://Peer.Example:8443/path") == "peer.example"
    assert policy.host_of("127.0.0.1") == "127.0.0.1"
