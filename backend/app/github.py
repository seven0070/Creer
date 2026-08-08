"""Optional GitHub REST helper for creating repositories."""

from __future__ import annotations

import httpx


def create_github_repo(
    token: str,
    name: str,
    private: bool = True,
    description: str = "",
) -> dict:
    """
    Create a GitHub repository for the authenticated user.

    Returns dict with html_url, clone_url, and full_name.
    Raises ValueError on auth/API failures.
    """
    if not token or not isinstance(token, str):
        raise ValueError("GitHub token is required")
    if not name or not isinstance(name, str):
        raise ValueError("Repository name is required")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Creer/0.2",
    }
    payload = {
        "name": name,
        "private": private,
        "description": description or "",
        "auto_init": False,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                "https://api.github.com/user/repos",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise ValueError(f"GitHub request failed: {exc}") from exc

    if resp.status_code == 401:
        raise ValueError("GitHub authentication failed — check your token")
    if resp.status_code == 403:
        raise ValueError("GitHub forbidden — token may lack repo scope")
    if resp.status_code == 422:
        detail = resp.json().get("message", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise ValueError(f"GitHub rejected repo creation: {detail}")
    if resp.status_code >= 400:
        raise ValueError(f"GitHub API error ({resp.status_code}): {resp.text[:300]}")

    data = resp.json()
    return {
        "html_url": data.get("html_url", ""),
        "clone_url": data.get("clone_url", ""),
        "full_name": data.get("full_name", ""),
    }
