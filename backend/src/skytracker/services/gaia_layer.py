"""Gaia layer of a time comparison.

(A) Expected position of the target at each SPHEREx date from Gaia DR3 (epoch 2016.0): proper motion
    plus annual parallax. SPHEREx is in low Earth orbit, so the observer is Earth (the 700 km offset
    is ~5e-6 AU, negligible). Earth's barycentric position comes from astropy's built-in ephemeris
    (no download). Parallax shift (Explanatory Supplement to the Astronomical Almanac, 7.2):
        Δα* = ϖ (X sin α − Y cos α),  Δδ = ϖ (X cos α sin δ + Y sin α sin δ − Z cos δ)
(B) Gaia sources in the field, drawn as *candidate* markers ("aday"). Nothing here is a definite
    match: the target's counterpart is the nearest Gaia source within one SPHEREx pixel (6.15″, the
    position uncertainty of a SPHEREx centroid), found at Gaia's epoch J2016.0, shown with its
    chance-coincidence probability P = 1 − exp(−π r² ρ): ρ = untruncated Gaia density (G < 19, COUNT
    query) in the queried circle, r = the observed separation (and, separately, the match radius).
Missing proper motion / parallax stay None and are reported as "veri yok", never as 0.
"""

from __future__ import annotations

import math

from astropy.coordinates import get_body_barycentric
from astropy.time import Time

from ..domain.astrometry import mjd_to_jyear

MATCH_RADIUS_ARCSEC = 6.15  # one SPHEREx pixel
MAX_MARKERS = 300


def earth_barycentric_au(mjd: float) -> tuple[float, float, float]:
    p = get_body_barycentric("earth", Time(mjd, format="mjd", scale="tdb"))
    return float(p.x.to_value("au")), float(p.y.to_value("au")), float(p.z.to_value("au"))


def position_at(src: dict, mjd: float) -> dict:
    """Gaia position moved from J2016.0 to `mjd`: proper motion (if any) + parallax (if any)."""
    ra, dec = src["ra"], src["dec"]
    dt = mjd_to_jyear(mjd) - 2016.0
    cosd = max(math.cos(math.radians(dec)), 1e-9)
    has_pm = src.get("pmra_mas_yr") is not None and src.get("pmdec_mas_yr") is not None
    has_plx = src.get("parallax_mas") is not None and src["parallax_mas"] > 0
    dra_mas = (src["pmra_mas_yr"] * dt) if has_pm else 0.0  # mu_alpha* (Gaia convention)
    ddec_mas = (src["pmdec_mas_yr"] * dt) if has_pm else 0.0
    if has_plx:
        x, y, z = earth_barycentric_au(mjd)
        a, d = math.radians(ra), math.radians(dec)
        p = src["parallax_mas"]
        dra_mas += p * (x * math.sin(a) - y * math.cos(a))
        ddec_mas += p * (x * math.cos(a) * math.sin(d) + y * math.sin(a) * math.sin(d) - z * math.cos(d))
    return {
        "ra": (ra + dra_mas / 3.6e6 / cosd) % 360.0,
        "dec": dec + ddec_mas / 3.6e6,
        "has_pm": has_pm,
        "has_parallax": has_plx,
    }


def _sep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * 3600


def chance_probability(
    n_sources: int, radius_deg: float, r_arcsec: float = MATCH_RADIUS_ARCSEC
) -> float | None:
    """P(at least one unrelated Gaia source within r) for a uniform density over the queried circle."""
    if radius_deg <= 0:
        return None
    area = math.pi * (radius_deg * 3600) ** 2  # arcsec^2 (small-circle approximation)
    rho = n_sources / area
    return 1.0 - math.exp(-math.pi * r_arcsec**2 * rho)


