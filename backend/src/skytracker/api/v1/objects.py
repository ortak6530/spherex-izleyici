"""Object information panel: SIMBAD (+ Sesame fallback) and a Wikipedia summary, each with its source.

Both endpoints answer at once from the cache; otherwise they return {"job_id"} and report their steps
over WebSocket (HTTP polling of /jobs/<id> always works too), because SIMBAD and Wikipedia can take
10-20 s when a mirror is slow.
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Query, Request

from ... import cache, jobs
from ...events import log_action
from ...http import UpstreamError
from ...providers import resolvers, simbad, wiki

router = APIRouter(prefix="/objects", tags=["objects"])
DAY = 86400


def distance_from_parallax(plx_mas: float | None, err_mas: float | None) -> dict | None:
    """Only for significant parallaxes (> 5 sigma); otherwise the distance is reported as unknown."""
    if not plx_mas or plx_mas <= 0 or (err_mas and plx_mas / err_mas < 5):
        return None
    pc = 1000.0 / plx_mas
    return {"pc": round(pc, 3), "ly": round(pc * 3.26156, 3), "method": "1/paralaks", "source": "SIMBAD"}


async def build_info(key: str, progress) -> dict:
    await progress("info_query", {"sources": "SIMBAD, Vikipedi"})
    sim, wk = await asyncio.gather(simbad.object_basic(key), wiki.summary(key), return_exceptions=True)
    sources: dict[str, str] = {}
    unavailable = []
    if isinstance(sim, (UpstreamError, BaseException)):
        unavailable.append("SIMBAD")
        await progress("info_fallback", {"source": "Sesame"})
        # Fallback: Sesame carries type, spectral type, parallax, proper motion, velocity
        try:
            sim = await resolvers.sesame(key)
            sources["basic"] = "CDS Sesame (SIMBAD kesintisinde yedek)"
        except Exception:  # noqa: BLE001
            sim = None
    else:
        sources["basic"] = "SIMBAD (CDS)"
    if isinstance(wk, BaseException):
        unavailable.append("Wikipedia")
        wk = None

    result = {
        "main_id": key,
        "simbad": sim,
        "distance": distance_from_parallax((sim or {}).get("plx_mas"), (sim or {}).get("plx_err_mas")),
        "wikipedia": wk,
        "sources": sources,
        "unavailable": unavailable,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "from_cache": False,
    }
    if sim:  # do not cache failures
        cache.put_json("_external/objinfo", key, result)
    return result


@router.get("/info")
async def info(request: Request, main_id: str = Query(min_length=1, max_length=100)) -> dict:
    key = main_id.strip()
    cached = cache.get_json("_external/objinfo", key, DAY)
    if cached is not None:
        cached["from_cache"] = True
        return cached
    log_action(request, "object_info", object_key=key)
    return {"job_id": jobs.start("object_info", lambda progress: build_info(key, progress))}


async def build_similar(main_id: str, otype: str, progress) -> dict:
    await progress("similar_query", {"otype": otype})
    try:
        items = await simbad.same_type(otype, main_id)
    except UpstreamError:
        return {"items": [], "unavailable": ["SIMBAD"]}
    out = {"items": items, "unavailable": []}
    cache.put_json("_external/similar", f"{otype}|{main_id}", out)
    return out


@router.get("/similar")
async def similar(main_id: str = Query(max_length=100), otype: str = Query(max_length=16)) -> dict:
    """Same-type objects for the object-vs-object comparison (most studied first)."""
    if (hit := cache.get_json("_external/similar", f"{otype}|{main_id}", DAY)) is not None:
        return hit
    return {"job_id": jobs.start("similar", lambda progress: build_similar(main_id, otype, progress))}
