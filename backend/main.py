from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.planner import plan_project
from app.generator import generate_files
from app.validator import validate_plan, validate_files
from app.templates import list_templates, get_template
from app.github import create_github_repo

VERSION = "0.2.0"

app = FastAPI(title="Creer", version=VERSION)


class PlanRequest(BaseModel):
    idea: str = Field(..., min_length=3, max_length=4000)
    template_id: str | None = None


class PlanBody(BaseModel):
    project_name: str
    stack: str | None = None
    files: list[str]
    template_id: str | None = None
    description: str | None = None


class GenerateRequest(BaseModel):
    idea: str = Field(..., min_length=3, max_length=4000)
    template_id: str | None = None
    plan: PlanBody | None = None


class GitHubCreateRepoRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    private: bool = True
    description: str = ""
    token: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION}


@app.get("/templates")
def templates():
    return {"templates": list_templates()}


@app.post("/plan")
def plan_only(request: PlanRequest):
    """Return a project plan without generating file contents."""
    try:
        if request.template_id and get_template(request.template_id) is None:
            raise ValueError(f"Unknown template_id: {request.template_id!r}")
        plan = plan_project(request.idea, template_id=request.template_id)
        validate_plan(plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Planning failed: {exc}") from exc

    result = {
        "project_name": plan["project_name"],
        "stack": plan.get("stack"),
        "files": plan["files"],
    }
    if plan.get("template_id"):
        result["template_id"] = plan["template_id"]
    if plan.get("description"):
        result["description"] = plan["description"]
    return result


@app.post("/generate")
def generate_project(request: GenerateRequest):
    try:
        if request.plan is not None:
            plan = request.plan.model_dump()
            # Drop nulls except keep stack as empty string for the generator prompt
            plan = {k: v for k, v in plan.items() if v is not None}
            plan.setdefault("stack", "")
            if request.template_id and "template_id" not in plan:
                plan["template_id"] = request.template_id
        else:
            if request.template_id and get_template(request.template_id) is None:
                raise ValueError(f"Unknown template_id: {request.template_id!r}")
            plan = plan_project(request.idea, template_id=request.template_id)

        validate_plan(plan)
        files = generate_files(plan)
        validate_files(files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

    result = {
        "project_name": plan["project_name"],
        "stack": plan.get("stack"),
        "files": files,
    }
    if plan.get("template_id"):
        result["template_id"] = plan["template_id"]
    return result


@app.post("/github/create-repo")
def github_create_repo(
    request: GitHubCreateRepoRequest,
    authorization: str | None = Header(default=None),
):
    """Create a GitHub repo. Prefer Authorization: Bearer <token>; body.token also accepted."""
    token = None
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
        else:
            token = authorization.strip()
    if not token:
        token = request.token
    if not token:
        raise HTTPException(
            status_code=401,
            detail="GitHub token required via Authorization: Bearer <token> or body.token",
        )

    try:
        result = create_github_repo(
            token=token,
            name=request.name,
            private=request.private,
            description=request.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"GitHub create failed: {exc}") from exc

    return result
