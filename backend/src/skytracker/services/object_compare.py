"""Object vs object comparison (scope item 2 in docs/DECISIONS.md).

Both objects are shown in the same wavelength channel, with the same cutout size and on a common
brightness scale. A table puts SIMBAD facts next to what SPHEREx measured in that channel.
"""

from __future__ import annotations

import asyncio
import math
import secrets

import numpy as np

from ..domain import compare as C
from ..domain.astrometry import propagate
from ..http import UpstreamError
from ..jobs import JobError
from ..providers import simbad
from ..providers import spherex as S
from .time_compare import _b64, _family, _parse

AB_ZERO_POINT_JY = 3631.0


async def _info(main_id: str | None) -> dict | None:
    if not main_id:
        return None
    try:
        return await simbad.object_basic(main_id)
    except UpstreamError:
        return None


async def _best_exposure(
    ra: float, dec: float, detector: int, lam: float, family: str | None, progress, tag: str
):
    """Exposure whose wavelength at the target is closest to lam (same calibration family first)."""
    images = await S.coverage(ra, dec)
    chosen = [i for i in images if i.detector == detector]
    if not chosen:
        raise JobError("NO_COVERAGE", object=tag)
    await progress("index_start", {"total": len(chosen), "detector": detector, "object": tag})
    samples = await S.index_wavelengths(chosen, ra, dec, progress)

    def score(img: S.SpherexImage):
        s = samples.get(img.image_id) or {}
        if not s.get("wavelength_um") or not s.get("on_detector"):
            return (2, math.inf)
        same_family = 0 if (family is None or _family(img.release) == family) else 1
        return (same_family, abs(s["wavelength_um"] - lam))

    best = min(chosen, key=score)
    if score(best)[1] == math.inf:
        raise JobError("NO_COVERAGE", object=tag)
    return best


def _ab_mag(flux_ujy: float | None) -> float | None:
    if flux_ujy is None or flux_ujy <= 0:
        return None
    return -2.5 * math.log10(flux_ujy * 1e-6 / AB_ZERO_POINT_JY)


def _distance(info: dict | None) -> dict | None:
    if not info:
        return None
    plx, err = info.get("plx_mas"), info.get("plx_err_mas")
    if not plx or plx <= 0 or (err and plx / err < 5):
        return None
    return {"pc": 1000.0 / plx, "source": "SIMBAD paralaks"}


