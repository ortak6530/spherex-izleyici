"""Gaia DR3 sources around a position, from the ESA Gaia archive TAP (gaiadr3.gaia_source) with pyvo.

Positions are ICRS at epoch J2016.0. Missing proper motion or parallax stays None ("veri yok"), it is
never replaced by 0 (DECISIONS §4e, Aşama 4 eki). Verified live 2026-11-14: Barnard field, r = 0.0707°,
G < 19 -> 424 rows in 2.4 s (DATA_SOURCES §4.11). astroquery is not used.
"""

from __future__ import annotations

import asyncio
import logging
import math
from urllib.parse import urlparse

import requests

from .. import cache
from ..config_loader import upstreams
from ..http import UpstreamError

log = logging.getLogger("skytracker.gaia")
TAP_URL = "https://gea.esac.esa.int/tap-server/tap"
G_LIMIT = 19.0
MAX_ROWS = 500
CACHE_S = 7 * 86400
EPOCH = 2016.0
COLUMNS = (
    "source_id, ra, dec, ra_error, dec_error, parallax, parallax_error, pmra, pmdec, phot_g_mean_mag, ruwe,"
    " astrometric_params_solved"
)
NEAR_RADIUS_DEG = 15 / 3600  # target lookup: no magnitude limit, small circle
_sem = asyncio.Semaphore(2)


class _TimeoutSession(requests.Session):
    """pyvo uses requests; give every call our timeout (pyvo has no timeout argument)."""

    def __init__(self, timeout: float):
        super().__init__()
        self._timeout = timeout

    def request(self, *a, **kw):
        kw.setdefault("timeout", self._timeout)
        return super().request(*a, **kw)


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _circle(ra: float, dec: float, radius_deg: float) -> str:
    return f"1 = CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.7f}, {dec:.7f}, {radius_deg:.6f}))"


# ADQL is built only from floats formatted with fixed precision and module constants (no request text),
# so the S608 "SQL injection" warnings below do not apply.


def adql(ra: float, dec: float, radius_deg: float) -> str:
    return (
        f"SELECT TOP {MAX_ROWS} {COLUMNS} FROM gaiadr3.gaia_source WHERE {_circle(ra, dec, radius_deg)} "  # noqa: S608
        f"AND phot_g_mean_mag < {G_LIMIT} ORDER BY phot_g_mean_mag"
    )


def adql_count(ra: float, dec: float, radius_deg: float) -> str:
    """Untruncated number of G < 19 sources: the density for chance-coincidence probabilities."""
    return (
        f"SELECT COUNT(*) AS n FROM gaiadr3.gaia_source WHERE {_circle(ra, dec, radius_deg)} "  # noqa: S608
        f"AND phot_g_mean_mag < {G_LIMIT}"
    )


def adql_near(ra: float, dec: float) -> str:
    return f"SELECT TOP 20 {COLUMNS} FROM gaiadr3.gaia_source WHERE {_circle(ra, dec, NEAR_RADIUS_DEG)}"  # noqa: S608


def _service():
    import pyvo  # heavy import, only when Gaia is used

    host = urlparse(TAP_URL).hostname
    if host not in upstreams().allowed_hosts:  # same outbound allowlist as the httpx client
        raise UpstreamError("HOST_NOT_ALLOWED", "esa", host or "")
    g = upstreams().groups.get("esa")
    return pyvo.dal.TAPService(TAP_URL, session=_TimeoutSession(g.timeout if g else 30))


def _count(q: str) -> int:
    return int(_service().run_sync(q).to_table()[0][0])


def _query(q: str) -> list[dict]:
    table = _service().run_sync(q, maxrec=MAX_ROWS).to_table()
    rows = []
    for r in table:
        rows.append(
            {
                "source_id": str(r["source_id"]),
                "ra": _num(r["ra"]),
                "dec": _num(r["dec"]),
                "ra_error_mas": _num(r["ra_error"]),
                "dec_error_mas": _num(r["dec_error"]),
                "parallax_mas": _num(r["parallax"]),
                "parallax_error_mas": _num(r["parallax_error"]),
                "pmra_mas_yr": _num(r["pmra"]),  # None when Gaia has no 5/6-parameter solution
                "pmdec_mas_yr": _num(r["pmdec"]),
                "g_mag": _num(r["phot_g_mean_mag"]),
                "ruwe": _num(r["ruwe"]),
                "params_solved": int(r["astrometric_params_solved"])
                if _num(r["astrometric_params_solved"])
                else None,
            }
        )
    return [r for r in rows if r["ra"] is not None and r["dec"] is not None]


async def _run(fn, q: str):
    async with _sem:
        try:
            return await asyncio.to_thread(fn, q)
        except UpstreamError:
            raise
        except Exception as e:  # noqa: BLE001 - pyvo/requests errors, timeouts
            log.info("Gaia TAP failed: %s", e)
            raise UpstreamError("UPSTREAM_UNAVAILABLE", "esa", str(e)[:200]) from e


async def cone(ra: float, dec: float, radius_deg: float, near: tuple[float, float] | None = None) -> dict:
    """Field sources (G < 19, brightest MAX_ROWS), their untruncated count, and - around `near`
    (the target's expected J2016.0 position) - every Gaia source without a magnitude limit."""
    nr = near or (ra, dec)
    key = f"{ra:.5f}_{dec:+.5f}_{radius_deg:.4f}_{nr[0]:.5f}_{nr[1]:+.5f}"
    if (hit := cache.get_json("_external/gaia", key, CACHE_S)) is not None:
        return hit
    rows, n_total, near_rows = await asyncio.gather(
        _run(_query, adql(ra, dec, radius_deg)),
        _run(_count, adql_count(ra, dec, radius_deg)),
        _run(_query, adql_near(*nr)),
    )
    out = {
        "sources": rows,
        "n_total": n_total,
        "near": near_rows,
        "radius_deg": radius_deg,
        "g_limit": G_LIMIT,
        "epoch": EPOCH,
        "truncated": n_total > len(rows),
        "source": "ESA Gaia DR3 (gaiadr3.gaia_source)",
    }
    cache.put_json("_external/gaia", key, out)
    return out
