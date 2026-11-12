"""Two-epoch comparison of the same sky position (Dönem A vs Dönem B).

Pipeline (decisions S2-S5 in docs/DECISIONS.md):
  1. cutouts A and B (same size), IMAGE - ZODI by default
  2. cross-family pair (QR2/R6 vs QR3/R7): multiply the R6 image by l3_flux_corrections
  3. local background per epoch (sigma-clipped, non-source pixels); none if the field is all source
  4. B resampled onto A's sky grid (bilinear), optional relative normalisation k (field pixels, target
     core excluded)
  5. difference + significance map, centroid shift (each epoch on its own grid), aperture photometry
  6. warning codes; the full result is stored in the `comparison` table
"""

from __future__ import annotations

import asyncio
import io
import math
import secrets
import warnings
from dataclasses import dataclass

import numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.wcs.utils import proj_plane_pixel_scales

from ..config_loader import releases
from ..domain import compare as C
from ..domain import flags as F
from ..domain.astrometry import propagate
from ..domain.wavelength import celestial_wcs, wave_wcs
from ..jobs import JobError
from ..providers import spherex as S


def proj_plane_pixel_area_matrix(wcs) -> np.ndarray:
    """2x2 diagonal of per-axis pixel scales (deg), unitless; works across astropy versions."""
    s = np.asarray(proj_plane_pixel_scales(wcs.celestial), dtype=float)
    return np.diag(s)


@dataclass
class Epoch:
    img: S.SpherexImage
    data: np.ndarray
    var: np.ndarray
    bad: np.ndarray
    bg_usable: np.ndarray
    phot_bad: np.ndarray
    wcs: object
    lam: float
    bw: float
    tx: float
    ty: float
    header: fits.Header
    version: str | None
    mjd: float
    omega: float
    zodi_median: float
    pixel_scale: float


def _family(release_id: str) -> str:
    r = releases().get(release_id)
    return r.calib_family if r else "?"


def _parse(img: S.SpherexImage, raw: bytes, ra: float, dec: float, zodi: str) -> Epoch:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        h = fits.open(io.BytesIO(raw))
        ih = h["IMAGE"].header
        data = h["IMAGE"].data.astype(np.float64)
        z = h["ZODI"].data.astype(np.float64)
        var = h["VARIANCE"].data.astype(np.float64)
        fl = h["FLAGS"].data
        schema = F.flag_schema(h["FLAGS"].header)
        cw = celestial_wcs(ih)
        ww = wave_wcs(ih, h["WCS-WAVE"])
        tx, ty = (float(v) for v in cw.world_to_pixel_values(ra, dec))
        lam, bw = (float(v) for v in ww.pixel_to_world_values(tx, ty))
        version = str(h[0].header.get("VERSION", "")).strip() or None
    if zodi == "sub":
        data = data - z
    bad = F.mask_from(fl, schema, F.DISPLAY_MASK) | ~np.isfinite(data)
    return Epoch(
        img=img,
        data=data,
        var=var,
        bad=bad,
        bg_usable=~(F.mask_from(fl, schema, F.BACKGROUND_MASK) | bad),
        phot_bad=F.mask_from(fl, schema, F.PHOTOMETRY_MASK) | ~np.isfinite(data),
        wcs=cw,
        lam=lam,
        bw=bw,
        tx=tx,
        ty=ty,
        header=ih,
        version=version,
        mjd=float(ih.get("MJD-AVG") or img.t_start_mjd),
        omega=float(ih.get("OMEGA_MEDIAN") or 37.82),
        zodi_median=float(np.nanmedian(z)),
        pixel_scale=float(np.sqrt(abs(np.linalg.det(proj_plane_pixel_area_matrix(cw)))) * 3600),
    )


