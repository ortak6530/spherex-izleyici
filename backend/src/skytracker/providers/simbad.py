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


def adql_like_prefix(parts: list[str]) -> str:
    """LIKE pattern 'p1%p2%…%': each user part is cleaned like adql_str; only we add the % wildcards.

    (adql_str strips '%', so `adql_str(v + '%')` silently became an exact match — fixed 2026-11-13.)
    """
    clean = [_ADQL_SAFE.sub("", p) for p in parts]
    v = "%".join(c for c in clean if c)[:80]
    return "'" + v.replace("'", "''") + "%'"


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


def like_words(text: str) -> list[str]:
    """'m3' -> ['m ', '3'], 'wise 0855' -> ['wise', '0855'].

    SIMBAD pads catalogue numbers with spaces ('M   3', 'NGC  1976'), so letters glued to a number must be
    followed directly by a space: 'M %3%' matches 'M   3' and 'M  31' but not 'MSX …', 'MCC 31' or 'MZ 350'.
    """
    words = []
    for w in re.split(r"\s+", text.strip()):
        parts = [p for p in re.split(r"(?<=[A-Za-z])(?=\d)", w) if p]
        words += [*(p + " " for p in parts[:-1]), parts[-1]] if parts else []
    return words


def suggest_patterns(text: str) -> list[str]:
    """LIKE prefix patterns; the CfA mirror has no ILIKE, so case variants are spelled out."""
    words = like_words(text)
    if not words or len("".join(words)) < 2:
        return []
    cases = {
        tuple(words),
        tuple(w.upper() for w in words),
        tuple(w.capitalize() for w in words),
    }
    pats = {adql_like_prefix(list(c)) for c in cases}
    pats |= {adql_like_prefix(["NAME " + c[0], *c[1:]]) for c in cases if not c[0].isupper() or len(c[0]) > 3}
    return sorted(pats)


async def suggest(text: str, limit: int = 8, timeout: float = 15) -> list[dict]:
    """Prefix search on SIMBAD identifiers, e.g. 'WISE 0855' -> 'WISE J085510.83-071442.5'."""
    pats = suggest_patterns(text)
    if not pats:
        return []
    where = " OR ".join(f"i.id LIKE {p}" for p in pats)
    q = (
        f"SELECT TOP {limit * 4} i.id, b.main_id, b.otype, b.ra, b.dec FROM ident AS i "
        f"JOIN basic AS b ON i.oidref = b.oid WHERE {where}"
    )
    rows = await tap_query(q, timeout=timeout)
    # Common names ("NAME …") first, then the shortest identifiers
    rows.sort(key=lambda r: (not r["id"].startswith("NAME "), len(r["id"])))
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
    SELECT TOP {limit + 1} main_id, otype, ra, dec, nbref FROM basic
    WHERE otype = {adql_str(otype)} AND main_id <> {adql_str(exclude_main_id)}
    ORDER BY nbref DESC
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
