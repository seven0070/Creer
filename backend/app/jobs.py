"""In-memory generation job registry for stream cancellation."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

# Jobs older than this are eligible for cleanup.
_TTL_SECONDS = 30 * 60


@dataclass
class _Job:
    cancelled: bool = False
    created_at: float = field(default_factory=time.time)


_lock = threading.Lock()
_jobs: dict[str, _Job] = {}


def _purge_expired(now: float | None = None) -> None:
    now = now if now is not None else time.time()
    expired = [jid for jid, job in _jobs.items() if now - job.created_at > _TTL_SECONDS]
    for jid in expired:
        del _jobs[jid]


def create_job(job_id: str | None = None) -> str:
    """Register a new job (or ensure an existing id) and return its id.

    If the id was already cancelled (cancel-before-start), keep it cancelled.
    """
    jid = (job_id or "").strip() or uuid.uuid4().hex
    with _lock:
        _purge_expired()
        existing = _jobs.get(jid)
        if existing is not None:
            # Refresh TTL but preserve cancelled flag.
            existing.created_at = time.time()
            return jid
        _jobs[jid] = _Job()
    return jid


def is_cancelled(job_id: str | None) -> bool:
    if not job_id:
        return False
    with _lock:
        job = _jobs.get(job_id)
        return bool(job and job.cancelled)


def cancel_job(job_id: str) -> bool:
    """Mark a job cancelled. Returns True if the job existed (or was created as cancelled)."""
    jid = (job_id or "").strip()
    if not jid:
        return False
    with _lock:
        _purge_expired()
        job = _jobs.get(jid)
        if job is None:
            # Allow cancel-before-start races: register already-cancelled.
            _jobs[jid] = _Job(cancelled=True)
            return True
        job.cancelled = True
        return True


def finish_job(job_id: str | None) -> None:
    if not job_id:
        return
    with _lock:
        _jobs.pop(job_id, None)
