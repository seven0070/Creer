"""Tests for optional registry write auth + one-hop discovery (v1.0)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

import main
from app import auth as auth_mod
from app import federation as fed
from app import packs as packs_mod
from app.federation import expand_peers_one_hop, list_federated
from main import VERSION


SAMPLE_PACK = {
    "id": "auth-demo-pack",
    "name": "Auth Demo",
    "description": "Installed via auth tests",
    "stack": "demo",
    "version": "1.0.0",
    "files": ["README.md"],
}


def test_install_without_token_still_works(tmp_path, monkeypatch):
    """When CREER_REGISTRY_TOKEN is unset, install works as before."""
    target = tmp_path / "installed"
    target.mkdir()
    monkeypatch.setenv("CREER_PACKS_DIR", str(target))
    monkeypatch.setattr(auth_mod, "CREER_REGISTRY_TOKEN", None)

    body = json.dumps(SAMPLE_PACK).encode("utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}

        def iter_bytes(self):
            yield body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            return FakeResponse()

    monkeypatch.setattr(packs_mod.httpx, "Client", FakeClient)
    c = TestClient(main.app)
    resp = c.post(
        "/packs/install",
        json={"url": "https://example.com/packs/auth-demo-pack.json", "overwrite": True},
    )
    assert resp.status_code == 200
    assert resp.json()["installed"] is True
    assert resp.json()["pack"]["id"] == "auth-demo-pack"


def test_install_requires_auth_when_token_set(tmp_path, monkeypatch):
    target = tmp_path / "installed"
    target.mkdir()
    monkeypatch.setenv("CREER_PACKS_DIR", str(target))
    monkeypatch.setattr(auth_mod, "CREER_REGISTRY_TOKEN", "secret-token")

    body = json.dumps(SAMPLE_PACK).encode("utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}

        def iter_bytes(self):
            yield body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            return FakeResponse()

    monkeypatch.setattr(packs_mod.httpx, "Client", FakeClient)
    c = TestClient(main.app)

    denied = c.post(
        "/packs/install",
        json={"url": "https://example.com/packs/auth-demo-pack.json", "overwrite": True},
    )
    assert denied.status_code == 401

    wrong = c.post(
        "/packs/install",
        json={"url": "https://example.com/packs/auth-demo-pack.json", "overwrite": True},
        headers={"Authorization": "Bearer wrong"},
    )
    assert wrong.status_code == 401

    ok = c.post(
        "/packs/install",
        json={"url": "https://example.com/packs/auth-demo-pack.json", "overwrite": True},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert ok.status_code == 200
    assert ok.json()["installed"] is True


def test_install_accepts_x_creer_token(tmp_path, monkeypatch):
    target = tmp_path / "installed"
    target.mkdir()
    monkeypatch.setenv("CREER_PACKS_DIR", str(target))
    monkeypatch.setattr(auth_mod, "CREER_REGISTRY_TOKEN", "header-secret")

    body = json.dumps({**SAMPLE_PACK, "id": "x-token-pack"}).encode("utf-8")

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}

        def iter_bytes(self):
            yield body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            return FakeResponse()

    monkeypatch.setattr(packs_mod.httpx, "Client", FakeClient)
    c = TestClient(main.app)
    ok = c.post(
        "/packs/install",
        json={"url": "https://example.com/packs/x-token-pack.json", "overwrite": True},
        headers={"X-Creer-Token": "header-secret"},
    )
    assert ok.status_code == 200


def test_delete_and_probe_require_auth(monkeypatch):
    monkeypatch.setattr(auth_mod, "CREER_REGISTRY_TOKEN", "probe-secret")
    c = TestClient(main.app)

    assert c.delete("/packs/nope").status_code == 401
    assert c.post("/registry/peers/probe", json={"url": "http://peer.example"}).status_code == 401

    # Reads stay public
    assert c.get("/registry").status_code == 200
    assert c.get("/health").status_code == 200
    assert c.get("/health").json()["auth_required"] is True


def test_discover_endpoint_shape(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "http://a.example,http://b.example")
    monkeypatch.setattr(auth_mod, "CREER_REGISTRY_TOKEN", "tok")
    monkeypatch.setattr(fed, "CREER_PUBLIC_BASE_URL", "http://me.example:8000")
    c = TestClient(main.app)
    r = c.get("/registry/discover")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1.0.0"
    assert body["base_url"] == "http://me.example:8000"
    assert isinstance(body["packs_count"], int)
    assert body["packs_count"] >= 0
    assert body["peers"] == ["http://a.example", "http://b.example"]
    assert body["auth_required"] is True


def test_discover_auth_required_false(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "")
    monkeypatch.setattr(auth_mod, "CREER_REGISTRY_TOKEN", None)
    monkeypatch.setattr(fed, "CREER_PUBLIC_BASE_URL", None)
    c = TestClient(main.app)
    body = c.get("/registry/discover").json()
    assert body["auth_required"] is False
    assert body["base_url"] is None
    assert body["peers"] == []


def test_federated_discover_expands_peers(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "http://seed.example")

    def fake_discover(base_url, *, timeout=3.0):
        if base_url == "http://seed.example":
            return {
                "version": "1.0.0",
                "peers": ["http://hop.example", "http://seed.example"],
                "packs_count": 1,
                "auth_required": False,
            }, None
        return None, "unreachable"

    def fake_fetch(base_url, *, q=None, source=None, timeout=8.0):
        if base_url == "http://seed.example":
            return (
                [
                    {
                        "id": "seed-pack",
                        "name": "Seed",
                        "peer": base_url,
                        "download_url": f"{base_url}/registry/packs/seed-pack/download",
                    }
                ],
                None,
            )
        if base_url == "http://hop.example":
            return (
                [
                    {
                        "id": "hop-pack",
                        "name": "Hop",
                        "peer": base_url,
                        "download_url": f"{base_url}/registry/packs/hop-pack/download",
                    }
                ],
                None,
            )
        return [], "unknown"

    monkeypatch.setattr(fed, "fetch_peer_discover", fake_discover)
    monkeypatch.setattr(fed, "_fetch_peer_registry", fake_fetch)

    result = list_federated(discover=True)
    assert result["version"] == "1.0.0"
    assert result["discovered_peers"] == ["http://hop.example"]
    peer_urls = [p["base_url"] for p in result["peers"]]
    assert peer_urls == ["http://seed.example", "http://hop.example"]
    ids = {i["id"] for i in result["items"]}
    assert "seed-pack" in ids
    assert "hop-pack" in ids


def test_federated_discover_false_no_expansion(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "http://seed.example")

    def boom(*a, **k):
        raise AssertionError("discover should not be called")

    monkeypatch.setattr(fed, "fetch_peer_discover", boom)
    monkeypatch.setattr(
        fed,
        "_fetch_peer_registry",
        lambda *a, **k: ([], None),
    )
    result = list_federated(discover=False)
    assert result["discovered_peers"] == []
    assert [p["base_url"] for p in result["peers"]] == ["http://seed.example"]


def test_federated_discover_query_param(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "http://seed.example")

    def fake_discover(base_url, *, timeout=3.0):
        return {"peers": ["http://extra.example"]}, None

    monkeypatch.setattr(fed, "fetch_peer_discover", fake_discover)
    monkeypatch.setattr(fed, "_fetch_peer_registry", lambda *a, **k: ([], None))

    c = TestClient(main.app)
    r = c.get("/registry/federated", params={"discover": "true"})
    assert r.status_code == 200
    body = r.json()
    assert body["discovered_peers"] == ["http://extra.example"]
    assert any(p["base_url"] == "http://extra.example" for p in body["peers"])


def test_expand_peers_respects_cap(monkeypatch):
    seeds = [f"http://s{i}.example" for i in range(6)]

    def fake_discover(base_url, *, timeout=3.0):
        # Each seed advertises many peers
        return {
            "peers": [f"http://n{i}.example" for i in range(10)],
        }, None

    monkeypatch.setattr(fed, "fetch_peer_discover", fake_discover)
    expanded, discovered = expand_peers_one_hop(seeds)
    assert len(expanded) == 8
    assert len(discovered) == 2
    assert all(d.startswith("http://n") for d in discovered)


def test_health_1_0(monkeypatch):
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "https://a.example")
    monkeypatch.setattr(auth_mod, "CREER_REGISTRY_TOKEN", None)
    c = TestClient(main.app)
    h = c.get("/health").json()
    assert h["version"] == "1.0.0"
    assert VERSION == "1.0.0"
    assert h["peers_configured"] == 1
    assert h["auth_required"] is False
    assert h["status"] == "ok"
