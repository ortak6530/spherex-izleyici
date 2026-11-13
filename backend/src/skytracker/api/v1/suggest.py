"""Search-box autocomplete: local Turkish names, Sesame (exact), JPL SBDB and SIMBAD identifier prefixes.

Every upstream runs in parallel under a short deadline; a slow or failing source is skipped (the
response says which) and the local list always answers, so typing never breaks the site.
"""

from __future__ import annotations

import asyncio
import logging
import re

from fastapi import APIRouter, HTTPException, Query, Request

from ... import cache
from ...domain.coords import CoordinateError, parse_coordinates
from ...http import UpstreamError
from ...providers import names, resolvers, simbad
from ...security import TokenBucket

log = logging.getLogger("skytracker.suggest")
router = APIRouter(tags=["search"])
_limiter = TokenBucket(rate_per_min=120, burst=40)
LIMIT = 8
DEADLINE_S = 4.0
SIMBAD_TTL_S = 24 * 3600
_NAME_OK = re.compile(r"^[\w\s+\-.*'’/()\[\]:,°″′\"]{1,100}$", re.UNICODE)


async def _guarded(name: str, coro, down: list[str]):
    try:
        return await asyncio.wait_for(coro, DEADLINE_S)
    except (TimeoutError, UpstreamError) as e:
        log.info("suggest source %s skipped: %s", name, e)
        down.append(name)
    except Exception:  # noqa: BLE001 - one bad source must not break the box
        log.exception("suggest source %s failed", name)
        down.append(name)
    return None


async def _simbad(text: str) -> list[dict]:
    key = names.normalize(text)
    if (hit := cache.get_json("_external/suggest_simbad", key, SIMBAD_TTL_S)) is not None:
        return hit["items"]
    items = await simbad.suggest(text, limit=LIMIT, timeout=DEADLINE_S)
    cache.put_json("_external/suggest_simbad", key, {"items": items})
    return items


def jpl_query(name: str) -> str:
    """What /resolve should get for an SBDB list entry: '2688 Halley (1982 HG1)' -> '2688',
    '1P/Halley' -> '1P', 'C/2017 D3 (ATLAS)' -> 'C/2017 D3' (SBDB rejects the long forms)."""
    if m := re.match(r"^(\d+)\s", name):
        return m.group(1)
    if m := re.match(r"^(\d+[PDI])/", name):
        return m.group(1)
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()


def _key(s: dict) -> str:
    """Same object from different sources -> same key ("NAME Barnard's star" == local "Barnard's Star")."""
    ident = re.sub(r"^NAME\s+", "", s.get("main_id") or s.get("query") or s["label"])
    return names.normalize(ident).replace(" ", "")


@router.get("/suggest")
async def suggest(
    request: Request,
    q: str = Query(min_length=1, max_length=100),
    local: bool = Query(default=False, description="only the local list (instant); the UI asks this first"),
) -> dict:
    if not _limiter.allow(request.state.session_id, cost=0.25 if local else 1.0):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    text = " ".join(q.split())
    if len(text) < 2:
        return {"items": [], "unavailable": []}

    try:
        c = parse_coordinates(text)
    except CoordinateError:
        c = None
    if c:
        item = {"kind": "coordinate", "label": text, "query": text, "ra": c.ra, "dec": c.dec}
        return {"items": [{**item, "source": "input"}], "unavailable": []}
    if not _NAME_OK.match(text):
        return {"items": [], "unavailable": []}

    local_hits = names.search_local(text, LIMIT)
    if local:
        return {"items": [{"kind": "name", **s} for s in local_hits], "unavailable": [], "partial": True}
    down: list[str] = []
    ses, sb, jpl = await asyncio.gather(
        _guarded("sesame", resolvers.sesame(text, simbad_only=True, timeout=DEADLINE_S), down),
        _guarded("simbad", _simbad(text), down),
        _guarded("jpl", resolvers.jpl_sbdb(text), down) if len(text) >= 3 else asyncio.sleep(0),
    )

    typed = names.normalize(text).replace(" ", "")
    remote: list[dict] = []
    # Sesame and a single SBDB object resolve the typed text itself, so they are exact matches
    if ses and ses.get("main_id"):
        mid = ses["main_id"].removeprefix("NAME ")
        remote.append({"label": mid, "query": text, "main_id": ses["main_id"], "detail": ses.get("otype"),
                       "source": "Sesame", "exact": True})  # fmt: skip
    if jpl and jpl.get("fullname"):
        remote.append({"label": jpl["fullname"], "query": jpl.get("designation") or text,
                       "detail": jpl.get("orbit_class"), "source": "JPL", "solar_system": True,
                       "exact": True})  # fmt: skip
    elif jpl and jpl.get("ambiguous"):
        for n in jpl["ambiguous"][:4]:
            remote.append({"label": n, "query": jpl_query(n), "source": "JPL", "solar_system": True,
                           "exact": _key({"label": jpl_query(n)}) == typed})  # fmt: skip
    for s in sb or []:
        remote.append({"label": s["label"], "query": s["main_id"], "main_id": s["main_id"],
                       "detail": s.get("otype"), "source": "SIMBAD",
                       "exact": typed in (_key({"label": s["label"]}), _key(s))})  # fmt: skip

    merged, seen = [], set()
    for s in local_hits + remote:
        k = _key(s)
        if k in seen:
            # the same object found again as an exact match keeps the first entry but promotes it
            if s.get("exact"):
                next(m for m in merged if _key(m) == k)["exact"] = True
            continue
        seen.add(k)
        merged.append({"kind": "name", **s})
    # Exact matches first ("m3" -> M 3 above M 31 / M 33), otherwise the source order is kept
    merged.sort(key=lambda s: not s.get("exact"))
    return {"items": merged[:LIMIT], "unavailable": sorted(set(down))}
