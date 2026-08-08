"""Tests for GET /doctor diagnostics (v1.4)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import main
from app import auth as auth_mod
from app import doctor as doctor_mod
from main import VERSION


EXPECTED_CHECK_IDS = [
    "health",
    "offline",
    "llm",
    "packs",
    "peers",
    "auth",
    "trust",
    "tls",
]


def test_doctor_shape_and_version():
    c = TestClient(main.app)
    resp = c.get("/doctor")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "1.4.0"
    assert VERSION == "1.4.0"
    assert "ok" in body
    assert isinstance(body["ok"], bool)
    assert isinstance(body["checks"], list)
    assert [ch["id"] for ch in body["checks"]] == EXPECTED_CHECK_IDS
    for ch in body["checks"]:
        assert "ok" in ch and "detail" in ch
        assert isinstance(ch["ok"], bool)
        assert isinstance(ch["detail"], str)
        assert ch["detail"]  # no empty details
    health = body["health"]
    assert health["version"] == "1.4.0"
    assert health["status"] == "ok"
    assert "offline" in health
    assert "packs_count" in health
    assert "tls_server_configured" in health
    assert "mtls_client_configured" in health


def test_doctor_ok_matches_all_checks():
    c = TestClient(main.app)
    body = c.get("/doctor").json()
    assert body["ok"] is all(ch["ok"] for ch in body["checks"])


def test_doctor_llm_ok_when_offline(monkeypatch):
    monkeypatch.setattr(doctor_mod, "CREER_OFFLINE", True)
    monkeypatch.setattr(doctor_mod, "OPENAI_API_KEY", None)
    monkeypatch.setattr(doctor_mod, "OPENAI_BASE_URL", None)
    report = doctor_mod.run_doctor("1.4.0")
    llm = next(ch for ch in report["checks"] if ch["id"] == "llm")
    assert llm["ok"] is True
    assert "offline" in llm["detail"].lower()
    assert report["ok"] is True


def test_doctor_llm_ok_when_key_set(monkeypatch):
    monkeypatch.setattr(doctor_mod, "CREER_OFFLINE", False)
    monkeypatch.setattr(doctor_mod, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(doctor_mod, "OPENAI_BASE_URL", None)
    report = doctor_mod.run_doctor("1.4.0")
    llm = next(ch for ch in report["checks"] if ch["id"] == "llm")
    assert llm["ok"] is True
    assert "OPENAI_API_KEY set" in llm["detail"]


def test_doctor_llm_ok_when_base_url_set(monkeypatch):
    monkeypatch.setattr(doctor_mod, "CREER_OFFLINE", False)
    monkeypatch.setattr(doctor_mod, "OPENAI_API_KEY", None)
    monkeypatch.setattr(doctor_mod, "OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
    report = doctor_mod.run_doctor("1.4.0")
    llm = next(ch for ch in report["checks"] if ch["id"] == "llm")
    assert llm["ok"] is True
    assert "BASE_URL set" in llm["detail"]


def test_doctor_llm_fail_without_config(monkeypatch):
    monkeypatch.setattr(doctor_mod, "CREER_OFFLINE", False)
    monkeypatch.setattr(doctor_mod, "OPENAI_API_KEY", None)
    monkeypatch.setattr(doctor_mod, "OPENAI_BASE_URL", None)
    report = doctor_mod.run_doctor("1.4.0")
    llm = next(ch for ch in report["checks"] if ch["id"] == "llm")
    assert llm["ok"] is False
    assert report["ok"] is False


def test_doctor_auth_detail_reflects_token(monkeypatch):
    monkeypatch.setattr(auth_mod, "CREER_REGISTRY_TOKEN", "secret-token")
    c = TestClient(main.app)
    body = c.get("/doctor").json()
    auth = next(ch for ch in body["checks"] if ch["id"] == "auth")
    assert auth["ok"] is True
    assert "required" in auth["detail"]
    assert body["health"]["auth_required"] is True

    monkeypatch.setattr(auth_mod, "CREER_REGISTRY_TOKEN", None)
    body2 = c.get("/doctor").json()
    auth2 = next(ch for ch in body2["checks"] if ch["id"] == "auth")
    assert "open" in auth2["detail"]
    assert body2["health"]["auth_required"] is False


def test_doctor_no_secrets_in_payload(monkeypatch):
    monkeypatch.setattr(doctor_mod, "OPENAI_API_KEY", "sk-super-secret-key")
    monkeypatch.setattr(auth_mod, "CREER_REGISTRY_TOKEN", "registry-secret")
    c = TestClient(main.app)
    raw = c.get("/doctor").text
    assert "sk-super-secret-key" not in raw
    assert "registry-secret" not in raw


def test_health_still_matches_doctor_health():
    c = TestClient(main.app)
    health = c.get("/health").json()
    doctor = c.get("/doctor").json()
    assert health == doctor["health"]
    assert health["version"] == "1.4.0"
