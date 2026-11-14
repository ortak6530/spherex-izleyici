"""SPHEREx observations around a target and cutouts. Slow steps run as jobs with WS progress."""

from __future__ import annotations

import asyncio
import base64
import math

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ... import jobs
from ...config_loader import releases
from ...events import log_action
from ...providers import spherex as S
from ...security import TokenBucket

router = APIRouter(prefix="/sky", tags=["sky"])
_limiter = TokenBucket(rate_per_min=20, burst=8)
CUTOUT_SIZES = (0.05, 0.1, 0.25, 0.5)
CHANNELS_PER_DETECTOR = 17


def _guard(request: Request) -> None:
    if not _limiter.allow(request.state.session_id):
        raise HTTPException(429, {"code": "RATE_LIMITED"})


class ObservationsRequest(BaseModel):
    ra: float = Field(ge=0, lt=360)
    dec: float = Field(ge=-90, le=90)
    detector: int = Field(default=2, ge=1, le=6)
    object_key: str | None = Field(default=None, max_length=120)


def approx_channel(lam: float, em_min: float, em_max: float) -> int | None:
    """LVF channels are ~equally spaced in log(lambda) (constant R); 1..17 within the detector."""
    if not (lam and em_min and em_max and em_max > em_min):
        return None
    f = math.log(lam / em_min) / math.log(em_max / em_min)
    return int(min(max(math.floor(f * CHANNELS_PER_DETECTOR) + 1, 1), CHANNELS_PER_DETECTOR))


def release_meta() -> dict:
    return {
        r.id: {"label": r.label, "calib_family": r.calib_family, "show_with_warning": r.show_with_warning}
        for r in releases().release
    }


@router.post("/observations")
async def observations(req: ObservationsRequest, request: Request) -> dict:
    """Start a job: SIA2 coverage (all active releases) + wavelength-at-target for one detector."""
    _guard(request)
    log_action(request, "observations", object_key=req.object_key, payload={"detector": req.detector})

    async def run(progress):
        images = await S.coverage(req.ra, req.dec, progress)
        if not images:
            return {
                "ra": req.ra,
                "dec": req.dec,
                "detector": req.detector,
                "visits": [],
                "no_coverage": True,
                "releases": release_meta(),
            }
        visits = S.group_visits(images)
        chosen = [i for i in images if i.detector == req.detector]
        await progress("index_start", {"total": len(chosen), "detector": req.detector})
        samples = await S.index_wavelengths(chosen, req.ra, req.dec, progress)
        out_visits = []
        for v in visits:
            per_det: dict[int, int] = {}
            for i in v["images"]:
                per_det[i.detector] = per_det.get(i.detector, 0) + 1
            rows = []
            for i in v["images"]:
                if i.detector != req.detector:
                    continue
                s = samples.get(i.image_id, {})
                lam = s.get("wavelength_um")
                rows.append(
                    {
                        "image_id": i.image_id,
                        "release": i.release,
                        "obs_id": i.obs_id,
                        "detector": i.detector,
                        "date_obs": i.date_obs,
                        "mjd": i.t_start_mjd,
                        "fits_url": i.fits_url,
                        "wavelength_um": lam,
                        "bandwidth_um": s.get("bandwidth_um"),
                        "channel": approx_channel(lam, i.em_min_um, i.em_max_um) if lam else None,
                        "on_detector": s.get("on_detector"),
                        "x": s.get("x"),
                        "y": s.get("y"),
                        "pipeline_version": s.get("pipeline_version"),
                        "error": s.get("error"),
                    }
                )
            rows.sort(key=lambda r: (r["wavelength_um"] is None, r["wavelength_um"] or 0))
            out_visits.append(
                {
                    "index": v["index"],
                    "label": v["label"],
                    "start": v["start"],
                    "end": v["end"],
                    "releases": v["releases"],
                    "images_per_detector": per_det,
                    "images": rows,
                }
            )
        return {
            "ra": req.ra,
            "dec": req.dec,
            "detector": req.detector,
            "visits": out_visits,
            "total_images": len(images),
            "no_coverage": False,
            "releases": release_meta(),
        }

    return {"job_id": jobs.start("observations", run)}


class SpectrumRequest(BaseModel):
    ra: float = Field(ge=0, lt=360)
    dec: float = Field(ge=-90, le=90)
    visit: int = Field(ge=1, le=100)  # the visit's "index" from /sky/observations
    object_key: str | None = Field(default=None, max_length=120)


@router.post("/spectrum")
async def spectrum(req: SpectrumRequest, request: Request) -> dict:
    """Start a job: aperture photometry at the target in every exposure of one visit (all 6 detectors)."""
    _guard(request)
    log_action(request, "spectrum", object_key=req.object_key, payload={"visit": req.visit})

    async def run(progress):
        from ...services.spectrum import visit_spectrum

        return await visit_spectrum(req.ra, req.dec, req.visit, progress)

    return {"job_id": jobs.start("spectrum", run)}


class CutoutRequest(BaseModel):
    image_id: str = Field(max_length=80, pattern=r"^[a-z0-9]+:[0-9A-Za-z_]+:D[1-6]$")
    ra: float = Field(ge=0, lt=360)
    dec: float = Field(ge=-90, le=90)
    size_deg: float = 0.1
    zodi: str = Field(default="sub", pattern="^(sub|raw)$")


def _b64(a: np.ndarray, dtype) -> str:
    # row 0 = bottom of the image (FITS order); the client flips when drawing
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode("ascii")


async def build_cutout(img: S.SpherexImage, ra: float, dec: float, size: float, zodi: str) -> dict:
    raw = await S.fetch_cutout_fits(img, ra, dec, size)
    c = await asyncio.to_thread(S.decode_cutout, raw, ra, dec, zodi)
    data = np.where(c["bad"], np.nan, c["data"]).astype(np.float32)
    finite = data[np.isfinite(data)]
    return {
        "image_id": img.image_id,
        "release": img.release,
        "fits_url": img.fits_url,
        "size_deg": size,
        "width": c["width"],
        "height": c["height"],
        "data_b64": _b64(data, "<f4"),
        "lambda_b64": _b64(c["lambda_map"], "<f4"),
        "stats": {
            "p01": float(np.percentile(finite, 1)) if finite.size else None,
            "p50": float(np.percentile(finite, 50)) if finite.size else None,
            "p995": float(np.percentile(finite, 99.5)) if finite.size else None,
        },
        "meta": c["meta"],
    }


@router.post("/cutout")
async def cutout(req: CutoutRequest, request: Request) -> dict:
    _guard(request)
    if req.size_deg not in CUTOUT_SIZES:
        raise HTTPException(400, {"code": "INVALID_SIZE", "allowed": CUTOUT_SIZES})
    img = S.get_image(req.image_id)
    if img is None:
        raise HTTPException(404, {"code": "UNKNOWN_IMAGE"})
    log_action(
        request, "cutout", release_id=img.release, payload={"image_id": req.image_id, "size": req.size_deg}
    )

    async def run(progress):
        await progress("cutout_request", {"image_id": img.image_id})
        return await build_cutout(img, req.ra, req.dec, req.size_deg, req.zodi)

    return {"job_id": jobs.start("cutout", run)}
