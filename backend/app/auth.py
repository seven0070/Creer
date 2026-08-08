"""Optional registry write auth — Bearer or X-Creer-Token when CREER_REGISTRY_TOKEN is set."""

from __future__ import annotations

from fastapi import Header, HTTPException

from config import CREER_REGISTRY_TOKEN as _TOKEN_FROM_CONFIG

# Module-level binding so tests can monkeypatch app.auth.CREER_REGISTRY_TOKEN
CREER_REGISTRY_TOKEN = _TOKEN_FROM_CONFIG


def registry_auth_required() -> bool:
    """True when mutating registry/pack endpoints require a token."""
    return bool(CREER_REGISTRY_TOKEN)


def _extract_token(
    authorization: str | None,
    x_creer_token: str | None,
) -> str | None:
    if x_creer_token and x_creer_token.strip():
        return x_creer_token.strip()
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
            return token or None
        stripped = authorization.strip()
        return stripped or None
    return None


def require_registry_write(
    authorization: str | None = Header(default=None),
    x_creer_token: str | None = Header(default=None, alias="X-Creer-Token"),
) -> None:
    """
    Gate mutating registry/pack endpoints.

    If CREER_REGISTRY_TOKEN is unset/empty → allow.
    Otherwise require Authorization: Bearer <token> or X-Creer-Token.
    """
    expected = CREER_REGISTRY_TOKEN
    if not expected:
        return

    provided = _extract_token(authorization, x_creer_token)
    if provided != expected:
        raise HTTPException(
            status_code=401,
            detail="Registry write authentication required",
        )
