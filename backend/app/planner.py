import json
import re
from config import OPENAI_API_KEY, MODEL
from app.validator import validate_plan

_client = None

def _get_client():
    global _client
    if _client is not None:
        return _client
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set. Set it in backend/.env or env var.")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError("openai package not installed. Run pip install -r requirements.txt") from e
    _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _extract_json(content: str) -> str:
    """Strip markdown fences and extract JSON object."""
    content = content.strip()
    # Remove ```json ... ``` or ``` ... ```
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        content = content.strip()
    # If still contains extra text, try to find first { and last }
    if not content.startswith("{"):
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            content = m.group(0)
    return content


def plan_project(idea: str) -> dict:
    """
    Convert idea into project plan via OpenAI.
    Returns dict with keys: project_name, stack, files
    """
    if not idea or not idea.strip():
        raise ValueError("Idea cannot be empty")

    client = _get_client()

    prompt = f"""
You are a senior software architect.

Convert the following idea into a clean project structure.

Return ONLY valid JSON (no markdown, no explanation) with this shape:
{{
  "project_name": "kebab-case-or-snake_case short name (no spaces)",
  "stack": "e.g. fastapi, nextjs, express-ts, python-cli",
  "files": ["path/to/file.py", "path/to/file2.md", ...]
}}

Rules:
- project_name must be filesystem-safe (lowercase, hyphens/underscores, no spaces)
- stack should be the primary tech choice for the idea
- files: 5-20 files, include README.md, .gitignore, and core source files
- Use conventional paths (e.g. app/main.py, src/index.ts, requirements.txt)
- No absolute paths, no .. , no hidden files except .gitignore/.env.example

Idea: {idea.strip()}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    raw = response.choices[0].message.content
    if not raw:
        raise ValueError("Empty response from LLM")
    json_str = _extract_json(raw)
    try:
        plan = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}\nRaw: {raw[:500]}") from e

    # Validate and sanitize
    return validate_plan(plan)
