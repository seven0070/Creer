from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.planner import plan_project
from app.generator import generate_files
from app.validator import validate_plan, validate_files

app = FastAPI(title="Creer", version="0.1.0")


class ProjectRequest(BaseModel):
    idea: str = Field(..., min_length=3, max_length=4000)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/generate")
def generate_project(request: ProjectRequest):
    try:
        plan = plan_project(request.idea)
        validate_plan(plan)
        files = generate_files(plan)
        validate_files(files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

    return {
        "project_name": plan["project_name"],
        "stack": plan.get("stack"),
        "files": files,
    }