async def compare_objects(a: dict, b: dict, image_a: str, size: float, zodi: str, progress) -> dict:
    """a/b: {name, main_id, ra, dec, key}. image_a: the exposure already chosen for object A."""
    ia = S.get_image(image_a)
    if ia is None:
        raise JobError("UNKNOWN_IMAGE")
    info_a, info_b = await asyncio.gather(_info(a.get("main_id")), _info(b.get("main_id")))
    sample_a = await S.target_sample(ia, a["ra"], a["dec"])
    if not sample_a.get("wavelength_um"):
        raise JobError("NO_COVERAGE", object="a")
    lam = sample_a["wavelength_um"]
    ib = await _best_exposure(b["ra"], b["dec"], ia.detector, lam, _family(ia.release), progress, "b")

    await progress("cutouts", {"a": ia.image_id, "b": ib.image_id})
    raw_a, raw_b = await asyncio.gather(
        S.fetch_cutout_fits(ia, a["ra"], a["dec"], size), S.fetch_cutout_fits(ib, b["ra"], b["dec"], size)
    )

    def epoch_pos(obj: dict, info: dict | None, mjd: float) -> tuple[float, float]:
        if info and info.get("ra") is not None and (info.get("pmra_mas_yr") or info.get("pmdec_mas_yr")):
            return propagate(info["ra"], info["dec"], info.get("pmra_mas_yr"), info.get("pmdec_mas_yr"), mjd)
        return obj["ra"], obj["dec"]

    pa = epoch_pos(a, info_a, ia.t_start_mjd)
    pb = epoch_pos(b, info_b, ib.t_start_mjd)
    ea, eb = await asyncio.gather(
        asyncio.to_thread(_parse, ia, raw_a, *pa, zodi), asyncio.to_thread(_parse, ib, raw_b, *pb, zodi)
    )

    warn: list[dict] = []
    ch = C.channel_match(ea.lam, eb.lam, ea.bw, eb.bw)
    if ch["status"] == "reject":
        raise JobError("CHANNEL_REJECT", delta_um=ch["delta_um"], ratio=ch["ratio"])
    if ch["status"] == "warn":
        warn.append({"code": "CHANNEL_WARN", **ch})
    if _family(ia.release) != _family(ib.release):
        warn.append({"code": "CROSS_RELEASE", "a": ia.release, "b": ib.release, "flux_corrected": False})
    ta, tb = (info_a or {}).get("otype"), (info_b or {}).get("otype")
    if ta and tb and ta != tb:
        warn.append(
            {
                "code": "DIFFERENT_TYPES",
                "a": (info_a or {}).get("otype_desc") or ta,
                "b": (info_b or {}).get("otype_desc") or tb,
            }
        )

    def _analyse() -> dict:
        out = {}
        arrays = {}
        for tag, e in (("a", ea), ("b", eb)):
            bg, _noise = C.robust_background(e.data, e.bg_usable)
            img = np.where(e.bad, np.nan, e.data - (bg or 0.0))
            arrays[tag] = img
            phot = C.aperture_flux(e.data, e.var, e.phot_bad, e.tx, e.ty, e.omega)
            if phot is None:
                warn.append({"code": "NO_PHOTOMETRY", "epoch": tag})
            fin = img[np.isfinite(img)]
            out[tag] = {
                "image_id": e.img.image_id,
                "release": e.img.release,
                "obs_id": e.img.obs_id,
                "detector": e.img.detector,
                "date_obs": e.img.date_obs,
                "fits_url": e.img.fits_url,
                "wavelength_um": e.lam,
                "bandwidth_um": e.bw,
                "pipeline_version": e.version,
                "target_px": [e.tx, e.ty],
                "pixel_scale_arcsec": e.pixel_scale,
                "orientation": S._sky_orientation(e.wcs, *e.data.shape),  # noqa: SLF001
                "background_mjy_sr": bg,
                "photometry": phot,
                "ab_mag": _ab_mag(phot and phot["flux_ujy"]),
                "own_limits": [float(np.percentile(fin, 0.5)), float(np.percentile(fin, 99.5))]
                if fin.size
                else [0.0, 1.0],
                "width": img.shape[1],
                "height": img.shape[0],
                "data_b64": _b64(img),
            }
        both = np.concatenate([arrays["a"][np.isfinite(arrays["a"])], arrays["b"][np.isfinite(arrays["b"])]])
        shared = (
            [float(np.percentile(both, 0.5)), float(np.percentile(both, 99.5))] if both.size else [0.0, 1.0]
        )
        fa, fb = out["a"]["photometry"], out["b"]["photometry"]
        ratio = fb["flux_ujy"] / fa["flux_ujy"] if fa and fb and fa["flux_ujy"] > 0 else None
        return {"a_view": out["a"], "b_view": out["b"], "shared_limits": shared, "flux_ratio_b_over_a": ratio}

    analysis = await asyncio.to_thread(_analyse)

    def facts(obj: dict, info: dict | None) -> dict:
        i = info or {}
        return {
            "name": obj.get("name"),
            "main_id": obj.get("main_id"),
            "otype": i.get("otype"),
            "otype_desc": i.get("otype_desc"),
            "sp_type": i.get("sp_type"),
            "distance": _distance(info),
            "mags": i.get("mags") or {},
            "pmra_mas_yr": i.get("pmra_mas_yr"),
            "pmdec_mas_yr": i.get("pmdec_mas_yr"),
            "source": "SIMBAD (CDS)" if info else None,
        }

    return {
        "id": secrets.token_hex(8),
        "kind": "object",
        "size_deg": size,
        "zodi": zodi,
        "channel": ch,
        "objects": {"a": facts(a, info_a), "b": facts(b, info_b)},
        "same_type": bool(ta and tb and ta == tb),
        "warnings": warn,
        **analysis,
    }
