"""Project planner — AI-driven or template-based."""

from __future__ import annotations

import json
import re

from config import CREER_OFFLINE, MODEL, OPENAI_API_KEY, OPENAI_BASE_URL
from app.llm import _get_client
from app.packs import apply_pack, get_pack
from app.templates import apply_template, get_template, slugify


def _llm_configured() -> bool:
    """True when an OpenAI key or OpenAI-compatible base URL is available."""
    return bool(OPENAI_API_KEY or OPENAI_BASE_URL)


def _parse_json(content: str) -> dict:
    """Parse model JSON, tolerating optional markdown fences."""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _ai_plan(idea: str) -> dict:
    prompt = f"""
You are a senior software architect.

Convert the following idea into a clean project structure.

Return ONLY valid JSON (no markdown):
{{
    "project_name": "...",
    "stack": "...",
    "files": ["path/file.py", ...]
}}

Rules:
- project_name must be a valid folder name (lowercase, hyphens ok, no spaces)
- files should be a focused, production-ready starter set (typically 5–15 files, max 40)
- include README.md and a dependency manifest appropriate for the stack

Idea: {idea}
"""

    response = _get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    plan = _parse_json(response.choices[0].message.content)
    if not isinstance(plan.get("files"), list) or not plan.get("project_name"):
        raise ValueError("Planner returned an invalid plan structure")
    return plan


def _ai_name_project(idea: str, template: dict) -> str:
    """Optionally ask the model for a short project name; fall back to slugify."""
    try:
        prompt = f"""
Given this project idea and stack, return ONLY valid JSON:
{{"project_name": "short-kebab-case-name"}}

Rules:
- lowercase, hyphens ok, no spaces
- 2–40 characters preferred
- must be a valid folder name

Idea: {idea}
Stack: {template.get("stack", "")}
Template: {template.get("name", "")}
"""
        response = _get_client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        data = _parse_json(response.choices[0].message.content)
        name = data.get("project_name")
        if isinstance(name, str) and name.strip():
            return slugify(name)
    except Exception:
        pass
    return slugify(idea)


def plan_project(
    idea: str,
    template_id: str | None = None,
    pack_id: str | None = None,
) -> dict:
    """
    Build a project plan from an idea, optionally anchored to a pack or template.

    pack_id and template_id are mutually exclusive — both set raises ValueError.

    When pack_id or template_id is set:
    - files and stack come from the pack/template
    - project_name is derived deterministically via slugify (no API key required)
    - if an LLM is configured and not offline, AI may refine project_name only

    Without either: full AI planning (requires OPENAI_API_KEY or OPENAI_BASE_URL),
    unless offline — offline without pack_id or template_id raises ValueError.
    """
    if pack_id and template_id:
        raise ValueError("Provide pack_id or template_id, not both")

    if CREER_OFFLINE and not pack_id and not template_id:
        raise ValueError(
            "Offline mode requires pack_id or template_id. Pass a pack_id "
            "(see GET /packs) or template_id (see GET /templates) — AI planning "
            "is disabled when CREER_OFFLINE is set."
        )

    if pack_id:
        pack = get_pack(pack_id)
        if pack is None:
            raise ValueError(f"Unknown pack_id: {pack_id!r}")

        plan = apply_pack(pack_id, idea)

        if _llm_configured() and not CREER_OFFLINE:
            plan["project_name"] = _ai_name_project(idea, pack)

        return plan

    if template_id:
        tmpl = get_template(template_id)
        if tmpl is None:
            raise ValueError(f"Unknown template_id: {template_id!r}")

        plan = apply_template(template_id, idea)

        # Optionally refine name with AI when an LLM endpoint is available and not offline
        if _llm_configured() and not CREER_OFFLINE:
            plan["project_name"] = _ai_name_project(idea, tmpl)

        return plan

    if not _llm_configured() and not CREER_OFFLINE:
        # No LLM endpoint and no pack/template — cannot plan with AI
        raise ValueError(
            "OPENAI_API_KEY (or OPENAI_BASE_URL) is not set. Provide a pack_id "
            "or template_id for pack/template-only planning, or set "
            "CREER_OFFLINE=1 with a pack_id or template_id."
        )

    return _ai_plan(idea)