async def _apply_flux_correction(e: Epoch) -> bool:
    """Multiply an R6 (QR2) cutout by the per-pixel QR3 correction for its detector region."""
    ny, nx = e.data.shape
    # cutout pixel (0-based) -> original detector pixel (0-based): x_orig = 1 + x_cut - CRPIX1A
    dx = 1 - float(e.header["CRPIX1A"])
    dy = 1 - float(e.header["CRPIX2A"])
    x0, y0 = round(dx), round(dy)
    corr = await S.flux_correction_region(e.img.detector, x0, x0 + nx - 1, y0, y0 + ny - 1)
    if corr is None or corr.shape != e.data.shape:
        return False
    e.data = e.data * corr
    e.var = e.var * corr**2
    return True


def _b64(a: np.ndarray) -> str:
    import base64

    return base64.b64encode(np.ascontiguousarray(a, dtype="<f4").tobytes()).decode("ascii")


def _sep_arcsec(ra1, dec1, ra2, dec2) -> tuple[float, float]:
    """Angular separation (arcsec) and position angle (deg, east of north) from 1 to 2."""
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    dra = r2 - r1
    sep = math.acos(min(1.0, math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(dra)))
    pa = math.degrees(math.atan2(math.sin(dra), math.cos(d1) * math.tan(d2) - math.sin(d1) * math.cos(dra)))
    return math.degrees(sep) * 3600, pa % 360


