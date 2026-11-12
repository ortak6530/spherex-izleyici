"""Proper-motion propagation. SIMBAD/Sesame positions are ICRS at epoch J2000.0; a fast star such as
Barnard's Star (~10.4"/yr) is ~4.4' away from that position in 2026, i.e. ~43 SPHEREx pixels.

Linear propagation (no parallax, no radial-velocity term): good to well below one SPHEREx pixel (6.15")
for 2025-2027; annual parallax (Barnard: 0.55") is ignored and noted in the UI.
"""

from __future__ import annotations

import math

J2000_MJD = 51544.5
DAYS_PER_YEAR = 365.25


def mjd_to_jyear(mjd: float) -> float:
    return 2000.0 + (mjd - J2000_MJD) / DAYS_PER_YEAR


def propagate(
    ra: float,
    dec: float,
    pmra_mas_yr: float | None,
    pmdec_mas_yr: float | None,
    to_mjd: float,
    from_jyear: float = 2000.0,
) -> tuple[float, float]:
    """pmra is mu_alpha* = mu_alpha cos(dec) (SIMBAD convention), both in mas/yr."""
    if not pmra_mas_yr and not pmdec_mas_yr:
        return ra, dec
    dt = mjd_to_jyear(to_mjd) - from_jyear
    ddec = (pmdec_mas_yr or 0.0) * dt / 3.6e6
    cosd = max(math.cos(math.radians(dec)), 1e-9)
    dra = (pmra_mas_yr or 0.0) * dt / 3.6e6 / cosd
    return (ra + dra) % 360.0, max(-90.0, min(90.0, dec + ddec))


def jyear_to_mjd(jyear: float) -> float:
    return J2000_MJD + (jyear - 2000.0) * DAYS_PER_YEAR


SEARCH_EPOCH = 2026.0  # positions used for SPHEREx searches (mid-mission)
