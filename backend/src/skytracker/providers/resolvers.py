"""Name resolution: CDS Sesame (SIMBAD -> NED -> VizieR), JPL SBDB for solar-system bodies,
Wikidata as a suggestion source. All results are cached on disk."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
import xml.etree.ElementTree as ET  # noqa: S405 - responses come only from allow-listed CDS hosts

from .. import cache
from ..config_loader import upstreams
from ..http import UpstreamError, http
from ..settings import get_settings
from . import simbad

log = logging.getLogger("skytracker.resolve")
DAY = 86400


def _ftext(el: ET.Element, tag: str) -> str | None:
    t = el.findtext(tag)
    return t.strip() if t else None


def _fnum(el: ET.Element, path: str) -> float | None:
    t = el.findtext(path)
    try:
        return float(t) if t else None
    except ValueError:
        return None


async def sesame(name: str, simbad_only: bool = False, timeout: float = 12) -> dict | None:
    """Resolve a name (SIMBAD -> NED -> VizieR). simbad_only=True is the fast path for autocomplete:
    unknown names fall through NED/VizieR slowly and NED adds noise (e.g. 'barnard' -> a galaxy)."""
    key = name.strip().lower()
    ns = "_external/sesame_s" if simbad_only else "_external/sesame"
    if (hit := cache.get_json(ns, key, 7 * DAY)) is not None:
        return hit.get("result")
    base = getattr(
        upstreams().groups["cds"], "sesame_url", "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV"
    )
    if simbad_only:
        base = base.rsplit("/", 1)[0] + "/S"
    url = base + "?" + urllib.parse.quote(name.strip())
    r = await http.get(url, timeout=timeout, retries=0 if simbad_only else 1)
    if r.status_code != 200:
        raise UpstreamError("UPSTREAM_UNAVAILABLE", "sesame", str(r.status_code))
    root = ET.fromstring(r.content)  # noqa: S314
    result = None
    for res in root.iter("Resolver"):
        ra, dec = _fnum(res, "jradeg"), _fnum(res, "jdedeg")
        if ra is None or dec is None:
            continue
        result = {
            "main_id": _ftext(res, "oname"),
            "ra": ra,
            "dec": dec,
            "otype": _ftext(res, "otype"),
            "sp_type": _ftext(res, "spType"),
            "morph_type": _ftext(res, "MType"),
            "plx_mas": _fnum(res, "plx/v"),
            "pmra_mas_yr": _fnum(res, "pm/pmRA"),
            "pmdec_mas_yr": _fnum(res, "pm/pmDE"),
            "radvel_km_s": _fnum(res, "Vel/v"),
            "redshift": _fnum(res, "z/v"),
            "resolver": res.get("name"),
        }
        break
    cache.put_json(ns, key, {"result": result})
    return result


async def jpl_sbdb(name: str) -> dict | None:
    """Solar-system body lookup. Returns None if not a known small body."""
    key = name.strip().lower()
    if (hit := cache.get_json("_external/sbdb", key, 7 * DAY)) is not None:
        return hit.get("result")
    r = await http.get(
        "https://ssd-api.jpl.nasa.gov/sbdb.api", params={"sstr": name.strip()}, timeout=12, retries=1
    )
    result = None
    if r.status_code == 200:
        d = r.json()
        obj = d.get("object")
        if obj:
            result = {
                "fullname": obj.get("fullname"),
                "designation": obj.get("des"),
                "kind": obj.get("kind"),  # an/au = asteroid, cn/cu = comet
                "orbit_class": (obj.get("orbit_class") or {}).get("name"),
            }
        elif d.get("list"):
            result = {"ambiguous": [x.get("name") for x in d["list"][:8]]}
    elif r.status_code not in (300, 400, 404):
        raise UpstreamError("UPSTREAM_UNAVAILABLE", "jpl", str(r.status_code))
    cache.put_json("_external/sbdb", key, {"result": result})
    return result


async def wikidata_suggest(text: str, lang: str = "tr", limit: int = 5) -> list[dict]:
    r = await http.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "search": text,
            "language": lang,
            "uselang": lang,
            "format": "json",
            "limit": limit,
            "type": "item",
        },
        headers={"User-Agent": get_settings().wikimedia_user_agent},
        timeout=8,
        retries=0,
    )
    if r.status_code != 200:
        return []
    hits = [h for h in r.json().get("search", []) if _astro_description(h.get("description"))]
    if not hits:
        return []
    # The SIMBAD identifier (P3083) is what Sesame can resolve; labels like "WISE 0855–0714" are not
    e = await http.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbgetentities",
            "ids": "|".join(h["id"] for h in hits),
            "props": "claims",
            "format": "json",
        },
        headers={"User-Agent": get_settings().wikimedia_user_agent},
        timeout=8,
        retries=0,
    )
    ents = e.json().get("entities", {}) if e.status_code == 200 else {}
    out = []
    for h in hits:
        claims = ents.get(h["id"], {}).get("claims", {}).get("P3083", [])
        simbad_id = next(
            (
                c["mainsnak"].get("datavalue", {}).get("value")
                for c in claims
                if c.get("mainsnak", {}).get("datavalue")
            ),
            None,
        )
        if simbad_id:
            out.append(
                {
                    "label": h.get("label"),
                    "description": h.get("description"),
                    "qid": h["id"],
                    "main_id": simbad_id,
                    "source": "Wikidata",
                }
            )
    return out


async def suggestions(text: str) -> list[dict]:
    """Candidate names for an unresolved query; each is re-resolved through Sesame when picked."""
    res = await asyncio.gather(simbad.suggest(text), wikidata_suggest(text, "en"), return_exceptions=True)
    out: list[dict] = []
    for part in res:
        if isinstance(part, BaseException):
            log.info("suggestion source failed: %s", part)
            continue
        out.extend(part)
    # Wikidata hits without astronomy context are noise; keep the ones that look like objects
    seen, final = set(), []
    for s in out:
        label = (s.get("label") or "").strip()
        if not label or label.lower() in seen:
            continue
        if s["source"] == "Wikidata" and not _astro_description(s.get("description")):
            continue
        seen.add(label.lower())
        final.append(s)
    return final[:8]


_ASTRO_WORDS = (
    "star",
    "dwarf",
    "galaxy",
    "nebula",
    "cluster",
    "comet",
    "asteroid",
    "planet",
    "quasar",
    "supernova",
    "constellation",
    "yıldız",
    "gökada",
    "bulutsu",
    "kuyruklu",
)


def _astro_description(desc: str | None) -> bool:
    d = (desc or "").lower()
    return any(w in d for w in _ASTRO_WORDS)
