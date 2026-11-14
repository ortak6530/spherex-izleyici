"""Live position: where the object is now, and "Benim gökyüzümde" (altitude, direction, rise/set) for a
chosen city or latitude/longitude. The browser's location is never asked for.

- Stars / galaxies: SIMBAD J2000 position + proper motion propagated to now (parallax ignored).
- Solar-system bodies: JPL Horizons observer ephemeris (24 h at 10-minute steps, cached 30 min), linearly
  interpolated to the current time; Horizons is never called every 10 s.
- Altitude / azimuth of fixed positions: astropy AltAz (precession, nutation, aberration; no refraction).
  IERS tables are not downloaded at run time (outbound allowlist): UT1-UTC falls back to 0, an error
  of < 1 s in time, far below what the page shows.
- Rise / set: the horizon is 0° geometric altitude (refraction and terrain ignored), from the 24 h
  altitude series; "always above" / "never above" when it does not cross.

Verified live 2026-11-14 (DATA_SOURCES §4.10): COMMAND 'N;' for numbered asteroids ('DES=433;' is a
different body), 'DES=x;CAP;' for comets (1P, 2P, 2025 N1: several apparitions otherwise), 'DES=x;'
for other provisional designations (CAP fails for 2024 YR4).
"""

from __future__ import annotations

import datetime as dt
import math
import re

import numpy as np
from astropy import units as u
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.time import Time
from astropy.utils import iers

from .. import cache
from ..domain.astrometry import propagate
from ..http import UpstreamError, http, raise_for_upstream

iers.conf.auto_download = False  # no outbound request outside upstreams.toml
iers.conf.iers_degraded_accuracy = "ignore"

HORIZONS = "https://ssd.jpl.nasa.gov/api/horizons.api"
SERIES_HOURS = 24
SERIES_STEP_MIN = 10
CACHE_S = 1800


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- fixed positions ----------


def star_now(target: dict, when: dt.datetime) -> dict:
    """Position at `when` from SIMBAD J2000 + proper motion; coordinates/galaxies stay where they are."""
    mjd = Time(when).mjd
    if target.get("ra_j2000") is not None:
        ra, dec = propagate(
            target["ra_j2000"],
            target["dec_j2000"],
            target.get("pmra_mas_yr"),
            target.get("pmdec_mas_yr"),
            mjd,
        )
        cosd = math.cos(math.radians(target["dec_j2000"]))
        moved = math.hypot((ra - target["ra_j2000"]) * cosd, dec - target["dec_j2000"]) * 3600
        has_pm = bool(target.get("pmra_mas_yr") or target.get("pmdec_mas_yr"))
        return {
            "ra": ra,
            "dec": dec,
            "moved_since_j2000_arcsec": moved if has_pm else None,
            "method": "SIMBAD J2000 + öz hareket (paralaks ihmal)" if has_pm else "SIMBAD (öz hareket yok)",
        }
    return {
        "ra": target["ra"],
        "dec": target["dec"],
        "moved_since_j2000_arcsec": None,
        "method": "girdi koordinatı",
    }


def altaz_series(ra: float, dec: float, lat: float, lon: float, start: dt.datetime) -> dict:
    """Altitude/azimuth now and over the next 24 h (fixed RA/Dec), plus rise/transit/set."""
    n = SERIES_HOURS * 60 // SERIES_STEP_MIN + 1
    times = Time(start) + np.arange(n) * SERIES_STEP_MIN * u.min
    frame = AltAz(obstime=times, location=EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=0 * u.m))
    aa = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs").transform_to(frame)
    return _events([t.to_datetime(timezone=dt.UTC) for t in times], aa.alt.deg, aa.az.deg)


def _events(times: list[dt.datetime], alt: np.ndarray, az: np.ndarray) -> dict:
    alt, az = np.asarray(alt, float), np.asarray(az, float)
    out: dict = {"alt_deg": float(alt[0]), "az_deg": float(az[0]), "rise": None, "set": None}
    for i in range(len(alt) - 1):
        a0, a1 = alt[i], alt[i + 1]
        if (a0 < 0 <= a1) or (a0 >= 0 > a1):
            f = a0 / (a0 - a1)
            when = times[i] + (times[i + 1] - times[i]) * f
            key = "rise" if a0 < 0 else "set"
            if out[key] is None:
                out[key] = {
                    "utc": _iso(when),
                    "az_deg": float(az[i] + f * ((az[i + 1] - az[i] + 540) % 360 - 180)),
                }
    k = int(np.argmax(alt))
    out["transit"] = {"utc": _iso(times[k]), "alt_deg": float(alt[k])}
    out["always_up"] = bool((alt >= 0).all())
    out["never_up"] = bool((alt < 0).all())
    out["horizon"] = "0° geometrik ufuk (kırılma ve arazi ihmal)"
    return out


# ---------- solar-system bodies (JPL Horizons) ----------


def horizons_command(designation: str) -> list[str]:
    des = designation.strip()
    if re.fullmatch(r"\d+", des):
        return [f"'{des};'"]  # numbered asteroid (record number); 'DES=433;' is a different body
    return [f"'DES={des};CAP;'", f"'DES={des};'"]