async def compare_time(
    image_a: str,
    image_b: str,
    ra: float,
    dec: float,
    size: float,
    zodi: str,
    normalize: bool,
    proper_motion: dict | None,
    progress,
) -> dict:
    ia, ib = S.get_image(image_a), S.get_image(image_b)
    if ia is None or ib is None:
        raise JobError("UNKNOWN_IMAGE")
    if ia.image_id == ib.image_id:
        raise JobError("SAME_IMAGE")
    await progress("cutouts", {"a": ia.image_id, "b": ib.image_id})
    # Both cutouts share one centre (the search-epoch position) so their fields overlap; the target
    # itself is looked for at its own position on each date (proper motion, if known)
    pos_a, pos_b = (ra, dec), (ra, dec)
    pm = proper_motion or {}
    if pm.get("ra_j2000") is not None and (pm.get("pmra_mas_yr") or pm.get("pmdec_mas_yr")):
        pos_a = propagate(
            pm["ra_j2000"], pm["dec_j2000"], pm.get("pmra_mas_yr"), pm.get("pmdec_mas_yr"), ia.t_start_mjd
        )
        pos_b = propagate(
            pm["ra_j2000"], pm["dec_j2000"], pm.get("pmra_mas_yr"), pm.get("pmdec_mas_yr"), ib.t_start_mjd
        )
    raw_a, raw_b = await asyncio.gather(
        S.fetch_cutout_fits(ia, ra, dec, size), S.fetch_cutout_fits(ib, ra, dec, size)
    )
    ea, eb = await asyncio.gather(
        asyncio.to_thread(_parse, ia, raw_a, *pos_a, zodi), asyncio.to_thread(_parse, ib, raw_b, *pos_b, zodi)
    )
    warn: list[dict] = []
    if pos_a != (ra, dec):
        warn.append({"code": "PROPER_MOTION_APPLIED"})

    # --- channel match (decision S5)
    ch = C.channel_match(ea.lam, eb.lam, ea.bw, eb.bw)
    if ch["status"] == "reject":
        # Decision S5: more than one bandwidth apart -> not the same channel, no comparison
        raise JobError("CHANNEL_REJECT", delta_um=ch["delta_um"], ratio=ch["ratio"])
    if ch["status"] == "warn":
        warn.append({"code": "CHANNEL_WARN", **ch})

    # --- release / calibration family (decision S2)
    fam_a, fam_b = _family(ia.release), _family(ib.release)
    flux_corrected = None
    if fam_a != fam_b:
        await progress("flux_correction", {})
        older = ea if fam_a == "R6" else eb
        ok = await _apply_flux_correction(older)
        flux_corrected = older.img.image_id if ok else None
        warn.append({"code": "CROSS_RELEASE", "a": ia.release, "b": ib.release, "flux_corrected": ok})
    elif ea.version != eb.version:
        warn.append({"code": "PIPELINE_DIFFERS", "a": ea.version, "b": eb.version})

    await progress("analysis", {})

    def _analyse() -> dict:
        # --- background per epoch
        bga, noise_a = C.robust_background(ea.data, ea.bg_usable)
        bgb, noise_b = C.robust_background(eb.data, eb.bg_usable)
        if bga is None or bgb is None:
            warn.append({"code": "NO_BACKGROUND"})
        a = ea.data - (bga or 0.0)
        b_native = eb.data - (bgb or 0.0)

        # --- B onto A's grid
        ny, nx = a.shape
        yy, xx = np.mgrid[0:ny, 0:nx]
        wra, wdec = ea.wcs.pixel_to_world_values(xx, yy)
        bx, by = eb.wcs.world_to_pixel_values(wra, wdec)
        b = C.bilinear_sample(b_native, eb.bad, np.asarray(bx, float), np.asarray(by, float))
        bvar = C.bilinear_sample(eb.var, eb.bad, np.asarray(bx, float), np.asarray(by, float))
        a = np.where(ea.bad, np.nan, a)
        overlap = float((np.isfinite(a) & np.isfinite(b)).mean())

        core = C.disk_mask(a.shape, ea.tx, ea.ty, 4)
        k = C.relative_scale(a, b, core) if normalize else None
        if normalize and k is None:
            warn.append({"code": "NORMALIZATION_UNRELIABLE"})
        scale = k if k else 1.0
        bs = b * scale
        diff = bs - a
        sigma = diff / np.sqrt(np.where(ea.bad, np.nan, ea.var) + (scale**2) * bvar)

        # --- target: centroid shift (native grids) and aperture photometry
        ca = C.centroid(ea.data, ea.phot_bad, ea.tx, ea.ty, 3.0, bga or 0.0)
        cb = C.centroid(eb.data, eb.phot_bad, eb.tx, eb.ty, 3.0, bgb or 0.0)
        shift = None
        if ca and cb:
            ra_a, dec_a = (float(v) for v in ea.wcs.pixel_to_world_values(*ca))
            ra_b, dec_b = (float(v) for v in eb.wcs.pixel_to_world_values(*cb))
            sep, pa = _sep_arcsec(ra_a, dec_a, ra_b, dec_b)
            shift = {
                "arcsec": sep,
                "px": sep / ea.pixel_scale,
                "pa_deg": pa,
                "a_centroid": [ra_a, dec_a],
                "b_centroid": [ra_b, dec_b],
            }
        fa = C.aperture_flux(ea.data, ea.var, ea.phot_bad, *(ca or (ea.tx, ea.ty)), ea.omega)
        fb = C.aperture_flux(eb.data, eb.var, eb.phot_bad, *(cb or (eb.tx, eb.ty)), eb.omega)
        for f, e, tag in ((fa, ea, "a"), (fb, eb, "b")):
            if f is None:
                core_px = C.disk_mask(e.data.shape, e.tx, e.ty, 2.0)
                nan_core = int((core_px & ~np.isfinite(e.data)).sum())
                warn.append(
                    {"code": "SATURATED_OR_MASKED_CORE" if nan_core else "NO_PHOTOMETRY", "epoch": tag}
                )
        change = C.percent_change(fa, fb)
        change_norm = None
        if change and k:
            fbn = dict(fb, flux_ujy=fb["flux_ujy"] * k, err_ujy=fb["err_ujy"] * k)
            change_norm = C.percent_change(fa, fbn)
        if fa and fa["err_ujy"] and fa["flux_ujy"] / fa["err_ujy"] < 5:
            warn.append({"code": "LOW_SNR", "snr": fa["flux_ujy"] / fa["err_ujy"]})
        for e, tag in ((ea, "a"), (eb, "b")):
            frac = float(e.bad.mean())
            if frac > 0.10:
                warn.append({"code": "HIGH_MASK_FRACTION", "epoch": tag, "fraction": frac})
            lines = C.nearby_lines(e.lam, e.bw)
            if lines:
                warn.append({"code": "ATMOSPHERIC_LINE", "epoch": tag, "lines": lines})
            if not (2 <= e.tx < e.data.shape[1] - 2 and 2 <= e.ty < e.data.shape[0] - 2):
                warn.append({"code": "TARGET_NEAR_EDGE", "epoch": tag})
        dt_days = eb.mjd - ea.mjd
        expected = None
        if proper_motion and proper_motion.get("pmra_mas_yr") is not None:
            pm = math.hypot(proper_motion["pmra_mas_yr"], proper_motion.get("pmdec_mas_yr") or 0.0)
            exp_arcsec = pm / 1000.0 * abs(dt_days) / 365.25
            expected = {
                "arcsec": exp_arcsec,
                "px": exp_arcsec / ea.pixel_scale,
                "pm_mas_yr": pm,
                "source": "SIMBAD öz hareket",
            }

        stats = C.difference_stats(diff, sigma)
        if stats.get("n"):
            mx, my = stats["max_px"]
            mra, mdec = (float(v) for v in ea.wcs.pixel_to_world_values(mx, my))
            stats["max_radec"] = [mra, mdec]
        fin = np.isfinite(a) & np.isfinite(bs)
        both = np.concatenate([a[fin], bs[fin]]) if fin.any() else np.array([0.0, 1.0])
        return {
            "width": nx,
            "height": ny,
            "a_b64": _b64(a),
            "b_b64": _b64(bs),
            "diff_b64": _b64(diff),
            "sigma_b64": _b64(sigma),
            "shared_limits": [float(np.percentile(both, 0.5)), float(np.percentile(both, 99.5))],
            "diff_limit": float(np.nanpercentile(np.abs(diff), 99)) if np.isfinite(diff).any() else 1.0,
            "background": {"a": bga, "b": bgb, "noise_a": noise_a, "noise_b": noise_b},
            "normalization": {"enabled": normalize, "factor": k},
            "overlap_fraction": overlap,
            "shift": shift,
            "expected_shift": expected,
            "photometry": {"a": fa, "b": fb, "change": change, "change_normalized": change_norm},
            "difference": stats,
            "dt_days": dt_days,
        }

    analysis = await asyncio.to_thread(_analyse)

    def epoch_meta(e: Epoch) -> dict:
        return {
            "image_id": e.img.image_id,
            "release": e.img.release,
            "calib_family": _family(e.img.release),
            "obs_id": e.img.obs_id,
            "detector": e.img.detector,
            "date_obs": Time(e.mjd, format="mjd").isot[:19] + "Z",
            "wavelength_um": e.lam,
            "bandwidth_um": e.bw,
            "pipeline_version": e.version,
            "fits_url": e.img.fits_url,
            "zodi_median": e.zodi_median,
            "bad_fraction": float(e.bad.mean()),
            "target_px": [e.tx, e.ty],
            "pixel_scale_arcsec": e.pixel_scale,
        }

    # Display geometry (N/E arrows, scale bar) comes from A's grid, which both images now share
    orient = S._sky_orientation(ea.wcs, *ea.data.shape)  # noqa: SLF001 - shared helper
    return {
        "id": secrets.token_hex(8),
        "kind": "time",
        "target": {"ra": ra, "dec": dec},
        "size_deg": size,
        "zodi": zodi,
        "a": epoch_meta(ea),
        "b": epoch_meta(eb),
        "channel": ch,
        "flux_corrected_image": flux_corrected,
        "warnings": warn,
        "orientation": orient,
        **analysis,
    }
