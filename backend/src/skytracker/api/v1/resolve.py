"""Search bar: coordinates or a name -> one target, or a list of suggestions."""

from __future__ import annotations

import asyncio
import math
import re

from fastapi import APIRouter, HTTPException, Query, Request

from ...domain.astrometry import SEARCH_EPOCH, jyear_to_mjd, propagate
from ...domain.coords import CoordinateError, parse_coordinates
from ...events import log_action
from ...http import UpstreamError
from ...providers import names, resolvers
from ...security import TokenBucket

router = APIRouter(tags=["search"])
_limiter = TokenBucket(rate_per_min=40, burst=15)
_NAME_OK = re.compile(r"^[\w\s+\-.*'’/()\[\]:,°″′\"]{1,100}$", re.UNICODE)


def object_key(main_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", main_id.lower()).strip("-")[:80]


def target_from_sesame(r: dict, query: str) -> dict:
    name = (r.get("main_id") or query).removeprefix("NAME ")
    pmra, pmdec = r.get("pmra_mas_yr"), r.get("pmdec_mas_yr")
    # SPHEREx searches use the position at the mission epoch, not J2000 (matters for fast stars)
    ra, dec = propagate(r["ra"], r["dec"], pmra, pmdec, jyear_to_mjd(SEARCH_EPOCH))
    moved = math.hypot((ra - r["ra"]) * math.cos(math.radians(r["dec"])), dec - r["dec"]) * 3600
    return {
        "kind": "object",
        "key": object_key(r.get("main_id") or query),
        "name": name,
        "main_id": r.get("main_id"),
        "query": query,
        "ra": ra,
        "dec": dec,
        "ra_j2000": r["ra"],
        "dec_j2000": r["dec"],
        "pmra_mas_yr": pmra,
        "pmdec_mas_yr": pmdec,
        "epoch": SEARCH_EPOCH,
        "moved_since_j2000_arcsec": moved,
        "otype": r.get("otype"),
        "source": "CDS Sesame (" + (r.get("resolver") or "SIMBAD") + ")",
    }


@router.get("/resolve")
async def resolve(request: Request, q: str = Query(min_length=1, max_length=100)) -> dict:
    if not _limiter.allow(request.state.session_id):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    text = q.strip()
    try:
        c = parse_coordinates(text)
    except CoordinateError as e:
        raise HTTPException(400, {"code": e.code}) from e
    if c:
        target = {
            "kind": "coordinate",
            "key": f"coord-{c.ra:.4f}{c.dec:+.4f}",
            "name": f"{c.ra:.5f} {c.dec:+.5f}",
            "main_id": None,
            "query": text,
            "ra": c.ra,
            "dec": c.dec,
            "otype": None,
            "input_format": c.input_format,
            "galactic": c.galactic,
            "source": "girdi",
        }
        log_action(request, "search", object_key=target["key"], payload={"kind": "coordinate"})
        return {"kind": "coordinate", "target": target}

    if not _NAME_OK.match(text):
        raise HTTPException(400, {"code": "INVALID_NAME"})

    # Turkish names from the local list ("Kutup Yıldızı") are looked up by their catalogue name
    lookup = names.exact_query(text) or text
    ses, sbdb = await asyncio.gather(
        resolvers.sesame(lookup), resolvers.jpl_sbdb(lookup), return_exceptions=True
    )
    upstream_down = [n for n, v in (("sesame", ses), ("jpl", sbdb)) if isinstance(v, UpstreamError)]
    ses = None if isinstance(ses, BaseException) else ses
    sbdb = None if isinstance(sbdb, BaseException) else sbdb

    solar = None
    if sbdb and sbdb.get("fullname"):
        solar = {
            "kind": "solar_system",
            "key": object_key(sbdb["fullname"]),
            "name": sbdb["fullname"],
            "designation": sbdb.get("designation"),
            "body_kind": sbdb.get("kind"),
            "orbit_class": sbdb.get("orbit_class"),
            "query": text,
            "source": "JPL SBDB",
        }

    if ses:
        target = target_from_sesame(ses, text)
        log_action(request, "search", object_key=target["key"], payload={"kind": "object"})
        # A name can be both (rare); offer the solar-system body as an alternative
        return {"kind": "object", "target": target, "alternatives": [solar] if solar else []}
    if solar:
        log_action(request, "search", object_key=solar["key"], payload={"kind": "solar_system"})
        return {"kind": "solar_system", "target": solar}

    try:
        cands = await resolvers.suggestions(text)
    except UpstreamError:
        cands = []
    if sbdb and sbdb.get("ambiguous"):
        cands += [
            {"label": n, "main_id": None, "source": "JPL SBDB", "solar_system": True}
            for n in sbdb["ambiguous"]
        ]
    log_action(request, "search", payload={"kind": "not_found", "suggestions": len(cands)})
    return {
        "kind": "ambiguous" if cands else "not_found",
        "candidates": cands,
        "upstream_unavailable": upstream_down,
    }
