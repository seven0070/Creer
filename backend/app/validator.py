import re
from pathlib import Path

# Allowed: alphanum, dash, underscore, dot, slash
SAFE_PATH_RE = re.compile(r"^[a-zA-Z0-9_\-./]+$")
BLOCKED_PARTS = {".", "..", ".git", "node_modules", "__pycache__"}

def is_safe_path(file_path: str) -> bool:
    """Return True if path is safe to write (no traversal, no absolute, no blocked)."""
    if not file_path or not isinstance(file_path, str):
        return False
    # no absolute
    if file_path.startswith("/") or file_path.startswith("\\"):
        return False
    # no windows absolute like C:\
    if re.match(r"^[a-zA-Z]:[/\\]", file_path):
        return False
    # no traversal sequences
    if ".." in Path(file_path).parts:
        return False
    if "\\" in file_path:
        return False
    if "//" in file_path:
        return False
    if not SAFE_PATH_RE.match(file_path):
        return False
    parts = Path(file_path).parts
    for p in parts:
        if p in BLOCKED_PARTS:
            return False
        if p.startswith("."):
            # allow .env.example, .gitignore but block hidden traversal
            if p not in {".env.example", ".gitignore"}:
                # allow dotfiles at root like .gitignore, .env.example
                # but disallow hidden folders/files like .secrets
                if p.startswith("."):
                    # we already handle allowed list, otherwise block hidden
                    if p not in (".env.example", ".gitignore"):
                        # block any other hidden file
                        return False
    # no empty segments, no trailing slash
    if file_path.endswith("/") or file_path.endswith("."):
        return False
    if len(file_path) > 200:
        return False
    return True


def validate_plan(plan: dict) -> dict:
    """Validate and sanitize plan returned by LLM."""
    if not isinstance(plan, dict):
        raise ValueError("Plan must be a dict")
    if "project_name" not in plan or "files" not in plan:
        raise ValueError("Plan missing project_name or files")
    project_name = plan["project_name"]
    if not isinstance(project_name, str) or not project_name:
        raise ValueError("Invalid project_name")
    # sanitize project_name -> slug
    # allow alphanum, dash, underscore
    slug = re.sub(r"[^a-zA-Z0-9_\-]", "-", project_name.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-_")
    if not slug:
        slug = "creer-project"
    if len(slug) > 50:
        slug = slug[:50].strip("-_")
    plan["project_name"] = slug

    if not isinstance(plan["files"], list):
        raise ValueError("files must be a list")
    # filter unsafe paths, deduplicate, limit
    safe_files = []
    seen = set()
    for f in plan["files"]:
        if not isinstance(f, str):
            continue
        f = f.strip()
        if not f or f in seen:
            continue
        if is_safe_path(f):
            safe_files.append(f)
            seen.add(f)
        if len(safe_files) >= 60:
            break
    if not safe_files:
        raise ValueError("No valid files in plan")
    plan["files"] = safe_files
    # ensure stack exists
    if "stack" not in plan or not isinstance(plan["stack"], str):
        plan["stack"] = "generic"
    return plan


def validate_file_path(file_path: str) -> str:
    if not is_safe_path(file_path):
        raise ValueError(f"Unsafe file path: {file_path}")
    return file_path
