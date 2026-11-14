"""CADC SSOIS (Solar System Object Image Search): which other telescopes' archive images could contain a
solar-system body (Gwyn, Hill & Kavelaars 2012). Links only; nothing is downloaded.

Verified live 2026-11-14 (DATA_SOURCES §10d):
- endpoint https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/cadcbin/ssos/ssosclf.pl (the API page leaves the
  base URL blank; the search form's results.js calls this path). `eunits` must be "arcseconds" or
  "arcminutes" (anything else -> HTTP 500).
- search=bynameCADC only (bynameHorizons / bynameMPC load JPL / MPC; the API page asks not to).
  bynameCADC uses MPCORB.DAT: asteroids by number or upper-case name work (433, EROS, CERES, 2024 YR4);
  **comets are not in it** ("this file does not contain planets, planetary satellites, or comets"),
  so 3I/ATLAS, 1P, 2P are reported as not covered rather than queried under another name.
- format=tsv: Image, MJD, Filter, Exptime, Object_RA, Object_Dec, Image_target, Telescope/Instrument,
  Datalink. Results are large (433 Eros: 7284 rows, 1.2 MB, 7 s); only a summary is kept.
"""

from __future__ import annotations

import datetime as dt
import html
import re
from collections import Counter

from astropy.time import Time

from .. import cache
from ..http import UpstreamError, http, raise_for_upstream

URL = "https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/cadcbin/ssos/ssosclf.pl"
START = "1990-01-01"
CACHE_S = 86400
RECENT = 50
COMET = re.compile(r"^(\d+[PDI](/.*)?|[PCDXI]/.+)$", re.I)  # 1P, 2P/Encke, C/2025 N1, 3I …
NOTE = (
    "SSOIS, cismin öngörülen konumunun görüntü alanına düştüğü arşiv karelerini listeler; cismin o karede "
    "görünür (yeterince parlak) olduğu anlamına gelmez."
)


def query_name(designation: str, kind: str | None = None) -> str | None:
    """Name for bynameCADC, or None when the body cannot be in MPCORB.DAT (comets).

    `kind` is JPL SBDB's: an/au asteroid, cn/cu comet (3I/ATLAS has des "2025 N1" but kind "cu")."""
    des = " ".join(designation.split())
    if (kind or "").startswith("c") or COMET.match(des):
        return None
    return des.upper()


def parse_tsv(text: str) -> tuple[list[dict], bool]:
    """(rows, not_found). A not-found answer comes back as an HTML message inside the TSV response."""
    lines = text.strip().splitlines()
    if not lines or not lines[0].startswith("Image\t"):
        return [], "not found" in text.lower()
    head = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        p = ln.split("\t")
        if len(p) < len(head):
            p += [""] * (len(head) - len(p))
        rows.append(dict(zip(head, p, strict=False)))
    return rows, False


def summarise(rows: list[dict]) -> dict:
    def mjd(r: dict) -> float | None:
        try:
            return float(r.get("MJD") or "")
        except ValueError:
            return None

    dated = [(mjd(r), r) for r in rows if mjd(r) is not None]
    dated.sort(key=lambda x: x[0], reverse=True)
    inst = Counter(r.get("Telescope/Instrument") or "?" for r in rows)

    def iso(m: float) -> str:
        return Time(m, format="mjd").isot[:10]

    recent = []
    for m, r in dated[:RECENT]:
        link = html.unescape((r.get("Datalink") or "").strip())
        recent.append(
            {
                "date": iso(m),
                "mjd": m,
                "instrument": r.get("Telescope/Instrument"),
                "filter": r.get("Filter") or None,
                "exptime_s": r.get("Exptime") or None,
                "image": r.get("Image"),
                "link": link if link.startswith("https://") else None,  # http links are not shown as links
            }
        )
    return {
        "total": len(rows),
        "first": iso(dated[-1][0]) if dated else None,
        "last": iso(dated[0][0]) if dated else None,
        "instruments": inst.most_common(12),
        "n_instruments": len(inst),
        "recent": recent,
    }


async def search(designation: str, kind: str | None = None) -> dict:
    name = query_name(designation, kind)
    base = {"designation": designation, "source": "CADC SSOIS (bynameCADC)", "note": NOTE}
    if name is None:
        return {**base, "status": "not_covered", "reason": "comet"}
    today = dt.datetime.now(dt.UTC).date().isoformat()
    key = f"{name}_{today}"
    if (hit := cache.get_json("_external/ssois", key, CACHE_S)) is not None:
        return hit
    params = {
        "lang": "en",
        "object": name,
        "search": "bynameCADC",
        "epoch1": START,
        "epoch2": today,
        "eellipse": "",
        "eunits": "arcseconds",
        "extres": "no",
        "xyres": "no",
        "format": "tsv",
    }
    r = await http.get(URL, params=params, timeout=90, retries=1)
    raise_for_upstream(r, "cadc")
    rows, not_found = parse_tsv(r.text)
    if not rows and not not_found:
        raise UpstreamError("UPSTREAM_BAD_RESPONSE", "cadc", r.text[:120])
    out = {**base, "query": name, "range": [START, today]}
    out |= {"status": "not_found"} if not_found else {"status": "ok", **summarise(rows)}
    cache.put_json("_external/ssois", key, out)
    return out
