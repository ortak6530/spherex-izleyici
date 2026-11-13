"""Moving objects (comets, asteroids) in SPHEREx frames via IRSA MOST (Moving Object Search Tool).

MOST takes a JPL Horizons designation (SBDB "des": "2025 N1", "433", "2P"; plain names such as
"Ceres" are often ambiguous and rejected) and returns every SPHEREx frame whose footprint contains
the predicted position, with that position per frame, plus a 6-hourly ephemeris.
Verified live 2026-11-13: 3I/ATLAS ("2025 N1") -> 364 DR1 frames (2025-08 ... 2026-04) in ~7 s.
"""

from __future__ import annotations

import contextlib
import io
import logging
import re
import warnings
from dataclasses import asdict, dataclass

import numpy as np
from astropy.io.votable import parse as parse_votable
from astropy.table import Table
from astropy.time import Time

from .. import cache
from ..config_loader import Release, releases
from ..http import UpstreamError, http, raise_for_upstream
from .spherex import SpherexImage, group_visits

log = logging.getLogger("skytracker.most")
MOST_URL = "https://irsa.ipac.caltech.edu/cgi-bin/MOST/nph-most"
IRSA_ROOT = "https://irsa.ipac.caltech.edu/"
MISSION_START = "2025-05-01"
CACHE_TTL_S = 24 * 3600
TRACK_STEP_DAYS = 1.0
DESIGNATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 /\-.]{0,39}$")

# Nominal detector ranges (SIA2 em_min/em_max, identical for DR1/QR3); MOST does not return them.
DETECTOR_RANGE_UM = {
    1: (0.7455, 1.1167),
    2: (1.1033, 1.6499),
    3: (1.6301, 2.4346),
    4: (2.4027, 3.8473),
    5: (3.8113, 4.43),
    6: (4.4115, 5.0096),
}


class MostNameError(Exception):
    """Horizons (via MOST) did not find the designation, or it is ambiguous."""


@dataclass
class MovingFrame:
    image_id: str
    release: str
    obs_id: str
    detector: int
    mjd: float  # exposure start
    mjd_end: float
    date_obs: str
    ra: float  # predicted position of the object in this frame (deg, J2000)
    dec: float
    sun_dist_au: float | None
    geo_dist_au: float | None
    phase_deg: float | None
    vmag: float | None
    dist_ctr_deg: float | None  # distance from the frame centre
    fits_url: str


def _num(v) -> float | None:
    with contextlib.suppress(TypeError, ValueError):
        f = float(v)
        if np.isfinite(f):
            return f
    return None


def _release_for(url: str) -> Release | None:
    return next((r for r in releases().release if r.ibe_prefix and url.startswith(r.ibe_prefix)), None)


