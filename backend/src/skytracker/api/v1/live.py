"""Live position (DECISIONS §4d-9): a job that publishes the object's current position every 10 s over
WebSocket ("position" progress steps on job:<id>; HTTP polling of the job is the fallback), optionally
with altitude / direction / rise-set for a city from config/cities_tr.json or a typed lat/lon.

One live job per browser: starting a new one stops the previous one. A job runs at most LIVE_MAX_S;
the page simply starts the next one. The query is resolved again on the server (cached).
"""

from __future__ import annotations

import asyncio
import json
import secrets
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ... import jobs
from ...domain.coords import CoordinateError
from ...events import log_action
from ...http import UpstreamError
from ...security import TokenBucket
from ...services import live as L
from ...settings import get_settings
from .resolve import resolve_target

router = APIRouter(prefix="/live", tags=["live"])
_limiter = TokenBucket(rate_per_min=6, burst=4)
INTERVAL_S = 10
LIVE_MAX_S = 600
_current: dict[str, str] = {}  # session -> token of its newest live job


@lru_cache
def cities() -> dict:
    return json.loads((get_settings().config_dir / "cities_tr.json").read_text("utf-8"))


@router.get("/cities")
def list_cities() -> dict:
    c = cities()
    return {"cities": c["cities"], "source": c["source"], "retrieved": c["retrieved"]}


class LiveRequest(BaseModel):
    q: str = Field(min_length=1, max_length=100)
    city: str | None = Field(default=None, max_length=40)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


def _site(req: LiveRequest) -> dict | None:
    if req.city:
        c = next((c for c in cities()["cities"] if c["name"] == req.city), None)
        if c is None:
            raise HTTPException(400, {"code": "UNKNOWN_CITY"})
        return {"name": c["name"], "lat": c["lat"], "lon": c["lon"], "source": f"Wikidata {c['wikidata']}"}
    if req.lat is not None and req.lon is not None:
        return {"name": None, "lat": req.lat, "lon": req.lon, "source": "girdi"}
    return None


@router.post("/start")
async def start(req: LiveRequest, request: Request) -> dict:
    sid = request.state.session_id
    if not _limiter.allow(sid):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    site = _site(req)
    token = secrets.token_hex(8)
    _current[sid] = token  # any older live job of this browser stops at its next tick
    log_action(request, "live_position", payload={"city": bool(site)})

    async def run(progress):
        try:
            target = await resolve_target(req.q)
        except CoordinateError:
            target = None
        if target is None:
            raise jobs.JobError("NOT_FOUND")
        last = None
        loop = asyncio.get_running_loop()
        t_end = loop.time() + LIVE_MAX_S
        while _current.get(sid) == token and loop.time() < t_end:
            try:
                last = await L.snapshot(target, site)
            except UpstreamError as e:
                if last is None:
                    raise
                last = {**last, "stale": e.code}  # keep showing the previous position, marked
            await progress("position", {"position": last, "name": target.get("name"), "kind": target["kind"]})
            await asyncio.sleep(INTERVAL_S)
        return {"position": last, "name": target.get("name"), "kind": target["kind"], "ended": True}

    return {"job_id": jobs.start("live_position", run)}
