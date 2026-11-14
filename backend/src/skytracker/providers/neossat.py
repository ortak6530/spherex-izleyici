"""NEOSSat (Canadian Space Agency) observations containing a position, from CADC's CAOM TAP service.

Verified live 2026-11-14 (DATA_SOURCES §12):
- service from the CADC registry (reg/resource-caps): ivo://cadc.nrc.ca/argus =
  https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus ; collection 'NEOSSAT' = 773 583 observations;
  o.type 'object' (695 057) / 'dark' (78 526) - darks are left out (guide: OBSTYPE = OBJECT).
- positional query: INTERSECTS(POINT, caom2.Plane.position_bounds); 2-20 s.
- products per observation: cord, cor, raw, clean. Guide order: CORD > COR > RAW (RAW only with a
  warning); CLEAN (old CSA software, not cropped) is never used.
- caom2ops/datalink?ID=<publisherID> -> VOTable with the preview PNG (#preview) and FITS (#this) URLs.
Links only: nothing is downloaded or processed here. FILTER = CLEAR (unfiltered optical), so no
brightness comparison with SPHEREx; the WCS is based on spacecraft attitude (ACS) estimates.
"""

from __future__ import annotations

import asyncio
import csv
import io
import re

from astropy.time import Time

from .. import cache
from ..http import UpstreamError, http, raise_for_upstream

TAP_SYNC = "https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus/sync"
DATALINK = "https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/caom2ops/datalink"
MAX_PLANES = 400
SHOW = 30
LINKED = 10
CACHE_S = 86400
PRODUCT_ORDER = {"cord": 0, "cor": 1, "raw": 2}  # 'clean' is never used
NOTE = (
    "NEOSSat (Kanada Uzay Ajansı) filtresiz optik kamera (FILTER = CLEAR): SPHEREx ile parlaklık "
    "karşılaştırması yapılmaz, yalnızca konum ve zaman. Görüntülerin WCS'i uydu yönelim tahminine "
    "dayanır; konum doğruluğu sınırlıdır."
)


def adql(ra: float, dec: float) -> str:
    # Only floats with fixed precision and constants go into the query (no request text)
    cols = "o.observationID, o.target_name, p.productID, p.publisherID, p.time_bounds_lower, p.time_exposure"
    return (
        f"SELECT TOP {MAX_PLANES} {cols} "  # noqa: S608 - floats and constants only
        "FROM caom2.Plane p JOIN caom2.Observation o ON p.obsID = o.obsID "
        "WHERE o.collection = 'NEOSSAT' AND o.type = 'object' "
        f"AND INTERSECTS(POINT('ICRS', {ra:.6f}, {dec:.6f}), p.position_bounds) = 1 "
        "ORDER BY p.time_bounds_lower DESC"
    )


def pick_products(rows: list[dict]) -> list[dict]:
    """One plane per observation, CORD > COR > RAW; CLEAN and unknown products are dropped."""
    best: dict[str, dict] = {}
    for r in rows:
        pid = (r.get("productID") or "").lower()
        if pid not in PRODUCT_ORDER:
            continue
        cur = best.get(r["observationID"])
        if cur is None or PRODUCT_ORDER[pid] < PRODUCT_ORDER[cur["productID"].lower()]:
            best[r["observationID"]] = r
    out = list(best.values())
    out.sort(key=lambda r: float(r.get("time_bounds_lower") or 0), reverse=True)
    return out


def _links(votable: str) -> dict:
    """preview / FITS URLs from a DataLink VOTable (rows: ID, access_url, semantics, …)."""
    out: dict = {}
    for row in re.findall(r"<TR>(.*?)</TR>", votable, re.S):
        cells = re.findall(r"<TD>(.*?)</TD>", row, re.S)
        if len(cells) >= 3 and cells[1].startswith("https://"):
            if cells[2] == "#preview" and "preview" not in out:
                out["preview"] = cells[1]
            elif cells[2] == "#this" and "fits" not in out:
                out["fits"] = cells[1]
    return out


async def _datalink(publisher_id: str) -> dict:
    if (hit := cache.get_json("_external/neossat_dl", publisher_id, 7 * CACHE_S)) is not None:
        return hit
    try:
        r = await http.get(DATALINK, params={"ID": publisher_id}, timeout=30, retries=1)
        links = _links(r.text) if r.status_code == 200 else {}
    except UpstreamError:
        links = {}
    cache.put_json("_external/neossat_dl", publisher_id, links)
    return links


async def search(ra: float, dec: float) -> dict:
    key = f"{ra:.4f}_{dec:+.4f}"
    if (hit := cache.get_json("_external/neossat", key, CACHE_S)) is not None:
        return hit
    r = await http.get(TAP_SYNC, params={"LANG": "ADQL", "FORMAT": "csv", "QUERY": adql(ra, dec)}, timeout=60)
    raise_for_upstream(r, "cadc")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    if rows and "observationID" not in rows[0]:
        raise UpstreamError("UPSTREAM_BAD_RESPONSE", "cadc", r.text[:120])
    obs = pick_products(rows)
    shown = obs[:SHOW]
    links = await asyncio.gather(*(_datalink(o["publisherID"]) for o in shown[:LINKED]))
    items = []
    for i, o in enumerate(shown):
        mjd = float(o["time_bounds_lower"]) if o.get("time_bounds_lower") else None
        items.append(
            {
                "observation_id": o["observationID"],
                "date_utc": Time(mjd, format="mjd").isot[:19] + "Z" if mjd else None,
                "exposure_s": float(o["time_exposure"]) if o.get("time_exposure") else None,
                "product": o["productID"].lower(),
                "raw_warning": o["productID"].lower() == "raw",
                "target_name": o.get("target_name") or None,
                **(links[i] if i < len(links) else {}),
            }
        )
    out = {
        "items": items,
        "n_observations": len(obs),
        "truncated": len(rows) >= MAX_PLANES,
        "source": "CADC CAOM TAP (argus), koleksiyon NEOSSAT",
        "note": NOTE,
    }
    cache.put_json("_external/neossat", key, out)
    return out