def _tables(content: bytes) -> tuple[Table | None, Table | None, str | None]:
    """(frames, ephemeris, object name as Horizons spells it)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        vt = parse_votable(io.BytesIO(content))
    frames = eph = None
    name = None
    for tb in vt.iter_tables():
        for p in tb.params:
            if p.name == "object_name" and p.value:
                name = str(p.value).strip()
        t = tb.to_table(use_names_over_ids=True)
        if "observationid" in t.colnames:
            frames = t
        elif "RA_obs" in t.colnames and "JD" in t.colnames:
            eph = t
    return frames, eph, name


def parse_frames(frames: Table | None) -> tuple[list[MovingFrame], dict[str, int]]:
    """Frames of active releases + a count of frames skipped per (non-active) release."""
    out: list[MovingFrame] = []
    skipped: dict[str, int] = {}
    if frames is None:
        return out, skipped
    for row in frames:
        if str(row["match"]).strip() not in ("1", "True"):
            continue
        url = IRSA_ROOT + str(row["uri"]).lstrip("/")
        rel = _release_for(url)
        if rel is None or rel.status != "active":
            k = rel.id if rel else "unknown"
            skipped[k] = skipped.get(k, 0) + 1
            continue
        det = int(str(row["productid"]).lstrip("D") or 0)
        if det not in DETECTOR_RANGE_UM:
            continue
        obs_id = str(row["observationid"]).strip()
        t0 = float(row["mjd_start"])
        out.append(
            MovingFrame(
                image_id=f"{rel.id}:{obs_id}:D{det}",
                release=rel.id,
                obs_id=obs_id,
                detector=det,
                mjd=t0,
                mjd_end=float(row["mjd_end"]),
                date_obs=Time(t0, format="mjd").isot[:19] + "Z",
                ra=float(row["ra_obj"]),
                dec=float(row["dec_obj"]),
                sun_dist_au=_num(row["sun_dist"]),
                geo_dist_au=_num(row["geo_dist"]),
                phase_deg=_num(row["phase"]),
                vmag=_num(row["vmag"]),
                dist_ctr_deg=_num(row["dist_ctr"]),
                fits_url=url,
            )
        )
    out.sort(key=lambda f: (f.mjd, f.detector))
    return out, skipped


def parse_track(eph: Table | None, step_days: float = TRACK_STEP_DAYS) -> list[dict]:
    """Ephemeris thinned to about one point per `step_days` (for the path plot and Excel)."""
    if eph is None or not len(eph):
        return []
    out: list[dict] = []
    last = -1e9
    for row in eph:
        jd = float(row["JD"])
        if jd - last < step_days - 1e-6:
            continue
        last = jd
        out.append(
            {
                "mjd": round(jd - 2400000.5, 4),
                "date": Time(jd, format="jd").isot[:16] + "Z",
                "ra": round(float(row["RA_obs"]), 6),
                "dec": round(float(row["Dec_obs"]), 6),
                "sun_dist_au": _num(row["HelioDist"]),
                "geo_dist_au": _num(row["GeoDist"]),
                "vmag": _num(row["Vmag"]),
            }
        )
    return out


def _register(f: MovingFrame) -> None:
    """Make the frame known to /sky/cutout and /compare (same image index as SIA2 results)."""
    rel = next(r for r in releases().release if r.id == f.release)
    lo, hi = DETECTOR_RANGE_UM[f.detector]
    img = SpherexImage(
        image_id=f.image_id,
        release=f.release,
        collection=rel.sia_collections[0] if rel.sia_collections else "",
        obs_id=f.obs_id,
        detector=f.detector,
        t_start_mjd=f.mjd,
        t_end_mjd=f.mjd_end,
        date_obs=f.date_obs,
        em_min_um=lo,
        em_max_um=hi,
        fits_url=f.fits_url,
        s3_key=rel.s3_prefix + f.fits_url[len(rel.ibe_prefix) :] if rel.s3_prefix else None,
    )
    cache.put_json("_index/images", f.image_id.replace(":", "_"), asdict(img))


async def query(designation: str, start: str, end: str) -> bytes:
    key = f"{designation}_{start}_{end}"
    if (hit := cache.get_bytes("_external/most", key, ".xml")) is not None and (
        cache.cache_age_s("_external/most", key, ".xml") or 0
    ) < CACHE_TTL_S:
        return hit
    form = {
        "catalog": "spherex",
        "input_type": "name_input",
        "obj_name": designation,
        "obs_begin": start,
        "obs_end": end,
        "output_mode": "VOTable",
    }
    r = await http.post(MOST_URL, files={k: (None, v) for k, v in form.items()}, timeout=180, retries=2)
    if r.status_code == 400 and "Object Name Error" in r.text:
        raise MostNameError(" ".join(r.text.split())[:300])
    raise_for_upstream(r, "irsa")
    if b"<VOTABLE" not in r.content[:2000]:
        raise UpstreamError("UPSTREAM_BAD_RESPONSE", "irsa", r.text[:120])
    cache.put_bytes("_external/most", key, r.content, ".xml")
    return r.content


async def moving_frames(designation: str, start: str, end: str) -> dict:
    raw = await query(designation, start, end)
    frames_t, eph_t, name = _tables(raw)
    frames, skipped = parse_frames(frames_t)
    for f in frames:
        _register(f)
    visits = []
    if frames:
        # group_visits works on SpherexImage-like objects (t_start_mjd / t_end_mjd / release)
        proxies = [
            SpherexImage(
                f.image_id, f.release, "", f.obs_id, f.detector, f.mjd, f.mjd_end, f.date_obs, 0, 0, "", None
            )
            for f in frames
        ]
        for v in group_visits(proxies):
            ids = {i.image_id for i in v["images"]}
            per_det: dict[int, int] = {}
            for f in frames:
                if f.image_id in ids:
                    per_det[f.detector] = per_det.get(f.detector, 0) + 1
            visits.append(
                {
                    "index": v["index"],
                    "label": v["label"],
                    "start": v["start"],
                    "end": v["end"],
                    "releases": v["releases"],
                    "frames_per_detector": per_det,
                    "frame_ids": [f.image_id for f in frames if f.image_id in ids],
                }
            )
    return {
        "designation": designation,
        "horizons_name": name,
        "start": start,
        "end": end,
        "frames": [asdict(f) for f in frames],
        "visits": visits,
        "skipped_releases": skipped,
        "track": parse_track(eph_t),
        "source": "IRSA MOST + JPL Horizons",
    }
