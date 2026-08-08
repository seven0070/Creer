from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from config import HOST, PORT

app = FastAPI(
    title="Creer Backend",
    description="AI-powered repo scaffolding backend - v0.1",
    version="0.1.0",
)

# CORS for VS Code extension and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectRequest(BaseModel):
    idea: str = Field(..., min_length=5, max_length=2000, description="Describe the project you want to create")


class GenerateResponse(BaseModel):
    project_name: str
    files: dict


@app.get("/")
def root():
    return {"name": "creer backend", "version": "0.1.0", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/generate", response_model=GenerateResponse)
def generate_project(request: ProjectRequest):
    # Lazy imports so health works without OpenAI key
    try:
        from app.planner import plan_project
        from app.generator import generate_files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backend import error: {e}")

    try:
        plan = plan_project(request.idea)
    except ValueError as e:
        # missing key or validation
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Planner failed: {e}")

    try:
        files = generate_files(plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Generator failed: {e}")

    return {
        "project_name": plan["project_name"],
        "files": files,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
