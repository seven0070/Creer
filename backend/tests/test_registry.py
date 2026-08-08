"""Tests for self-hosted pack registry (v0.7)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

import main
from app.packs import install_pack, uninstall_pack


def test_health_registry_fields():
    c = TestClient(main.app)
    h = c.get("/health").json()
    assert h["version"] == "1.2.0"
    assert h["registry_count"] >= 3
    assert "peers_configured" in h


def test_registry_lists_and_search():
    c = TestClient(main.app)
    r = c.get("/registry")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 3
    assert all("download_url" in i for i in items)

    r = c.get("/registry", params={"q": "fastapi"})
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"]]
    assert "fastapi-crud" in ids

    r = c.get("/registry", params={"source": "bundled"})
    assert r.status_code == 200
    assert all(i["source"] == "bundled" for i in r.json()["items"])


def test_registry_download_and_reinstall():
    c = TestClient(main.app)
    r = c.get("/registry/packs/python-lib/download")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    pack = r.json()
    assert pack["id"] == "python-lib"
    assert isinstance(pack["files"], list) and pack["files"]

    # Install under a new id via bytes path (avoid conflicting with bundled id)
    data = dict(pack)
    data["id"] = "python-lib-copy"
    data["name"] = "Python Lib Copy"
    install_pack(data, overwrite=True)
    try:
        ids = [p["id"] for p in c.get("/packs").json()["packs"]]
        assert "python-lib-copy" in ids
        detail = c.get("/registry/packs/python-lib-copy")
        assert detail.status_code == 200
        assert detail.json()["source"] == "installed"
    finally:
        uninstall_pack("python-lib-copy")


def test_marketplace_enriched():
    c = TestClient(main.app)
    items = c.get("/marketplace").json()["items"]
    bundled = [i for i in items if i.get("source") == "bundled" and i["id"] == "fastapi-crud"]
    assert bundled
    # Local download URL attached when pack exists
    assert bundled[0].get("url") or bundled[0].get("download_url")
