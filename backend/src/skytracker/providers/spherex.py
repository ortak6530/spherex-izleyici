"""SPHEREx data access (NASA/IPAC IRSA): SIA2 coverage, header range-reads for the wavelength at a
target, and cutouts from the IRSA cutout service. Everything is cached per data release."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import math
import warnings
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass

import numpy as np
from astropy.io import fits
from astropy.io.votable import parse as parse_votable
from astropy.time import Time

from .. import cache
from ..config_loader import Release, releases
from ..domain import flags as F
from ..domain.wavelength import celestial_wcs, wave_wcs, wavelength_at
from ..http import UpstreamError, http, raise_for_upstream

log = logging.getLogger("skytracker.spherex")
SIA_URL = "https://irsa.ipac.caltech.edu/SIA"
DETECTOR_PIXELS = 2040
VISIT_GAP_DAYS = 30
Progress = Callable[[str, dict], Awaitable[None]]


@dataclass
class SpherexImage:
    image_id: str  # "<release>:<obs_id>:D<det>"
    release: str
    collection: str
    obs_id: str
    detector: int
    t_start_mjd: float
    t_end_mjd: float
    date_obs: str  # ISO, UTC
    em_min_um: float
    em_max_um: float
    fits_url: str
    s3_key: str | None


def target_key(ra: float, dec: float) -> str:
    return f"{ra:.5f}_{dec:+.5f}"


def _detector_of(bandname: str) -> int:
    # "SPHEREx-D4" -> 4
    try:
        return int(str(bandname).rsplit("D", 1)[-1])
    except ValueError:
        return 0


async def _sia_collection(rel: Release, collection: str, ra: float, dec: float) -> list[SpherexImage]:
    url = f"{SIA_URL}?COLLECTION={collection}&POS=circle+{ra:.6f}+{dec:.6f}+0.0005&RESPONSEFORMAT=VOTable"
    r = await http.get(url, timeout=60)
    raise_for_upstream(r, "irsa")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        table = parse_votable(io.BytesIO(r.content)).get_first_table().to_table(use_names_over_ids=True)
    out = []
    for row in table:
        if str(row["dataproduct_type"]) != "image":
            continue
        det = _detector_of(row["energy_bandpassname"])
        obs_id = str(row["obs_id"])
        s3 = None
        with contextlib.suppress(KeyError, ValueError, TypeError):
            s3 = json.loads(str(row["cloud_access"]))["aws"]["key"]
        t0 = float(row["t_min"])
        out.append(
            SpherexImage(
                image_id=f"{rel.id}:{obs_id}:D{det}",
                release=rel.id,
                collection=collection,
                obs_id=obs_id,
                detector=det,
                t_start_mjd=t0,
                t_end_mjd=float(row["t_max"]),
                date_obs=Time(t0, format="mjd").isot[:19] + "Z",
                em_min_um=round(float(row["em_min"]) * 1e6, 4),
                em_max_um=round(float(row["em_max"]) * 1e6, 4),
                fits_url=str(row["access_url"]),
                s3_key=s3,
            )
        )
    return out


async def coverage(ra: float, dec: float, progress: Progress | None = None) -> list[SpherexImage]:
    """All SPHEREx images (active releases) whose footprint contains (ra, dec)."""
    images: list[SpherexImage] = []
    for rel in releases().active:
        for coll in rel.sia_collections:
            key = f"{coll}_{target_key(ra, dec)}"
            hit = cache.get_json(f"{rel.id}/coverage", key, 24 * 3600)
            if hit is None:
                if progress:
                    await progress("sia_query", {"release": rel.label, "collection": coll})
                found = await _sia_collection(rel, coll, ra, dec)
                cache.put_json(f"{rel.id}/coverage", key, [asdict(i) for i in found])
            else:
                found = [SpherexImage(**d) for d in hit]
            for img in found:
                cache.put_json("_index/images", img.image_id.replace(":", "_"), asdict(img))
            images.extend(found)
            if progress:
                await progress("sia_done", {"release": rel.label, "count": len(found)})
    images.sort(key=lambda i: i.t_start_mjd)
    return images


def cached_coverage_count(ra: float, dec: float) -> int | None:
    """Number of images at (ra, dec) if every active collection is already cached; None otherwise.

    Never queries IRSA (the assistant uses it to mention how many images the open object has)."""
    total = 0
    for rel in releases().active:
        for coll in rel.sia_collections:
            hit = cache.get_json(f"{rel.id}/coverage", f"{coll}_{target_key(ra, dec)}", 24 * 3600)
            if hit is None:
                return None
            total += len(hit)
    return total


def get_image(image_id: str) -> SpherexImage | None:
    d = cache.get_json("_index/images", image_id.replace(":", "_"), None)
    return SpherexImage(**d) if d else None


def group_visits(images: list[SpherexImage]) -> list[dict]:
    """Split the time series wherever there is a gap > VISIT_GAP_DAYS (one visit per survey pass)."""
    visits: list[dict] = []
    for img in sorted(images, key=lambda i: i.t_start_mjd):
        if not visits or img.t_start_mjd - visits[-1]["t_end"] > VISIT_GAP_DAYS:
            visits.append({"t_start": img.t_start_mjd, "t_end": img.t_end_mjd, "images": []})
        v = visits[-1]
        v["t_end"] = max(v["t_end"], img.t_end_mjd)
        v["images"].append(img)
    for n, v in enumerate(visits, 1):
        start = Time(v["t_start"], format="mjd")
        v["index"] = n
        v["label"] = start.strftime("%Y-%m")
        v["start"] = start.isot[:10]
        v["end"] = Time(v["t_end"], format="mjd").isot[:10]
        v["releases"] = sorted({i.release for i in v["images"]})
    return visits


# ---------- wavelength at the target (header range-reads, no full download) ----------


def _parse_primary_and_image_header(raw: bytes) -> tuple[fits.Header, fits.Header]:
    prim = fits.Header.fromstring(raw.decode("latin-1"))
    off = len(prim.tostring())  # padded to 2880
    img = fits.Header.fromstring(raw[off:].decode("latin-1"))
    return prim, img


def _parse_wcs_wave_tail(tail: bytes) -> fits.BinTableHDU:
    i = tail.rfind(b"XTENSION= 'BINTABLE'")
    if i < 0:
        raise ValueError("WCS-WAVE table not found in file tail")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fits.BinTableHDU.fromstring(tail[i:])


def _sample_slot(img: SpherexImage, ra: float, dec: float) -> tuple[str, str]:
    return f"{img.release}/samples", f"{img.obs_id}_D{img.detector}_{target_key(ra, dec)}"


def cached_sample(img: SpherexImage, ra: float, dec: float) -> dict | None:
    """target_sample() only if it is already cached (no request to IRSA)."""
    return cache.get_json(*_sample_slot(img, ra, dec), None)


async def target_sample(img: SpherexImage, ra: float, dec: float) -> dict:
    """Detector position, wavelength and bandwidth of the target in one exposure (cached)."""
    ns, key = _sample_slot(img, ra, dec)
    if (hit := cache.get_json(ns, key, None)) is not None:
        return hit
    head, tail = await asyncio.gather(
        http.get(img.fits_url, headers={"Range": "bytes=0-40319"}, timeout=40),
        http.get(img.fits_url, headers={"Range": "bytes=-17280"}, timeout=40),
    )
    for r in (head, tail):
        if r.status_code not in (200, 206):
            raise_for_upstream(r, "irsa")

    def _compute() -> dict:
        prim, h = _parse_primary_and_image_header(head.content)
        tbl = _parse_wcs_wave_tail(tail.content)
        x, y = celestial_wcs(h).world_to_pixel_values(ra, dec)
        x, y = float(x), float(y)
        on = -0.5 <= x < DETECTOR_PIXELS - 0.5 and -0.5 <= y < DETECTOR_PIXELS - 0.5
        lam, bw = wavelength_at(h, tbl, x, y) if on else (None, None)
        return {
            "image_id": img.image_id,
            "x": round(x, 2),
            "y": round(y, 2),
            "on_detector": on,
            "wavelength_um": None if lam is None else round(lam, 5),
            "bandwidth_um": None if bw is None else round(bw, 5),
            "pipeline_version": str(prim.get("VERSION", "")).strip() or None,
            "sps_epa": h.get("SPS_EPA"),
            "mjd_avg": h.get("MJD-AVG"),
        }

    sample = await asyncio.to_thread(_compute)
    cache.put_json(ns, key, sample)
    return sample


async def index_wavelengths(
    images: list[SpherexImage], ra: float, dec: float, progress: Progress | None = None
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    done = 0

    async def one(img: SpherexImage):
        nonlocal done
        try:
            out[img.image_id] = await target_sample(img, ra, dec)
        except (UpstreamError, ValueError, OSError) as e:
            log.info("sample failed for %s: %s", img.image_id, e)
            out[img.image_id] = {"image_id": img.image_id, "error": getattr(e, "code", "SAMPLE_FAILED")}
        done += 1
        if progress and (done % 4 == 0 or done == len(images)):
            await progress("index", {"done": done, "total": len(images)})

    await asyncio.gather(*(one(i) for i in images))
    return out


# ---------- QR2 -> QR3 flux corrections (rows read with HTTP Range) ----------


async def flux_correction_region(det: int, x0: int, x1: int, y0: int, y1: int) -> np.ndarray | None:
    """Correction factors for original detector pixels [y0:y1+1, x0:x1+1] (0-based), or None."""
    rel = next((r for r in releases().active if r.flux_corrections_url), None)
    if rel is None:
        return None
    url = rel.flux_corrections_url.format(det=det)
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, DETECTOR_PIXELS - 1), min(y1, DETECTOR_PIXELS - 1)
    key = f"D{det}_{y0}_{y1}"
    raw = cache.get_bytes(f"{rel.id}/fluxcorr", key)
    if raw is None:
        head = await http.get(url, headers={"Range": "bytes=0-8639"}, timeout=30)
        if head.status_code not in (200, 206):
            return None
        _prim, h = _parse_primary_and_image_header(head.content)
        offset = len(fits.Header.fromstring(head.content.decode("latin-1")).tostring()) + len(h.tostring())
        row = DETECTOR_PIXELS * 4
        r = await http.get(
            url, headers={"Range": f"bytes={offset + y0 * row}-{offset + (y1 + 1) * row - 1}"}, timeout=60
        )
        if r.status_code not in (200, 206):
            return None
        raw = r.content
        cache.put_bytes(f"{rel.id}/fluxcorr", key, raw)
    rows = np.frombuffer(raw, dtype=">f4").reshape(y1 - y0 + 1, DETECTOR_PIXELS)
    return rows[:, x0 : x1 + 1].astype(np.float64)


# ---------- cutouts ----------


async def fetch_cutout_fits(img: SpherexImage, ra: float, dec: float, size_deg: float) -> bytes:
    ns = f"{img.release}/cutouts"
    key = f"{img.obs_id}_D{img.detector}_{target_key(ra, dec)}_{size_deg:.3f}"
    if (hit := cache.get_bytes(ns, key, ".fits")) is not None:
        return hit
    url = f"{img.fits_url}?center={ra:.6f},{dec:.6f}d&size={size_deg:.4f}"
    r = await http.get(url, timeout=120, retries=4)
    raise_for_upstream(r, "irsa")
    if not r.content.startswith(b"SIMPLE"):
        raise UpstreamError("UPSTREAM_BAD_RESPONSE", "irsa", r.content[:60].decode("latin-1"))
    cache.put_bytes(ns, key, r.content, ".fits")
    return r.content


def _sky_orientation(wcs, ny: int, nx: int) -> dict:
    """Angles (deg, counter-clockwise from +x in image pixel space) of North and East, and pixel scale."""
    cx, cy = (nx - 1) / 2.0, (ny - 1) / 2.0
    ra0, dec0 = (float(v) for v in wcs.pixel_to_world_values(cx, cy))
    d = 1.0 / 60.0  # 1 arcmin
    xn, yn = wcs.world_to_pixel_values(ra0, dec0 + d)
    xe, ye = wcs.world_to_pixel_values(ra0 + d / max(math.cos(math.radians(dec0)), 1e-6), dec0)
    px_per_arcmin = math.hypot(xn - cx, yn - cy)
    return {
        "north_deg": math.degrees(math.atan2(float(yn - cy), float(xn - cx))),
        "east_deg": math.degrees(math.atan2(float(ye - cy), float(xe - cx))),
        "pixel_scale_arcsec": 60.0 / px_per_arcmin if px_per_arcmin else None,
        "center_ra": ra0,
        "center_dec": dec0,
    }


def decode_cutout(raw: bytes, ra: float, dec: float, zodi: str = "sub") -> dict:
    """Arrays (row 0 = bottom, FITS order) + metadata the viewer needs. CPU-bound: call in a thread."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hdul = fits.open(io.BytesIO(raw))
        prim = hdul[0].header
        ih = hdul["IMAGE"].header
        img = hdul["IMAGE"].data.astype(np.float32)
        z = hdul["ZODI"].data.astype(np.float32)
        var = hdul["VARIANCE"].data.astype(np.float32)
        fl = hdul["FLAGS"].data
        schema = F.flag_schema(hdul["FLAGS"].header)
        cwcs = celestial_wcs(ih)
        wwcs = wave_wcs(ih, hdul["WCS-WAVE"])
        ny, nx = img.shape
        yy, xx = np.mgrid[0:ny, 0:nx]
        lam, bw = wwcs.pixel_to_world_values(xx, yy)
        tx, ty = (float(v) for v in cwcs.world_to_pixel_values(ra, dec))
        ix, iy = min(max(round(tx), 0), nx - 1), min(max(round(ty), 0), ny - 1)
        zodi_model = str(hdul["ZODI"].header.get("ZODIMDL", "")).strip() or None

    bad = F.mask_from(fl, schema, F.DISPLAY_MASK) | ~np.isfinite(img)
    data = img - z if zodi == "sub" else img
    orient = _sky_orientation(cwcs, ny, nx)
    lam_gradient = np.gradient(lam)
    return {
        "width": nx,
        "height": ny,
        "data": data,
        "variance": var,
        "bad": bad,
        "lambda_map": lam.astype(np.float32),
        "meta": {
            "unit": "MJy/sr",
            "zodi": zodi,
            "zodi_model": zodi_model,
            "zodi_median": float(np.nanmedian(z)),
            "target_px": [tx, ty],
            "wavelength_um": round(float(lam[iy, ix]), 5),
            "bandwidth_um": round(float(bw[iy, ix]), 5),
            "wavelength_min_um": round(float(np.nanmin(lam)), 5),
            "wavelength_max_um": round(float(np.nanmax(lam)), 5),
            # direction (in pixel space) in which wavelength increases fastest
            "wavelength_gradient_deg": math.degrees(
                math.atan2(float(np.nanmedian(lam_gradient[0])), float(np.nanmedian(lam_gradient[1])))
            ),
            "date_obs": str(ih.get("DATE-OBS", "")),
            "mjd_avg": ih.get("MJD-AVG"),
            "detector": ih.get("DETECTOR"),
            "obs_id": str(ih.get("OBSID", "")),
            "pipeline_version": str(prim.get("VERSION", "")).strip() or None,
            "psf_fwhm_arcsec": ih.get("PSF_FWHM"),
            "omega_median_arcsec2": ih.get("OMEGA_MEDIAN"),
            "sps_epa": ih.get("SPS_EPA"),
            "bad_fraction": round(float(bad.mean()), 4),
            "flag_fractions": F.flag_fractions(fl, schema),
            **orient,
        },
    }
