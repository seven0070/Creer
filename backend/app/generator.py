from openai import OpenAI
from config import OPENAI_API_KEY, MODEL

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def generate_files(plan: dict) -> dict[str, str]:
    """Generate file contents one-by-one from a project plan."""
    files_output: dict[str, str] = {}

    for file_path in plan["files"]:
        prompt = f"""
Generate the full content for file: {file_path}

Project Stack: {plan["stack"]}
Project Name: {plan["project_name"]}

Follow best practices.
Return ONLY the file content — no markdown fences, no explanation.
"""

        response = _get_client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        content = response.choices[0].message.content or ""
        # Strip accidental markdown fences
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        files_output[file_path] = content

    return files_output
