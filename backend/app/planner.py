from openai import OpenAI
import json
import re
from config import OPENAI_API_KEY, MODEL

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _parse_json(content: str) -> dict:
    """Parse model JSON, tolerating optional markdown fences."""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def plan_project(idea: str) -> dict:
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
- project_name must be a valid folder name (lowercase, hyphens ok)
- files should be a focused, production-ready starter set (typically 5–15 files)
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