def _parse_horizons(result: str) -> list[dict]:
    s, e = result.find("$$SOE"), result.find("$$EOE")
    if s < 0 or e < 0:
        return []
    head = result[:s].strip().splitlines()
    cols = [c.strip() for c in head[-2].split(",")] if len(head) >= 2 else []
    idx = {name: cols.index(name) for name in cols if name}
    rows = []
    for line in result[s + 5 : e].strip().splitlines():
        p = [x.strip() for x in line.split(",")]

        def val(name: str, p=p) -> float | None:
            i = idx.get(name)
            try:
                return float(p[i]) if i is not None and p[i] not in ("", "n.a.") else None
            except ValueError:
                return None

        when = dt.datetime.strptime(p[0], "%Y-%b-%d %H:%M").replace(tzinfo=dt.UTC)
        mag = val("T-mag") if "T-mag" in idx else val("APmag")
        rows.append(
            {
                "t": when,
                "ra": val("R.A._(ICRF)"),
                "dec": val("DEC_(ICRF)"),
                "az": val("Azi_(a-app)"),
                "el": val("Elev_(a-app)"),
                "mag": mag,
                "delta_au": val("delta"),
            }
        )
    return [r for r in rows if r["ra"] is not None]


async def horizons_series(designation: str, lat: float | None, lon: float | None, start: dt.datetime) -> dict:
    t0 = start.replace(minute=start.minute - start.minute % SERIES_STEP_MIN, second=0, microsecond=0)
    site = f"{lat:.3f},{lon:.3f}" if lat is not None and lon is not None else "geo"
    key = f"{designation}|{site}|{t0:%Y%m%d%H%M}"
    if (hit := cache.get_json("_external/horizons", key, CACHE_S)) is not None:
        for r in hit["rows"]:
            r["t"] = dt.datetime.fromisoformat(r["t"])
        return hit
    params = {
        "format": "json",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "START_TIME": f"'{t0:%Y-%m-%d %H:%M}'",
        "STOP_TIME": f"'{t0 + dt.timedelta(hours=SERIES_HOURS):%Y-%m-%d %H:%M}'",
        "STEP_SIZE": f"'{SERIES_STEP_MIN} m'",
        "QUANTITIES": "'1,4,9,20'" if site != "geo" else "'1,9,20'",
        "ANG_FORMAT": "'DEG'",
        "CSV_FORMAT": "'YES'",
    }
    if site == "geo":
        params["CENTER"] = "'500@399'"
    else:
        params |= {
            "CENTER": "'coord@399'",
            "COORD_TYPE": "'GEODETIC'",
            "SITE_COORD": f"'{lon:.4f},{lat:.4f},0'",
        }
    rows: list[dict] = []
    name = None
    for cmd in horizons_command(designation):
        r = await http.get(HORIZONS, params={**params, "COMMAND": cmd}, timeout=30)
        raise_for_upstream(r, "jpl")
        res = r.json().get("result", "")
        rows = _parse_horizons(res)
        if rows:
            m = re.search(r"Target body name:\s*(.+?)\s{2,}", res)
            name = m.group(1) if m else None
            break
    if not rows:
        raise UpstreamError("HORIZONS_NO_EPHEMERIS", "jpl", designation)
    out = {"rows": rows, "name": name, "site": site}
    cache.put_json("_external/horizons", key, {**out, "rows": [{**r, "t": r["t"].isoformat()} for r in rows]})
    return out


def interpolate(rows: list[dict], when: dt.datetime) -> dict:
    """Linear interpolation between the two ephemeris rows around `when` (RA unwrapped at 0/360)."""
    for a, b in zip(rows, rows[1:], strict=False):
        if a["t"] <= when <= b["t"]:
            f = (when - a["t"]) / (b["t"] - a["t"])

            def lerp(k: str, wrap: bool = False, a=a, b=b, f=f) -> float | None:
                if a[k] is None or b[k] is None:
                    return a[k]
                d = b[k] - a[k]
                if wrap:
                    d = (d + 180) % 360 - 180
                    return (a[k] + f * d) % 360
                return a[k] + f * d

            return {
                "ra": lerp("ra", True),
                "dec": lerp("dec"),
                "az": lerp("az", True),
                "el": lerp("el"),
                "mag": a["mag"],
                "delta_au": lerp("delta_au"),
            }
    r = rows[0] if when < rows[0]["t"] else rows[-1]
    return {
        "ra": r["ra"],
        "dec": r["dec"],
        "az": r["az"],
        "el": r["el"],
        "mag": r["mag"],
        "delta_au": r["delta_au"],
    }


async def snapshot(target: dict, site: dict | None, when: dt.datetime | None = None) -> dict:
    """Everything the live panel shows for one moment."""
    when = when or now_utc()
    out: dict = {"utc": _iso(when), "site": site}
    if target.get("kind") == "solar_system":
        des = target.get("designation")
        if not des:
            raise UpstreamError("HORIZONS_NO_EPHEMERIS", "jpl", "no designation")
        s = await horizons_series(des, site and site["lat"], site and site["lon"], when)
        p = interpolate(s["rows"], when)
        out |= {
            "ra": p["ra"],
            "dec": p["dec"],
            "mag": p["mag"],
            "delta_au": p["delta_au"],
            "method": "JPL Horizons gözlemci efemerisi (10 dk adım, ara değer)",
            "horizons_name": s["name"],
        }
        if site:
            future = [r for r in s["rows"] if r["t"] >= when - dt.timedelta(minutes=SERIES_STEP_MIN)]
            ev = _events([r["t"] for r in future], [r["el"] for r in future], [r["az"] for r in future])
            ev["alt_deg"], ev["az_deg"] = p["el"], p["az"]
            out["sky"] = ev
        return out
    pos = star_now(target, when)
    out |= pos
    if site:
        out["sky"] = altaz_series(pos["ra"], pos["dec"], site["lat"], site["lon"], when)
    return out
