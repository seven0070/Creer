"""Creer v0.6 marketplace / remote pack install tests (offline)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure offline before importing the app
os.environ["CREER_OFFLINE"] = "1"
# Isolate installs into a temp dir via fixture; clear CREER_PACKS_DIR by default
os.environ.pop("CREER_PACKS_DIR", None)

from app import packs as packs_mod
from main import VERSION, app


SAMPLE_PACK = {
    "id": "marketplace-demo",
    "name": "Marketplace Demo",
    "description": "Installed via tests",
    "stack": "demo",
    "version": "1.0.0",
    "files": ["README.md", "main.py"],
}


@pytest.fixture()
def install_dir(tmp_path, monkeypatch):
    """Point writable installs at a temp directory (not repo packs/)."""
    target = tmp_path / "installed"
    target.mkdir()
    monkeypatch.setenv("CREER_PACKS_DIR", str(target))
    # Also keep INSTALLED_DIR clean conceptually — writable_packs_dir uses env
    yield target


@pytest.fixture()
def client(install_dir):
    return TestClient(app)


def test_health_version_0_9(client, monkeypatch):
    monkeypatch.setattr("app.doctor.CREER_OFFLINE", True)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "1.4.0"
    assert VERSION == "1.4.0"
    assert data["offline"] is True
    assert data["packs_count"] >= 3
    assert "peers_configured" in data


def test_marketplace_catalog(client):
    resp = client.get("/marketplace")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 4
    bundled = [i for i in items if i.get("source") == "bundled"]
    remote = [i for i in items if i.get("source") == "remote"]
    assert len(bundled) == 3
    assert {b["id"] for b in bundled} == {"fastapi-crud", "python-lib", "express-ts"}
    assert len(remote) >= 1
    assert all("url" in r for r in remote)


def test_install_pack_from_bytes(install_dir):
    body = json.dumps(SAMPLE_PACK).encode("utf-8")
    installed = packs_mod.install_pack_from_bytes(body, overwrite=False)
    assert installed["id"] == "marketplace-demo"
    assert (install_dir / "marketplace-demo.json").is_file()
    ids = {p["id"] for p in packs_mod.list_packs()}
    assert "marketplace-demo" in ids


def test_install_endpoint_mocked_httpx(client, install_dir, monkeypatch):
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
            assert method == "GET"
            assert url.startswith("https://")
            return FakeResponse()

    monkeypatch.setattr(packs_mod.httpx, "Client", FakeClient)

    resp = client.post(
        "/packs/install",
        json={"url": "https://example.com/packs/marketplace-demo.json", "overwrite": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["installed"] is True
    assert data["pack"]["id"] == "marketplace-demo"

    packs = client.get("/packs").json()["packs"]
    assert any(p["id"] == "marketplace-demo" for p in packs)


def test_install_overwrite_false_conflict(client, install_dir, monkeypatch):
    packs_mod.install_pack(SAMPLE_PACK, overwrite=False)
    with pytest.raises(packs_mod.PackConflictError):
        packs_mod.install_pack(SAMPLE_PACK, overwrite=False)

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
    resp = client.post(
        "/packs/install",
        json={
            "url": "https://example.com/packs/marketplace-demo.json",
            "overwrite": False,
        },
    )
    assert resp.status_code == 409


def test_delete_installed_only(client, install_dir):
    packs_mod.install_pack(SAMPLE_PACK, overwrite=True)
    assert any(p["id"] == "marketplace-demo" for p in packs_mod.list_packs())

    resp = client.delete("/packs/marketplace-demo")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert not (install_dir / "marketplace-demo.json").exists()
    assert not any(p["id"] == "marketplace-demo" for p in packs_mod.list_packs())

    # Built-in cannot be deleted via writable dir
    resp = client.delete("/packs/fastapi-crud")
    assert resp.status_code == 404
    # Still listed (bundled)
    assert any(p["id"] == "fastapi-crud" for p in client.get("/packs").json()["packs"])


def test_reject_non_http_scheme():
    with pytest.raises(ValueError, match="http/https"):
        packs_mod.validate_remote_pack_url("file:///etc/passwd")
    with pytest.raises(ValueError, match="http/https"):
        packs_mod.validate_remote_pack_url("ftp://example.com/pack.json")


def test_parse_yaml_pack():
    text = """
id: yaml-demo
name: YAML Demo
description: from yaml
stack: yaml
version: "1.0.0"
files:
  - README.md
"""
    pack = packs_mod.parse_pack_content(text, "pack.yaml")
    assert pack["id"] == "yaml-demo"