def build(
    field: dict | None,
    wcs,
    mjd_a: float,
    mjd_b: float,
    ref_2016: tuple[float, float],
    measured_a: tuple[float, float] | None,
    shift: dict | None,
    pixel_scale: float,
    shape,
) -> dict | None:
    """Everything the viewer and the result panel show. `field` is providers.gaia.cone() output;
    `ref_2016` is the target's expected J2016.0 position (SIMBAD + proper motion), so the match is
    made at Gaia's own epoch even for sources without a Gaia proper motion (e.g. Luhman 16)."""
    if not field:
        return None
    sources = field["sources"]
    ny, nx = shape
    markers = []
    for s in sources:
        p = position_at(s, mjd_a)
        x, y = (float(v) for v in wcs.world_to_pixel_values(p["ra"], p["dec"]))
        if -0.5 <= x < nx - 0.5 and -0.5 <= y < ny - 0.5:
            markers.append(
                {
                    "source_id": s["source_id"],
                    "px": [round(x, 2), round(y, 2)],
                    "g_mag": s["g_mag"],
                    "has_pm": p["has_pm"],
                    "has_parallax": p["has_parallax"],
                }
            )
    markers.sort(key=lambda m: m["g_mag"] if m["g_mag"] is not None else 99)
    markers = markers[:MAX_MARKERS]

    # Candidate counterpart: nearest Gaia source (no magnitude limit, J2016.0) to the target's expected
    # J2016.0 position; within one SPHEREx pixel it is shown as "aday", never as a sure match
    candidates = field.get("near") or sources
    best, best_sep = None, None
    for s in candidates:
        sep = _sep_arcsec(ref_2016[0], ref_2016[1], s["ra"], s["dec"])
        if best_sep is None or sep < best_sep:
            best, best_sep = s, sep
    n_total = field.get("n_total") or len(sources)
    p_chance = chance_probability(n_total, field["radius_deg"])
    target = None
    if best is not None and best_sep is not None and best_sep <= MATCH_RADIUS_ARCSEC:
        pa, pb = position_at(best, mjd_a), position_at(best, mjd_b)
        target = {
            "source_id": best["source_id"],
            "g_mag": best["g_mag"],
            "separation_2016_arcsec": best_sep,
            "match_radius_arcsec": MATCH_RADIUS_ARCSEC,
            # chance of an unrelated G < 19 source this close (at the observed separation, floor 0.1″)
            "chance_probability": chance_probability(n_total, field["radius_deg"], max(best_sep, 0.1)),
            "chance_probability_radius": p_chance,  # … anywhere within the 6.15″ match radius
            "parallax_mas": best["parallax_mas"],
            "pmra_mas_yr": best["pmra_mas_yr"],
            "pmdec_mas_yr": best["pmdec_mas_yr"],
            "ruwe": best["ruwe"],
            "params_solved": best.get("params_solved"),
            "has_pm": pa["has_pm"],
            "has_parallax": pa["has_parallax"],
            # (A) expected positions only with a Gaia proper motion; otherwise "veri yok"
            "expected_a_px": None,
            "expected_b_px": None,
            "expected_shift_arcsec": None,
            "difference_px": None,
            "separation_a_arcsec": None,
        }
        if pa["has_pm"]:
            exp_shift = _sep_arcsec(pa["ra"], pa["dec"], pb["ra"], pb["dec"])
            ax, ay = (float(v) for v in wcs.world_to_pixel_values(pa["ra"], pa["dec"]))
            bx, by = (float(v) for v in wcs.world_to_pixel_values(pb["ra"], pb["dec"]))
            target |= {
                "expected_a_px": [round(ax, 2), round(ay, 2)],
                "expected_b_px": [round(bx, 2), round(by, 2)],
                "expected_shift_arcsec": exp_shift,
                "expected_shift_px": exp_shift / pixel_scale,
                "measured_shift_arcsec": shift["arcsec"] if shift else None,
                "difference_px": abs(shift["arcsec"] - exp_shift) / pixel_scale if shift else None,
                "separation_a_arcsec": _sep_arcsec(measured_a[0], measured_a[1], pa["ra"], pa["dec"])
                if measured_a
                else None,
            }
    return {
        "markers": markers,
        "n_field": n_total,
        "n_markers_queried": len(sources),
        "g_limit": field["g_limit"],
        "radius_deg": field["radius_deg"],
        "truncated": field["truncated"],
        "target": target,
        "nearest_separation_arcsec": best_sep,
        "chance_probability": p_chance,
        "source": field["source"],
        "epoch": "J2016.0 → SPHEREx tarihleri (öz hareket + yıllık paralaks)",
        "note": "Gaia işaretleri olası karşılıklardır (aday); kesin eşleşme değildir.",
    }
