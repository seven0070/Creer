"""Tests for federation UX — peer status, probe, ad-hoc peers (v0.9)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import main
from app import federation as fed
from app import peer_policy as policy
from app.federation import list_federated, list_peer_status, probe_peer, resolve_peers
from main import VERSION


def _allow_fake_hosts(monkeypatch):
    """Skip SSRF DNS checks for .example test hosts."""
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", True)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "")
    monkeypatch.setattr(policy, "is_private_or_unsafe_host", lambda host: False)


def test_probe_peer_ok(monkeypatch):
    _allow_fake_hosts(monkeypatch)
    calls: list[str] = []

    class FakeResp:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            calls.append(url)
            if url.endswith("/health"):
                return FakeResp(
                    {"status": "ok", "version": "0.8.0", "registry_count": 3}
                )
            raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(fed.httpx, "Client", FakeClient)
    result = probe_peer("http://peer.example:8001")
    assert result["ok"] is True
    assert result["base_url"] == "http://peer.example:8001"
    assert result["version"] == "0.8.0"
    assert result["count"] == 3
    assert result["error"] is None
    assert isinstance(result["latency_ms"], (int, float))
    assert result["latency_ms"] >= 0
    assert any(u.endswith("/health") for u in calls)


def test_probe_peer_fail(monkeypatch):
    _allow_fake_hosts(monkeypatch)

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            raise ConnectionError("connection refused")

    monkeypatch.setattr(fed.httpx, "Client", FakeClient)
    result = probe_peer("http://dead.peer:9999")
    assert result["ok"] is False
    assert result["base_url"] == "http://dead.peer:9999"
    assert result["error"]
    assert "connection refused" in result["error"]
    assert result["count"] is None
    assert isinstance(result["latency_ms"], (int, float))


def test_probe_peer_registry_fallback(monkeypatch):
    """When /health fails, /registry still yields ok + count."""
    _allow_fake_hosts(monkeypatch)

    class FakeResp:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            if url.endswith("/health"):
                raise ConnectionError("no health")
            if url.endswith("/registry"):
                return FakeResp(
                    {
                        "version": "0.8.0",
                        "items": [{"id": "a"}, {"id": "b"}],
                    }
                )
            raise AssertionError(url)

    monkeypatch.setattr(fed.httpx, "Client", FakeClient)
    result = probe_peer("http://peer.example")
    assert result["ok"] is True
    assert result["count"] == 2
    assert result["version"] == "0.8.0"
    assert result["error"] is None


def test_resolve_peers_merges_extra_dedupe_max():
    # configured via monkeypatch below in other tests; unit-test via parse_peers path
    peers = resolve_peers(None)
    assert isinstance(peers, list)

    # With extras only when no config
    from app import federation as f

    # Temporarily empty config
    original = f.CREER_REGISTRY_PEERS
    try:
        f.CREER_REGISTRY_PEERS = "http://a.example,http://b.example"
        merged = resolve_peers(
            [
                "http://b.example/",
                "http://c.example",
                "ftp://bad",
                "http://d.example",
            ]
        )
        assert merged == [
            "http://a.example",
            "http://b.example",
            "http://c.example",
            "http://d.example",
        ]

        f.CREER_REGISTRY_PEERS = ",".join(f"http://p{i}.example" for i in range(10))
        capped = resolve_peers(["http://extra.example"])
        assert len(capped) == 8
        assert "http://extra.example" not in capped  # configured fills the cap
    finally:
        f.CREER_REGISTRY_PEERS = original


def test_list_peer_status_concurrent(monkeypatch):
    monkeypatch.setattr(
        fed,
        "CREER_REGISTRY_PEERS",
        "http://a.example,http://b.example",
    )

    def fake_probe(base_url, timeout=5.0):
        return {
            "base_url": base_url,
            "ok": base_url.endswith("a.example"),
            "latency_ms": 1.0,
            "count": 1 if base_url.endswith("a.example") else None,
            "version": "1.0.0" if base_url.endswith("a.example") else None,
            "error": None if base_url.endswith("a.example") else "down",
        }

    monkeypatch.setattr(fed, "probe_peer", fake_probe)
    statuses = list_peer_status()
    assert len(statuses) == 2
    assert statuses[0]["base_url"] == "http://a.example"
    assert statuses[0]["ok"] is True
    assert statuses[1]["base_url"] == "http://b.example"
    assert statuses[1]["ok"] is False


def test_registry_peers_route(monkeypatch):
    monkeypatch.setattr(
        fed,
        "CREER_REGISTRY_PEERS",
        "https://peer.example",
    )
    monkeypatch.setattr(
        fed,
        "probe_peer",
        lambda base_url, timeout=5.0: {
            "base_url": base_url,
            "ok": True,
            "latency_ms": 2.5,
            "count": 4,
            "version": "1.0.0",
            "error": None,
        },
    )
    c = TestClient(main.app)
    r = c.get("/registry/peers")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] == ["https://peer.example"]
    assert len(body["peers"]) == 1
    assert body["peers"][0]["ok"] is True
    assert body["peers"][0]["count"] == 4


def test_registry_peers_probe_validation():
    c = TestClient(main.app)
    bad = c.post("/registry/peers/probe", json={"url": "ftp://evil.example"})
    assert bad.status_code == 400

    bad2 = c.post("/registry/peers/probe", json={"url": "not-a-url"})
    assert bad2.status_code == 400

    bad3 = c.post("/registry/peers/probe", json={"url": "http://"})
    assert bad3.status_code == 400


def test_registry_peers_probe_ok(monkeypatch):
    _allow_fake_hosts(monkeypatch)
    monkeypatch.setattr(
        main,
        "probe_peer",
        lambda base_url, timeout=5.0: {
            "base_url": base_url.rstrip("/"),
            "ok": True,
            "latency_ms": 10.0,
            "count": 2,
            "version": "1.0.0",
            "error": None,
        },
    )
    c = TestClient(main.app)
    r = c.post("/registry/peers/probe", json={"url": "http://peer.test:9000/"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["base_url"] == "http://peer.test:9000"
    assert body["count"] == 2


def test_federated_with_extra_peers_query(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "")

    def fake_fetch(base_url, *, q=None, source=None, timeout=8.0):
        assert base_url == "http://adhoc.peer:8002"
        return [
            {
                "id": "adhoc-pack",
                "name": "Adhoc",
                "peer": base_url,
                "download_url": f"{base_url}/registry/packs/adhoc-pack/download",
            }
        ], None

    monkeypatch.setattr(fed, "_fetch_peer_registry", fake_fetch)
    c = TestClient(main.app)
    r = c.get("/registry/federated", params={"peers": "http://adhoc.peer:8002/"})
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1.1.0"
    assert any(p["base_url"] == "http://adhoc.peer:8002" for p in body["peers"])
    assert any(i["id"] == "adhoc-pack" for i in body["items"])


def test_list_federated_extra_peers_arg(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "http://cfg.peer")

    seen: list[str] = []

    def fake_fetch(base_url, *, q=None, source=None, timeout=8.0):
        seen.append(base_url)
        return [], None

    monkeypatch.setattr(fed, "_fetch_peer_registry", fake_fetch)
    result = list_federated(extra_peers=["http://extra.peer/", "http://cfg.peer"])
    assert result["version"] == "1.1.0"
    assert seen == ["http://cfg.peer", "http://extra.peer"]


def test_health_0_9(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "https://a.example,https://b.example")
    c = TestClient(main.app)
    h = c.get("/health").json()
    assert h["version"] == "1.1.0"
    assert VERSION == "1.1.0"
    assert h["peers_configured"] == 2
    assert h["status"] == "ok"
