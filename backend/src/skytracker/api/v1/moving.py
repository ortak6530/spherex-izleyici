"""Moving objects (solar-system bodies): SPHEREx frames from IRSA MOST and object-centred cutouts."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from ... import jobs
from ...events import log_action
from ...providers import most, ssois
from ...providers import spherex as S
from ...security import TokenBucket
from .sky import CUTOUT_SIZES, build_cutout

router = APIRouter(prefix="/moving", tags=["moving"])
_limiter = TokenBucket(rate_per_min=10, burst=4)
# Playback loads many small cutouts one after another, so frames get their own, looser bucket.
_frame_limiter = TokenBucket(rate_per_min=120, burst=40)
MAX_RANGE_DAYS = 800


def _date(v: str | None, default: dt.date) -> dt.date:
    if not v:
        return default
    try:
        return dt.date.fromisoformat(v)
    except ValueError as e:
        raise HTTPException(400, {"code": "INVALID_DATE"}) from e


@router.get("/{designation:path}/frames")
async def frames(
    request: Request,
    designation: str = Path(max_length=40),
    start: str | None = Query(default=None, max_length=10),
    end: str | None = Query(default=None, max_length=10),
) -> dict:
    """Start a job: all SPHEREx frames (active releases) containing the object, grouped into visits."""
    if not _limiter.allow(request.state.session_id):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    des = " ".join(designation.split())
    if not most.DESIGNATION_RE.match(des):
        raise HTTPException(400, {"code": "INVALID_NAME"})
    d0 = _date(start, dt.date.fromisoformat(most.MISSION_START))
    d1 = _date(end, dt.datetime.now(dt.UTC).date())
    if d1 <= d0 or (d1 - d0).days > MAX_RANGE_DAYS:
        raise HTTPException(400, {"code": "INVALID_DATE"})
    log_action(
        request, "moving_frames", object_key=des, payload={"start": d0.isoformat(), "end": d1.isoformat()}
    )

    async def run(progress):
        await progress("most_query", {"designation": des})
        try:
            out = await most.moving_frames(des, d0.isoformat(), d1.isoformat())
        except most.MostNameError as e:
            raise jobs.JobError("MOVING_NOT_FOUND", designation=des) from e
        await progress("most_done", {"count": len(out["frames"])})
        return out

    return {"job_id": jobs.start("moving_frames", run)}


@router.get("/{designation:path}/ssois")
async def other_telescopes(
    request: Request,
    designation: str = Path(max_length=40),
    kind: str | None = Query(default=None, max_length=4, pattern="^[a-z]{1,4}$"),
) -> dict:
    """Start a job: archive images of other telescopes that could contain the body (CADC SSOIS)."""
    if not _limiter.allow(request.state.session_id):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    des = " ".join(designation.split())
    if not most.DESIGNATION_RE.match(des):
        raise HTTPException(400, {"code": "INVALID_NAME"})
    log_action(request, "ssois", object_key=des)

    async def run(progress):
        await progress("ssois_query", {"designation": des})
        return await ssois.search(des, kind)

    return {"job_id": jobs.start("ssois", run)}


class FrameCutoutRequest(BaseModel):
    image_id: str = Field(max_length=80, pattern=r"^[a-z0-9]+:[0-9A-Za-z_]+:D[1-6]$")
    ra: float = Field(ge=0, lt=360)
    dec: float = Field(ge=-90, le=90)
    size_deg: float = 0.1
    zodi: str = Field(default="sub", pattern="^(sub|raw)$")


@router.post("/cutout")
async def frame_cutout(req: FrameCutoutRequest, request: Request) -> dict:
    """One frame, centred on the object's predicted position in that frame (same payload as /sky/cutout)."""
    if not _frame_limiter.allow(request.state.session_id):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    if req.size_deg not in CUTOUT_SIZES:
        raise HTTPException(400, {"code": "INVALID_SIZE", "allowed": CUTOUT_SIZES})

    async def run(progress):
        # The frame contains the predicted position, so a coverage query there re-indexes it if needed
        img = await S.find_image(req.image_id, req.ra, req.dec, progress)
        if img is None:
            raise jobs.JobError("UNKNOWN_IMAGE")
        await progress("cutout_request", {"image_id": img.image_id})
        return await build_cutout(img, req.ra, req.dec, req.size_deg, req.zodi)

    return {"job_id": jobs.start("moving_cutout", run)}
