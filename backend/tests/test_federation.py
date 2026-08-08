"""Tests for federated multi-host registry discovery (v0.8)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import main
from app import federation as fed
from app.federation import list_federated, parse_peers
from main import VERSION


def test_parse_peers_normalize_dedupe():
    raw = (
        " http://127.0.0.1:8001/,https://creer-packs.example.com,"
        "http://127.0.0.1:8001,ftp://bad.example,not-a-url,,https://creer-packs.example.com/ "
    )
    peers = parse_peers(raw)
    assert peers == [
        "http://127.0.0.1:8001",
        "https://creer-packs.example.com",
    ]


def test_parse_peers_from_config(monkeypatch):
    monkeypatch.setattr(
        fed,
        "CREER_REGISTRY_PEERS",
        "https://a.example/,https://b.example",
    )
    assert parse_peers() == ["https://a.example", "https://b.example"]


def test_list_federated_mocked_peer(monkeypatch):
    monkeypatch.setattr(
        fed,
        "CREER_REGISTRY_PEERS",
        "http://peer.test:9000",
    )

    peer_item = {
        "id": "peer-only-pack",
        "name": "Peer Pack",
        "description": "from peer",
        "stack": "python",
        "version": "1.0.0",
        "source": "bundled",
        "files": ["README.md"],
        "download_url": "/registry/packs/peer-only-pack/download",
        "install_url": "/registry/packs/peer-only-pack/download",
    }

    def fake_fetch(base_url, *, q=None, source=None, timeout=8.0):
        assert base_url == "http://peer.test:9000"
        return [
            {
                **peer_item,
                "peer": base_url,
                "download_url": f"{base_url}/registry/packs/peer-only-pack/download",
                "install_url": f"{base_url}/registry/packs/peer-only-pack/download",
            }
        ], None

    monkeypatch.setattr(fed, "_fetch_peer_registry", fake_fetch)

    result = list_federated()
    assert result["version"] == "0.9.0"
    assert "items" in result["local"]
    assert len(result["peers"]) == 1
    assert result["peers"][0]["ok"] is True
    assert result["peers"][0]["count"] == 1
    assert result["peers"][0]["error"] is None

    ids = [i["id"] for i in result["items"]]
    assert "peer-only-pack" in ids
    # Local packs come first
    local_ids = {i["id"] for i in result["local"]["items"]}
    assert ids[: len(local_ids)] == [i["id"] for i in result["local"]["items"]]

    peer_entry = next(i for i in result["items"] if i["id"] == "peer-only-pack")
    assert peer_entry["peer"] == "http://peer.test:9000"
    assert peer_entry["download_url"].startswith("http://peer.test:9000/")


def test_peer_failure_keeps_local(monkeypatch):
    monkeypatch.setattr(
        fed,
        "CREER_REGISTRY_PEERS",
        "http://dead.peer:9999",
    )

    def fake_fetch(base_url, *, q=None, source=None, timeout=8.0):
        return [], "connection refused"

    monkeypatch.setattr(fed, "_fetch_peer_registry", fake_fetch)

    result = list_federated()
    assert result["version"] == "0.9.0"
    local_count = len(result["local"]["items"])
    assert local_count >= 3
    assert len(result["items"]) == local_count
    assert result["peers"][0]["ok"] is False
    assert result["peers"][0]["count"] == 0
    assert "connection refused" in (result["peers"][0]["error"] or "")


def test_dedupe_prefers_local(monkeypatch):
    monkeypatch.setattr(
        fed,
        "CREER_REGISTRY_PEERS",
        "http://peer.test:9000",
    )

    def fake_fetch(base_url, *, q=None, source=None, timeout=8.0):
        # Overlap with bundled fastapi-crud id
        return [
            {
                "id": "fastapi-crud",
                "name": "Peer FastAPI",
                "peer": base_url,
                "download_url": f"{base_url}/registry/packs/fastapi-crud/download",
            }
        ], None

    monkeypatch.setattr(fed, "_fetch_peer_registry", fake_fetch)
    result = list_federated()
    matches = [i for i in result["items"] if i["id"] == "fastapi-crud"]
    assert len(matches) == 1
    assert matches[0].get("peer") is None  # local wins


def test_health_0_9_and_federated_route(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "https://a.example,https://b.example")
    # Also patch config import used if parse_peers reads module-level — already patched fed
    c = TestClient(main.app)
    h = c.get("/health").json()
    assert h["version"] == "0.9.0"
    assert VERSION == "0.9.0"
    assert h["peers_configured"] == 2

    # No live peers — empty mock via monkeypatch on fetch
    monkeypatch.setattr(
        fed,
        "_fetch_peer_registry",
        lambda *a, **k: ([], "offline"),
    )
    r = c.get("/registry/federated")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.0"
    assert "local" in body
    assert len(body["items"]) == len(body["local"]["items"])


def test_fetch_peer_registry_absolutizes(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "items": [
                    {
                        "id": "remote-pack",
                        "download_url": "/registry/packs/remote-pack/download",
                        "install_url": "/registry/packs/remote-pack/download",
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            assert url == "http://peer.example/registry"
            return FakeResp()

    monkeypatch.setattr(fed.httpx, "Client", FakeClient)
    items = fed.fetch_peer_registry("http://peer.example")
    assert len(items) == 1
    assert items[0]["peer"] == "http://peer.example"
    assert items[0]["download_url"] == "http://peer.example/registry/packs/remote-pack/download"
