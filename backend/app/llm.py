"""Shared OpenAI-compatible client for Creer."""

from __future__ import annotations

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_BASE_URL

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Lazy OpenAI client. Passes base_url when OPENAI_BASE_URL is set (Ollama, etc.)."""
    global _client
    if _client is None:
        if not OPENAI_API_KEY and not OPENAI_BASE_URL:
            raise ValueError(
                "OPENAI_API_KEY is not set (or set OPENAI_BASE_URL for a local OpenAI-compatible server)"
            )
        kwargs: dict = {"api_key": OPENAI_API_KEY or "not-needed"}
        if OPENAI_BASE_URL:
            kwargs["base_url"] = OPENAI_BASE_URL
        _client = OpenAI(**kwargs)
    return _client


def reset_client() -> None:
    """Clear the cached client (useful in tests)."""
    global _client
    _client = None
