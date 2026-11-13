"""In-process background jobs with progress over WebSocket (topic "job:<id>") and HTTP polling.

A slow request returns {"job_id"} at once; the client subscribes on /ws for live steps and can always
fall back to GET /api/v1/jobs/<id>. Single Render instance -> an in-memory registry is enough.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Any

from .http import UpstreamError
from .realtime import manager

log = logging.getLogger("skytracker.jobs")
JOB_TTL_S = 1800
MAX_JOBS = 500


class JobError(Exception):
    """Expected, user-facing failure with a stable code (e.g. CHANNEL_REJECT)."""

    def __init__(self, code: str, **params: Any):
        super().__init__(code)
        self.code = code
        self.params = params


_jobs: dict[str, dict[str, Any]] = {}
_tasks: set[asyncio.Task] = set()


def _prune() -> None:
    now = time.time()
    for jid in [j for j, v in _jobs.items() if now - v["created"] > JOB_TTL_S]:
        _jobs.pop(jid, None)
    while len(_jobs) > MAX_JOBS:
        _jobs.pop(next(iter(_jobs)))


def get(job_id: str) -> dict | None:
    j = _jobs.get(job_id)
    if not j:
        return None
    return {k: v for k, v in j.items() if k != "created"}


JobFn = Callable[[Callable[[str, dict], Awaitable[None]]], Awaitable[Any]]


def start(kind: str, fn: JobFn) -> str:
    _prune()
    job_id = secrets.token_urlsafe(12)
    _jobs[job_id] = {
        "id": job_id,
        "kind": kind,
        "status": "running",
        "steps": [],
        "result": None,
        "error": None,
        "created": time.time(),
    }

    async def progress(step: str, data: dict) -> None:
        # elapsed_s lets the UI show how long a slow upstream (IRSA: 30-60 s) has been working
        entry = {"step": step, **data, "elapsed_s": round(time.time() - _jobs[job_id]["created"], 1)}
        _jobs[job_id]["steps"].append(entry)
        del _jobs[job_id]["steps"][:-30]  # keep the tail only
        await manager.publish(f"job:{job_id}", {"type": "progress", "job_id": job_id, **entry})

    async def runner() -> None:
        job = _jobs[job_id]
        try:
            job["result"] = await fn(progress)
            job["status"] = "done"
        except UpstreamError as e:
            job["status"], job["error"] = "error", {"code": e.code, "upstream": e.upstream}
        except JobError as e:
            job["status"], job["error"] = "error", {"code": e.code, **e.params}
        except Exception:  # noqa: BLE001 - surfaced to the client as a generic error
            log.exception("job %s (%s) failed", job_id, kind)
            job["status"], job["error"] = "error", {"code": "INTERNAL_ERROR"}
        await manager.publish(f"job:{job_id}", {"type": "job_" + job["status"], "job_id": job_id})

    task = asyncio.create_task(runner())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return job_id
