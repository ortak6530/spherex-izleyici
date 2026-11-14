"""Gaia layer: parallax + proper motion to SPHEREx dates, candidate counterpart with chance probability,
missing astrometry stays "veri yok", queries and failure handling."""

import asyncio
import math

import numpy as np
from astropy.wcs import WCS

from skytracker.domain.astrometry import jyear_to_mjd
from skytracker.providers import gaia as G
from skytracker.services import gaia_layer as GL
from skytracker.services import time_compare as TC

BARNARD = {  # Gaia DR3 4472832130942575872 (values as returned live 2026-11-14, rounded)
    "source_id": "4472832130942575872",
    "ra": 269.44850252543836,
    "dec": 4.739420051112412,
    "parallax_mas": 546.976,
    "pmra_mas_yr": -801.551,
    "pmdec_mas_yr": 10362.394,
    "g_mag": 8.194,
    "ruwe": 1.08,
    "params_solved": 31,
}
LUHMAN16 = {
    "source_id": "5353626573555863424",
    "ra": 162.30840,
    "dec": -53.31810,
    "parallax_mas": None,
    "pmra_mas_yr": None,
    "pmdec_mas_yr": None,
    "g_mag": 16.92,
    "ruwe": None,
    "params_solved": 3,
}


def test_parallax_matches_an_independent_vector_computation():
    """Geometric check: apparent direction = star position (barycentric, distance 1/ϖ) − Earth position."""
    mjd = jyear_to_mjd(2025.65)
    star = dict(BARNARD, pmra_mas_yr=0.0, pmdec_mas_yr=0.0)  # isolate the parallax term
    p = GL.position_at(star, mjd)
    d_au = 206264.806 / (star["parallax_mas"] / 1000)
    a, dlt = math.radians(star["ra"]), math.radians(star["dec"])
    u = d_au * np.array([math.cos(dlt) * math.cos(a), math.cos(dlt) * math.sin(a), math.sin(dlt)])
    v = u - np.array(GL.earth_barycentric_au(mjd))
    ra_v = math.degrees(math.atan2(v[1], v[0])) % 360
    dec_v = math.degrees(math.asin(v[2] / np.linalg.norm(v)))
    assert abs((p["ra"] - ra_v) * 3600 * math.cos(dlt)) < 0.002  # < 2 mas
    assert abs((p["dec"] - dec_v) * 3600) < 0.002
    # and the parallax term itself is of the right size (Barnard: up to ~0.55″)
    shift = math.hypot((p["ra"] - star["ra"]) * math.cos(dlt), p["dec"] - star["dec"]) * 3600
    assert 0.05 < shift < 0.56


def test_missing_astrometry_is_not_zero_filled():
    p = GL.position_at(LUHMAN16, jyear_to_mjd(2025.5))
    assert (p["ra"], p["dec"]) == (LUHMAN16["ra"], LUHMAN16["dec"])
    assert p["has_pm"] is False and p["has_parallax"] is False


def test_chance_probability_uses_the_untruncated_density():
    # Luhman 16 field: 716 sources with G < 19 inside r = 0.0707°
    assert (
        abs(
            GL.chance_probability(716, 0.0707)
            - (1 - math.exp(-math.pi * 6.15**2 * 716 / (math.pi * (0.0707 * 3600) ** 2)))
        )
        < 1e-12
    )
    assert GL.chance_probability(716, 0.0707, 0.71) < 0.01  # at the observed 0.71″ it is small
    assert GL.chance_probability(10, 0) is None


def grid(ra, dec):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [30.5, 30.5]
    w.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]
    return w


def field(sources, near):
    return {
        "sources": sources,
        "near": near,
        "n_total": 422,
        "radius_deg": 0.0707,
        "g_limit": 19.0,
        "truncated": False,
        "source": "ESA Gaia DR3 (gaiadr3.gaia_source)",
    }


def test_build_marks_candidates_and_expected_positions():
    mjd_a, mjd_b = jyear_to_mjd(2025.65), jyear_to_mjd(2026.72)
    pa = GL.position_at(BARNARD, mjd_a)
    w = grid(pa["ra"], pa["dec"])
    far = dict(BARNARD, source_id="far", ra=BARNARD["ra"] + 1.0, g_mag=12.0)  # outside the 59x59 grid
    layer = GL.build(
        field([BARNARD, far], [BARNARD]),
        w,
        mjd_a,
        mjd_b,
        (BARNARD["ra"], BARNARD["dec"]),
        (pa["ra"], pa["dec"]),
        {"arcsec": 12.5},
        6.15,
        (59, 59),
    )
    assert [m["source_id"] for m in layer["markers"]] == [BARNARD["source_id"]]
    t = layer["target"]
    assert t["source_id"] == BARNARD["source_id"] and t["separation_2016_arcsec"] < 0.01
    assert t["expected_a_px"] and t["expected_b_px"] and 10.5 < t["expected_shift_arcsec"] < 11.8
    assert "aday" in layer["note"] and "kesin eşleşme değildir" in layer["note"]


def test_no_gaia_motion_means_no_expected_position():
    w = grid(LUHMAN16["ra"], LUHMAN16["dec"])
    layer = GL.build(
        field([LUHMAN16], [LUHMAN16]),
        w,
        jyear_to_mjd(2025.4),
        jyear_to_mjd(2026.4),
        (LUHMAN16["ra"] + 0.7 / 3600, LUHMAN16["dec"]),
        None,
        {"arcsec": 2.9},
        6.15,
        (59, 59),
    )
    t = layer["target"]
    assert t and t["has_pm"] is False and t["expected_a_px"] is None and t["expected_shift_arcsec"] is None
    # nothing within one pixel -> no candidate at all (never a forced match)
    none = GL.build(
        field([LUHMAN16], [LUHMAN16]),
        w,
        0,
        0,
        (LUHMAN16["ra"] + 0.01, LUHMAN16["dec"]),
        None,
        None,
        6.15,
        (59, 59),
    )
    assert none["target"] is None


def test_queries_and_failure_never_block_the_comparison(monkeypatch):
    q = G.adql(269.45, 4.74, 0.0707)
    assert "gaiadr3.gaia_source" in q and "phot_g_mean_mag < 19" in q and "TOP 500" in q
    assert G.adql_count(269.45, 4.74, 0.0707).startswith("SELECT COUNT(*)")
    assert "phot_g_mean_mag" not in G.adql_near(269.45, 4.74).split("WHERE")[1]  # no magnitude limit
    from skytracker.config_loader import upstreams

    assert "gea.esac.esa.int" in upstreams().allowed_hosts

    async def boom(*a, **k):
        raise RuntimeError("Gaia down")

    monkeypatch.setattr(TC.gaia, "cone", boom)
    assert asyncio.run(TC._gaia_field(1.0, 2.0, 0.07, (1.0, 2.0))) is None
