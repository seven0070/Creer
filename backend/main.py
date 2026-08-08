"""Creer FastAPI application — plan, generate, stream, GitHub helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import CREER_OFFLINE, MODEL, OPENAI_BASE_URL
from app.bakeins import apply_bakeins
from app.planner import plan_project
from app.generator import generate_files, generate_files_iter
from app.validator import validate_plan, validate_files
from app.templates import list_templates, get_template
from app.github import create_github_repo

VERSION = "0.3.0"

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


def _resolve_plan(request: GenerateRequest) -> dict:
    """Resolve a validated plan from GenerateRequest (shared by sync + stream)."""
    if request.plan is not None:
        plan = request.plan.model_dump()
        plan = {k: v for k, v in plan.items() if v is not None}
        plan.setdefault("stack", "")
        if request.template_id and "template_id" not in plan:
            plan["template_id"] = request.template_id
    else:
        if request.template_id and get_template(request.template_id) is None:
            raise ValueError(f"Unknown template_id: {request.template_id!r}")
        plan = plan_project(request.idea, template_id=request.template_id)

    validate_plan(plan)
    return plan


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": VERSION,
        "offline": CREER_OFFLINE,
        "base_url_set": bool(OPENAI_BASE_URL),
        "model": MODEL,
    }


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
        plan = _resolve_plan(request)
        files = generate_files(plan)
        files = apply_bakeins(plan, files)
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


@app.post("/generate/stream")
def generate_project_stream(request: GenerateRequest):
    """Stream generation progress as Server-Sent Events (JSON data lines)."""

    def event_stream() -> Iterator[str]:
        plan: dict | None = None
        try:
            plan = _resolve_plan(request)
            file_list = list(plan["files"])
            yield _sse(
                {
                    "event": "start",
                    "project_name": plan["project_name"],
                    "total": len(file_list),
                    "stack": plan.get("stack") or "",
                }
            )

            files: dict[str, str] = {}
            for event, partial in generate_files_iter(plan):
                files = partial
                yield _sse(event)

            files = apply_bakeins(plan, files)
            validate_files(files)

            done: dict = {
                "event": "done",
                "project_name": plan["project_name"],
                "files": files,
                "stack": plan.get("stack") or "",
            }
            if plan.get("template_id"):
                done["template_id"] = plan["template_id"]
            yield _sse(done)
        except ValueError as exc:
            yield _sse({"event": "error", "detail": str(exc)})
        except Exception as exc:
            yield _sse({"event": "error", "detail": f"Generation failed: {exc}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
