"""Creer FastAPI application — plan, generate, stream, cancel, GitHub helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from config import (
    CREER_ALLOW_PRIVATE_PEERS,
    CREER_FEDERATION_MAX_HOPS,
    CREER_OFFLINE,
    CREER_PUBLIC_BASE_URL,
    MODEL,
    OPENAI_BASE_URL,
)
from app.auth import registry_auth_required, require_registry_write
from app.bakeins import apply_bakeins, list_bakein_options
from app.planner import plan_project
from app.generator import generate_files, generate_files_iter
from app.validator import validate_plan, validate_files
from app.templates import list_templates, get_template
from app.packs import (
    PackConflictError,
    PackNotInstalledError,
    get_pack,
    install_pack_from_url,
    list_packs,
    uninstall_pack,
)
from app.registry import (
    featured_marketplace,
    get_registry_pack,
    list_registry,
    pack_download_bytes,
    registry_count,
)
from app.federation import (
    discover_self,
    list_federated,
    list_peer_status,
    parse_peers,
    probe_peer,
)
from app.peer_policy import assert_peer_allowed
from app.peer_trust import trust_enabled, trust_mode
from app.github import create_github_repo
from app.jobs import cancel_job, create_job, finish_job, is_cancelled
from app.quality import has_errors, run_quality_gates

VERSION = "1.2.0"

app = FastAPI(title="Creer", version=VERSION)


class PlanRequest(BaseModel):
    idea: str = Field(..., min_length=3, max_length=4000)
    template_id: str | None = None
    pack_id: str | None = None


class PlanBody(BaseModel):
    project_name: str
    stack: str | None = None
    files: list[str]
    template_id: str | None = None
    pack_id: str | None = None
    description: str | None = None


class BakeinOptions(BaseModel):
    license: Literal["mit", "apache-2.0", "none"] = "mit"
    ci: Literal["auto", "python", "node", "none"] = "auto"
    include_readme: bool = True


class GenerateRequest(BaseModel):
    idea: str = Field(..., min_length=3, max_length=4000)
    template_id: str | None = None
    pack_id: str | None = None
    plan: PlanBody | None = None
    job_id: str | None = None
    bakeins: BakeinOptions | None = None


class CancelRequest(BaseModel):
    job_id: str = Field(..., min_length=1)


class QualityRequest(BaseModel):
    plan: PlanBody | None = None
    files: dict[str, str]
    bakeins: BakeinOptions | None = None


class GitHubCreateRepoRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    private: bool = True
    description: str = ""
    token: str | None = None


class PackInstallRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2000)
    overwrite: bool = False


class PeerProbeRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2000)


def _check_pack_template_exclusive(
    pack_id: str | None, template_id: str | None
) -> None:
    if pack_id and template_id:
        raise ValueError("Provide pack_id or template_id, not both")


def _resolve_plan(request: GenerateRequest) -> dict:
    """Resolve a validated plan from GenerateRequest (shared by sync + stream)."""
    _check_pack_template_exclusive(request.pack_id, request.template_id)

    if request.plan is not None:
        plan = request.plan.model_dump()
        plan = {k: v for k, v in plan.items() if v is not None}
        plan.setdefault("stack", "")
        _check_pack_template_exclusive(plan.get("pack_id"), plan.get("template_id"))
        if request.pack_id and "pack_id" not in plan:
            plan["pack_id"] = request.pack_id
        if request.template_id and "template_id" not in plan:
            plan["template_id"] = request.template_id
        # Re-check after merging top-level ids into plan
        _check_pack_template_exclusive(plan.get("pack_id"), plan.get("template_id"))
    else:
        if request.pack_id and get_pack(request.pack_id) is None:
            raise ValueError(f"Unknown pack_id: {request.pack_id!r}")
        if request.template_id and get_template(request.template_id) is None:
            raise ValueError(f"Unknown template_id: {request.template_id!r}")
        plan = plan_project(
            request.idea,
            template_id=request.template_id,
            pack_id=request.pack_id,
        )

    validate_plan(plan)
    return plan


def _bakein_dict(bakeins: BakeinOptions | None) -> dict[str, Any] | None:
    return bakeins.model_dump() if bakeins is not None else None


def _expect_license(bakeins: BakeinOptions | None) -> bool:
    if bakeins is None:
        return True
    return bakeins.license != "none"


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
        "packs_count": len(list_packs()),
        "registry_count": registry_count(),
        "public_base_url_set": bool(CREER_PUBLIC_BASE_URL),
        "peers_configured": len(parse_peers()),
        "auth_required": registry_auth_required(),
        "federation_max_hops": CREER_FEDERATION_MAX_HOPS,
        "allow_private_peers": CREER_ALLOW_PRIVATE_PEERS,
        "peer_trust_mode": trust_mode(),
        "peer_trust_signing": trust_enabled(),
    }


@app.get("/templates")
def templates():
    return {"templates": list_templates()}


@app.get("/packs")
def packs():
    return {"packs": list_packs()}


@app.get("/registry")
def registry(
    q: str | None = Query(default=None, description="Search name/description/id/stack"),
    source: str = Query(default="all", description="bundled | installed | all"),
):
    """Self-hosted searchable pack registry (local only)."""
    return list_registry(q=q, source=source)


@app.get("/registry/federated")
def registry_federated(
    q: str | None = Query(default=None, description="Search name/description/id/stack"),
    source: str = Query(default="all", description="bundled | installed | all"),
    peers: str | None = Query(
        default=None,
        description="Comma-separated extra peer base URLs for this request only",
    ),
    discover: bool = Query(
        default=False,
        description="Multi-hop peer discovery via GET {peer}/registry/discover",
    ),
    max_hops: int | None = Query(
        default=None,
        ge=0,
        le=2,
        description="Hop budget for discover (overrides CREER_FEDERATION_MAX_HOPS for this request)",
    ),
):
    """Federated registry: local packs plus peer Creer registries."""
    extra = parse_peers(peers) if peers else None
    return list_federated(
        q=q,
        source=source,
        include_local=True,
        extra_peers=extra,
        discover=discover,
        max_hops=max_hops,
    )


@app.get("/registry/discover")
def registry_discover():
    """Gossip-lite self advertisement: version, packs, configured peers, auth flag."""
    return discover_self()


@app.get("/registry/peers")
def registry_peers():
    """Configured peer list plus live probe status for each peer."""
    return {"peers": list_peer_status(), "configured": parse_peers()}


@app.post("/registry/peers/probe")
def registry_peers_probe(
    request: PeerProbeRequest,
    _: None = Depends(require_registry_write),
):
    """Ad-hoc probe of a single peer base URL (auth required when token configured)."""
    url = (request.url or "").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail="url must use http or https with a host",
        )
    try:
        assert_peer_allowed(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return probe_peer(url)


@app.get("/registry/packs/{pack_id}")
def registry_pack_detail(pack_id: str):
    item = get_registry_pack(pack_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Unknown pack_id: {pack_id!r}")
    return item


@app.get("/registry/packs/{pack_id}/download")
def registry_pack_download(pack_id: str):
    """Download pack as portable JSON (usable as POST /packs/install url)."""
    result = pack_download_bytes(pack_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown pack_id: {pack_id!r}")
    data, filename = result
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/marketplace")
def marketplace():
    """Curated marketplace view (featured + local download URLs when available)."""
    return {"items": featured_marketplace()}


@app.post("/packs/install")
def packs_install(
    request: PackInstallRequest,
    _: None = Depends(require_registry_write),
):
    """Fetch a remote pack URL (http/https), validate, and install locally."""
    try:
        pack = install_pack_from_url(request.url, overwrite=request.overwrite)
    except PackConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Pack install failed: {exc}"
        ) from exc
    return {"installed": True, "pack": pack}


@app.get("/packs/{pack_id}")
def pack_detail(pack_id: str):
    pack = get_pack(pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail=f"Unknown pack_id: {pack_id!r}")
    return pack


@app.delete("/packs/{pack_id}")
def packs_delete(
    pack_id: str,
    _: None = Depends(require_registry_write),
):
    """Delete a pack from the writable installed dir only (not shipped examples)."""
    try:
        uninstall_pack(pack_id)
    except PackNotInstalledError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted": True, "pack_id": pack_id}


@app.get("/bakeins")
def bakeins():
    return list_bakein_options()


@app.post("/plan")
def plan_only(request: PlanRequest):
    """Return a project plan without generating file contents."""
    try:
        _check_pack_template_exclusive(request.pack_id, request.template_id)
        if request.pack_id and get_pack(request.pack_id) is None:
            raise ValueError(f"Unknown pack_id: {request.pack_id!r}")
        if request.template_id and get_template(request.template_id) is None:
            raise ValueError(f"Unknown template_id: {request.template_id!r}")
        plan = plan_project(
            request.idea,
            template_id=request.template_id,
            pack_id=request.pack_id,
        )
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
    if plan.get("pack_id"):
        result["pack_id"] = plan["pack_id"]
    if plan.get("template_id"):
        result["template_id"] = plan["template_id"]
    if plan.get("description"):
        result["description"] = plan["description"]
    return result


@app.post("/generate")
def generate_project(request: GenerateRequest):
    job_id = create_job(request.job_id)
    try:
        if is_cancelled(job_id):
            raise ValueError("Cancelled by user")
        plan = _resolve_plan(request)
        files = generate_files(plan, should_cancel=lambda: is_cancelled(job_id))
        files = apply_bakeins(plan, files, _bakein_dict(request.bakeins))
        validate_files(files)
        quality = run_quality_gates(
            plan, files, expect_license=_expect_license(request.bakeins)
        )
        if has_errors(quality):
            detail = "; ".join(
                f"{i.get('code')}: {i.get('message')}" for i in quality if i.get("severity") == "error"
            )
            raise ValueError(f"Quality gate failed: {detail}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc
    finally:
        finish_job(job_id)

    result = {
        "project_name": plan["project_name"],
        "stack": plan.get("stack"),
        "files": files,
        "quality": quality,
        "job_id": job_id,
    }
    if plan.get("pack_id"):
        result["pack_id"] = plan["pack_id"]
    if plan.get("template_id"):
        result["template_id"] = plan["template_id"]
    return result


@app.post("/generate/stream")
def generate_project_stream(request: GenerateRequest):
    """Stream generation progress as Server-Sent Events (JSON data lines)."""
    job_id = create_job(request.job_id)

    def event_stream() -> Iterator[str]:
        plan: dict | None = None
        try:
            if is_cancelled(job_id):
                yield _sse(
                    {
                        "event": "cancelled",
                        "job_id": job_id,
                        "detail": "Cancelled by user",
                    }
                )
                return

            plan = _resolve_plan(request)
            file_list = list(plan["files"])
            yield _sse(
                {
                    "event": "start",
                    "job_id": job_id,
                    "project_name": plan["project_name"],
                    "total": len(file_list),
                    "stack": plan.get("stack") or "",
                }
            )

            files: dict[str, str] = {}
            cancelled = False
            for event, partial in generate_files_iter(
                plan, should_cancel=lambda: is_cancelled(job_id)
            ):
                files = partial
                if event.get("event") == "cancelled":
                    cancelled = True
                    yield _sse(
                        {
                            "event": "cancelled",
                            "job_id": job_id,
                            "detail": event.get("detail") or "Cancelled by user",
                        }
                    )
                    break
                yield _sse(event)

            if cancelled:
                return

            files = apply_bakeins(plan, files, _bakein_dict(request.bakeins))
            validate_files(files)
            quality = run_quality_gates(
                plan, files, expect_license=_expect_license(request.bakeins)
            )
            if has_errors(quality):
                detail = "; ".join(
                    f"{i.get('code')}: {i.get('message')}"
                    for i in quality
                    if i.get("severity") == "error"
                )
                yield _sse({"event": "error", "detail": f"Quality gate failed: {detail}", "quality": quality})
                return

            done: dict = {
                "event": "done",
                "job_id": job_id,
                "project_name": plan["project_name"],
                "files": files,
                "stack": plan.get("stack") or "",
                "quality": quality,
            }
            if plan.get("pack_id"):
                done["pack_id"] = plan["pack_id"]
            if plan.get("template_id"):
                done["template_id"] = plan["template_id"]
            yield _sse(done)
        except ValueError as exc:
            yield _sse({"event": "error", "detail": str(exc)})
        except Exception as exc:
            yield _sse({"event": "error", "detail": f"Generation failed: {exc}"})
        finally:
            finish_job(job_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/generate/cancel")
def generate_cancel(request: CancelRequest):
    ok = cancel_job(request.job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid job_id")
    return {"cancelled": True, "job_id": request.job_id}


@app.post("/quality")
def quality_check(request: QualityRequest):
    plan = request.plan.model_dump() if request.plan is not None else {"files": list(request.files.keys())}
    plan.setdefault("files", list(request.files.keys()))
    quality = run_quality_gates(
        plan,
        request.files,
        expect_license=_expect_license(request.bakeins),
    )
    return {"quality": quality, "ok": not has_errors(quality)}


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
