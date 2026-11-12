"""SIMBAD via TAP with a mirror list (Strasbourg was down on 2026-11-12; the CfA mirror worked)."""

from __future__ import annotations

import csv
import io
import logging
import re

from ..config_loader import upstreams
from ..http import UpstreamError, http

log = logging.getLogger("skytracker.simbad")

_ADQL_SAFE = re.compile(r"[^A-Za-z0-9 +\-.*_'/()\[\]]")


def adql_str(value: str) -> str:
    """Escape a user string for an ADQL single-quoted literal (also strips odd characters)."""
    v = _ADQL_SAFE.sub("", value)[:80]
    return "'" + v.replace("'", "''") + "'"


async def tap_query(adql: str, timeout: float = 20) -> list[dict]:
    mirrors = getattr(upstreams().groups["cds"], "simbad_tap_mirrors", None) or [
        "https://simbad.cfa.harvard.edu/simbad/sim-tap"
    ]
    last: Exception | None = None
    for base in mirrors:
        try:
            r = await http.get(
                base + "/sync",
                params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql},
                timeout=timeout,
                retries=1,
            )
        except UpstreamError as e:
            last = e
            continue
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and "csv" in ctype:
            return list(csv.DictReader(io.StringIO(r.text)))
        last = UpstreamError("UPSTREAM_UNAVAILABLE", "simbad", f"{base} {r.status_code}")
        log.info("SIMBAD mirror %s failed with %s, trying next", base, r.status_code)
    raise last or UpstreamError("UPSTREAM_UNAVAILABLE", "simbad")


def _f(v: str | None) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


async def object_basic(main_id: str) -> dict | None:
    """Type, spectral type, parallax, proper motion, redshift, V/K magnitudes for a SIMBAD main_id."""
    q = f"""
    SELECT b.main_id, b.otype, t.label AS otype_label, t.description AS otype_desc, b.ra, b.dec,
           b.sp_type, b.morph_type, b.plx_value, b.plx_err, b.pmra, b.pmdec, b.rvz_redshift, b.rvz_radvel,
           b.galdim_majaxis, b.galdim_minaxis, f.filter, f.flux
    FROM basic AS b
    LEFT JOIN otypedef AS t ON t.otype = b.otype
    LEFT JOIN flux AS f ON f.oidref = b.oid AND f.filter IN ('V','K','J','H')
    WHERE b.main_id = {adql_str(main_id)}
    """
    rows = await tap_query(q)
    if not rows:
        return None
    r0 = rows[0]
    mags = {r["filter"]: _f(r["flux"]) for r in rows if r.get("filter")}
    return {
        "main_id": r0["main_id"],
        "otype": r0["otype"],
        "otype_label": r0.get("otype_label") or None,
        "otype_desc": r0.get("otype_desc") or None,
        "ra": _f(r0["ra"]),
        "dec": _f(r0["dec"]),
        "sp_type": r0.get("sp_type") or None,
        "morph_type": r0.get("morph_type") or None,
        "plx_mas": _f(r0.get("plx_value")),
        "plx_err_mas": _f(r0.get("plx_err")),
        "pmra_mas_yr": _f(r0.get("pmra")),
        "pmdec_mas_yr": _f(r0.get("pmdec")),
        "redshift": _f(r0.get("rvz_redshift")),
        "radvel_km_s": _f(r0.get("rvz_radvel")),
        "major_axis_arcmin": _f(r0.get("galdim_majaxis")),
        "mags": mags,
    }


async def suggest(text: str, limit: int = 8) -> list[dict]:
    """Prefix search on SIMBAD identifiers, e.g. 'WISE 0855' -> 'WISE J085510.83-071442.5'."""
    t = re.sub(r"\s+", " ", text.strip())
    if len(t) < 2:
        return []
    core = t.replace(" ", "%")
    variants = {core, core.upper(), core.capitalize(), "NAME " + core, "NAME " + core.capitalize()}
    where = " OR ".join(f"i.id LIKE {adql_str(v + '%')}" for v in sorted(variants))
    q = (
        f"SELECT TOP {limit * 3} i.id, b.main_id, b.otype, b.ra, b.dec FROM ident AS i "
        f"JOIN basic AS b ON i.oidref = b.oid WHERE {where}"
    )
    rows = await tap_query(q, timeout=15)
    seen: set[str] = set()
    out = []
    for r in rows:
        if r["main_id"] in seen:
            continue
        seen.add(r["main_id"])
        out.append(
            {
                "label": r["id"].removeprefix("NAME "),
                "main_id": r["main_id"],
                "otype": r["otype"],
                "ra": _f(r["ra"]),
                "dec": _f(r["dec"]),
                "source": "SIMBAD",
            }
        )
        if len(out) >= limit:
            break
    return out


async def same_type(otype: str, exclude_main_id: str, ra: float | None = None, limit: int = 8) -> list[dict]:
    """Well-studied objects of the same SIMBAD type (most bibliographic references first)."""
    q = f"""
    SELECT TOP {limit + 1} b.main_id, b.otype, b.ra, b.dec, b.nbref FROM basic AS b
    WHERE b.otype = {adql_str(otype)} AND b.main_id <> {adql_str(exclude_main_id)}
    ORDER BY b.nbref DESC
    """
    rows = await tap_query(q, timeout=20)
    return [
        {
            "label": r["main_id"].removeprefix("NAME "),
            "main_id": r["main_id"],
            "otype": r["otype"],
            "ra": _f(r["ra"]),
            "dec": _f(r["dec"]),
            "source": "SIMBAD",
        }
        for r in rows
    ][:limit]
