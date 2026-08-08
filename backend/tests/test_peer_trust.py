"""Tests for signed peer trust via shared HMAC (v1.2)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import main
from app import federation as fed
from app import peer_policy as policy
from app import peer_trust as trust
from app.federation import list_federated
from app.peer_trust import (
    evaluate_peer_trust,
    sign_payload,
    trust_enabled,
    trust_mode,
    verify_payload,
)
from main import VERSION


def _allow_fake_hosts(monkeypatch):
    monkeypatch.setattr(policy, "CREER_ALLOW_PRIVATE_PEERS", True)
    monkeypatch.setattr(policy, "CREER_PEER_ALLOWLIST", "")
    monkeypatch.setattr(policy, "CREER_PEER_DENYLIST", "")
    monkeypatch.setattr(policy, "is_private_or_unsafe_host", lambda host: False)


def test_sign_verify_roundtrip(monkeypatch):
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_SECRET", "shared-secret-v12")
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_MODE", "optional")

    payload = {"version": "1.5.0", "items": [{"id": "a"}], "base_url": None}
    signed = sign_payload(payload)
    assert "trust" in signed
    assert signed["trust"]["alg"] == "HMAC-SHA256"
    assert signed["trust"]["kid"] == "default"
    assert isinstance(signed["trust"]["sig"], str)
    assert len(signed["trust"]["sig"]) == 64

    status, err = verify_payload(signed)
    assert status == "signed"
    assert err is None
    assert trust_enabled() is True


def test_tamper_detection(monkeypatch):
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_SECRET", "shared-secret-v12")
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_MODE", "optional")

    signed = sign_payload({"version": "1.5.0", "items": [{"id": "a"}]})
    tampered = dict(signed)
    tampered["items"] = [{"id": "evil"}]
    status, err = verify_payload(tampered)
    assert status == "invalid"
    assert err is not None

    bad_sig = dict(signed)
    bad_sig["trust"] = dict(signed["trust"])
    bad_sig["trust"]["sig"] = "0" * 64
    status2, err2 = verify_payload(bad_sig)
    assert status2 == "invalid"
    assert err2 is not None


def test_required_mode_rejects_unsigned(monkeypatch):
    _allow_fake_hosts(monkeypatch)
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_SECRET", "shared-secret-v12")
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_MODE", "required")
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "http://peer.example")

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "version": "1.5.0",
                "items": [{"id": "remote", "download_url": "/x"}],
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            return FakeResp()

    monkeypatch.setattr(fed, "peer_httpx_client", lambda timeout=8.0, **k: FakeClient())
    result = list_federated()
    assert len(result["peers"]) == 1
    meta = result["peers"][0]
    assert meta["ok"] is False
    assert meta["trust_status"] == "unsigned"
    assert meta["error"]
    assert meta["count"] == 0
    assert not any(i.get("id") == "remote" for i in result["items"])


def test_optional_accepts_unsigned(monkeypatch):
    _allow_fake_hosts(monkeypatch)
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_SECRET", "shared-secret-v12")
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_MODE", "optional")
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "http://peer.example")

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "version": "1.5.0",
                "items": [
                    {
                        "id": "remote-pack",
                        "download_url": "/registry/packs/remote-pack/download",
                    }
                ],
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            return FakeResp()

    monkeypatch.setattr(fed, "peer_httpx_client", lambda timeout=8.0, **k: FakeClient())
    result = list_federated()
    meta = result["peers"][0]
    assert meta["ok"] is True
    assert meta["trust_status"] == "unsigned"
    assert meta["error"] is None
    assert any(i.get("id") == "remote-pack" for i in result["items"])


def test_optional_rejects_invalid_sig(monkeypatch):
    _allow_fake_hosts(monkeypatch)
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_SECRET", "shared-secret-v12")
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_MODE", "optional")
    monkeypatch.setattr(fed, "CREER_REGISTRY_PEERS", "http://peer.example")

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "version": "1.5.0",
                "items": [{"id": "remote"}],
                "trust": {"alg": "HMAC-SHA256", "kid": "default", "sig": "ab" * 32},
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            return FakeResp()

    monkeypatch.setattr(fed, "peer_httpx_client", lambda timeout=8.0, **k: FakeClient())
    result = list_federated()
    meta = result["peers"][0]
    assert meta["ok"] is False
    assert meta["trust_status"] == "invalid"
    assert meta["error"]


def test_off_skips(monkeypatch):
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_SECRET", "shared-secret-v12")
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_MODE", "off")
    assert trust_mode() == "off"

    unsigned = {"version": "1.5.0", "items": []}
    status, err = verify_payload(unsigned)
    assert status == "skipped"
    assert err is None

    pol_status, pol_err = evaluate_peer_trust(unsigned)
    assert pol_status == "skipped"
    assert pol_err is None

    # Outbound still signed when secret set
    signed = sign_payload(unsigned)
    assert "trust" in signed


def test_health_shows_mode(monkeypatch):
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_SECRET", "s3cret")
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_MODE", "optional")
    # health reads trust_mode/trust_enabled from peer_trust module via imports in main
    c = TestClient(main.app)
    h = c.get("/health").json()
    assert h["version"] == "1.5.0"
    assert h["peer_trust_mode"] == "optional"
    assert h["peer_trust_signing"] is True
    assert "s3cret" not in str(h)


def test_discover_and_registry_sign_when_secret(monkeypatch):
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_SECRET", "shared-secret-v12")
    monkeypatch.setattr(trust, "CREER_PEER_TRUST_MODE", "off")
    c = TestClient(main.app)

    discover = c.get("/registry/discover").json()
    assert "trust" in discover
    assert discover["trust"]["alg"] == "HMAC-SHA256"
    status, err = verify_payload(discover)
    # mode off → skipped even with valid sig present
    assert status == "skipped"
    assert err is None

    monkeypatch.setattr(trust, "CREER_PEER_TRUST_MODE", "required")
    status2, err2 = verify_payload(discover)
    assert status2 == "signed"
    assert err2 is None

    registry = c.get("/registry").json()
    assert registry["version"] == "1.5.0"
    assert "trust" in registry
    assert verify_payload(registry)[0] == "signed"


def test_version_bump():
    assert VERSION == "1.5.0"
    assert fed.FEDERATION_VERSION == "1.5.0"
    c = TestClient(main.app)
    assert c.get("/health").json()["version"] == "1.5.0"
