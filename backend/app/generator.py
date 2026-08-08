from config import OPENAI_API_KEY, MODEL
from app.validator import validate_file_path

_client = None

def _get_client():
    global _client
    if _client is not None:
        return _client
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")
    from openai import OpenAI
    _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def generate_files(plan: dict) -> dict:
    """
    Generate file contents one-by-one from plan.
    plan: {project_name, stack, files}
    Returns: dict[file_path -> content]
    """
    if not plan or "files" not in plan:
        raise ValueError("Invalid plan")
    
    client = _get_client()
    stack = plan.get("stack", "generic")
    project_name = plan.get("project_name", "app")

    files_output = {}

    for file_path in plan["files"]:
        # safety check again
        validate_file_path(file_path)

        prompt = f"""
Generate the FULL content for file: {file_path}

Project Name: {project_name}
Project Stack: {stack}
Full file list: {', '.join(plan['files'])}

Requirements:
- Follow best practices for the stack
- Production-ready, clean code
- Include necessary imports
- If file is README.md, include project title, description, setup instructions
- If file is .gitignore, include appropriate ignores
- Return ONLY the file content, no markdown fences, no explanation, no preamble
- Do not wrap in ``` code blocks
"""

        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = response.choices[0].message.content
        if content is None:
            content = ""
        # Strip outer fences if model still adds them (defensive)
        content_stripped = content.strip()
        if content_stripped.startswith("```"):
            # remove first line fence and last fence
            lines = content_stripped.splitlines()
            # drop first line if it's fence
            if lines[0].startswith("```"):
                lines = lines[1:]
            # drop last line if fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
            # if file had language tag line removed, content now correct
            # ensure not adding extra markdown
        files_output[file_path] = content

    return files_output
