"""Comparisons. Results (without pixel arrays) are stored so the assistant and Excel export can read them."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ... import jobs
from ...db import session_scope
from ...db.models import Comparison
from ...events import log_action
from ...http import UpstreamError
from ...providers import simbad
from ...security import TokenBucket
from ...services.object_compare import compare_objects
from ...services.time_compare import compare_time
from .sky import CUTOUT_SIZES

router = APIRouter(prefix="/compare", tags=["compare"])
_limiter = TokenBucket(rate_per_min=10, burst=4)
IMAGE_ID = r"^[a-z0-9]+:[0-9A-Za-z_]+:D[1-6]$"


def strip_arrays(result: dict) -> dict:
    """Drop pixel arrays (any '*_b64' key, at any depth) before storing a comparison."""
    return {
        k: strip_arrays(v) if isinstance(v, dict) else v for k, v in result.items() if not k.endswith("_b64")
    }


def save_comparison(request: Request, kind: str, object_key: str | None, params: dict, result: dict) -> None:
    with session_scope() as db:
        db.add(
            Comparison(
                id=result["id"],
                session_id=request.state.session_id,
                kind=kind,
                object_key=object_key,
                params=params,
                result=strip_arrays(result),
            )
        )


class TimeCompareRequest(BaseModel):
    image_a: str = Field(pattern=IMAGE_ID)
    image_b: str = Field(pattern=IMAGE_ID)
    ra: float = Field(ge=0, lt=360)
    dec: float = Field(ge=-90, le=90)
    size_deg: float = 0.1
    zodi: str = Field(default="sub", pattern="^(sub|raw)$")
    normalize: bool = True  # decision S4: on by default
    main_id: str | None = Field(default=None, max_length=100)
    object_key: str | None = Field(default=None, max_length=120)


@router.post("/time")
async def time_compare(req: TimeCompareRequest, request: Request) -> dict:
    if not _limiter.allow(request.state.session_id):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    if req.size_deg not in CUTOUT_SIZES:
        raise HTTPException(400, {"code": "INVALID_SIZE"})
    log_action(
        request,
        "compare_time",
        object_key=req.object_key,
        payload={"a": req.image_a, "b": req.image_b, "size": req.size_deg},
    )

    async def run(progress):
        pm = None
        if req.main_id:
            try:
                info = await simbad.object_basic(req.main_id)
                if info:
                    pm = {
                        "pmra_mas_yr": info.get("pmra_mas_yr"),
                        "pmdec_mas_yr": info.get("pmdec_mas_yr"),
                        "ra_j2000": info.get("ra"),
                        "dec_j2000": info.get("dec"),
                    }
            except UpstreamError:
                pm = None  # expected shift is then simply not reported
        result = await compare_time(
            req.image_a, req.image_b, req.ra, req.dec, req.size_deg, req.zodi, req.normalize, pm, progress
        )
        result["object_key"] = req.object_key
        save_comparison(request, "time", req.object_key, req.model_dump(), result)
        return result

    return {"job_id": jobs.start("compare_time", run)}


class ObjectRef(BaseModel):
    name: str = Field(max_length=120)
    main_id: str | None = Field(default=None, max_length=100)
    key: str = Field(max_length=120)
    ra: float = Field(ge=0, lt=360)
    dec: float = Field(ge=-90, le=90)


class ObjectCompareRequest(BaseModel):
    a: ObjectRef
    b: ObjectRef
    image_a: str = Field(pattern=IMAGE_ID)  # the exposure currently selected for object A
    size_deg: float = 0.1
    zodi: str = Field(default="sub", pattern="^(sub|raw)$")


@router.post("/objects")
async def object_compare(req: ObjectCompareRequest, request: Request) -> dict:
    if not _limiter.allow(request.state.session_id):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    if req.size_deg not in CUTOUT_SIZES:
        raise HTTPException(400, {"code": "INVALID_SIZE"})
    if req.a.key == req.b.key:
        raise HTTPException(400, {"code": "SAME_OBJECT"})
    log_action(request, "compare_objects", object_key=req.a.key, payload={"b": req.b.key})

    async def run(progress):
        result = await compare_objects(
            req.a.model_dump(), req.b.model_dump(), req.image_a, req.size_deg, req.zodi, progress
        )
        result["object_key"] = req.a.key
        save_comparison(request, "object", req.a.key, req.model_dump(), result)
        return result

    return {"job_id": jobs.start("compare_objects", run)}
