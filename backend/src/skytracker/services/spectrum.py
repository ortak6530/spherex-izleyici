"""Spectrum of one visit: our own aperture photometry at the target in every exposure (6 detectors x ~17).

Cutouts would cost ~4-5 MB each (the service adds the PSF cube), ~0.5 GB per object. Instead we read
only the rows around the target with HTTP Range (ARCHITECTURE §6.4): the L2 file is uncompressed
(PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI, EPSF, WCS-WAVE), so each HDU's data offset follows from its
header length. Per exposure: 1 header read + 3 x 17 rows (~140 kB each) + 2 small header reads.

Method (shown to the user): 2 px aperture, local background = median of a 4-7 px annulus (this also
removes zodiacal light), FLAGS photometry mask, VARIANCE for the statistical error, +3 % systematic.
Simple aperture photometry: not IRSA's PSF fitting; for extended sources only the light inside the
aperture is measured. Results are cached per exposure and target.
"""

from __future__ import annotations

import asyncio
import logging
import math
import warnings

import numpy as np
from astropy.io import fits

from .. import cache
from ..domain import compare as C
from ..domain import flags as F
from ..http import UpstreamError, http, raise_for_upstream
from ..providers import spherex as S

log = logging.getLogger("skytracker.spectrum")
HALF = 8  # rows/columns read on each side of the target (aperture 2 px + annulus to 7 px)
HEAD_BYTES = 40320  # primary + IMAGE header fit in the first ~23 kB (DATA_SOURCES §4.6)
HDR_BYTES = 40320  # enough for the FLAGS / VARIANCE headers
DEFAULT_OMEGA = 37.82  # arcsec^2, same fallback as the time comparison
METHOD = (
    "Basit açıklık fotometrisi (2 piksel yarıçap, 4–7 piksel halkadan yerel arka plan; zodyak ışığı da "
    "böylece çıkar), FLAGS fotometri maskesi, hata VARIANCE + %3 sistematik. IRSA'nın PSF uydurmalı "
    "aracından farklıdır; genişletilmiş kaynaklarda yalnızca açıklık içindeki ışık ölçülür."
)


class LayoutError(Exception):
    """The file is not laid out as expected (compressed, other extension order...)."""


def _padded(n: int) -> int:
    return math.ceil(n / 2880) * 2880


def _data_bytes(h: fits.Header) -> int:
    """Data area of an HDU: the table/image itself plus the heap (PCOUNT) of a compressed HDU."""
    return abs(int(h["BITPIX"])) // 8 * int(h["NAXIS1"]) * int(h["NAXIS2"]) + int(h.get("PCOUNT", 0) or 0)


def _header(raw: bytes) -> fits.Header:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fits.Header.fromstring(raw.decode("latin-1"))


async def _range(url: str, start: int, length: int) -> bytes:
    r = await http.get(url, headers={"Range": f"bytes={start}-{start + length - 1}"}, timeout=40)
    if r.status_code != 206:
        raise_for_upstream(r, "irsa")
        raise LayoutError(f"Range not honoured (HTTP {r.status_code})")
    return r.content


def _array(raw: bytes, h: fits.Header, nrows: int, nx: int) -> np.ndarray:
    bitpix = int(h["BITPIX"])
    dtype = {-32: ">f4", -64: ">f8", 32: ">i4", 16: ">i2"}.get(bitpix)
    if dtype is None:
        raise LayoutError(f"BITPIX {bitpix}")
    a = np.frombuffer(raw, dtype=dtype).reshape(nrows, nx).astype(np.float64 if bitpix < 0 else np.int64)
    bzero, bscale = h.get("BZERO", 0), h.get("BSCALE", 1)
    if bitpix > 0 and bzero:  # e.g. uint32 stored as int32 + BZERO
        a = a * int(bscale) + int(bzero)
    return a


async def _rows(url: str, data_off: int, h: fits.Header, y0: int, y1: int) -> np.ndarray:
    nx = int(h["NAXIS1"])
    bpp = abs(int(h["BITPIX"])) // 8
    raw = await _range(url, data_off + y0 * nx * bpp, (y1 - y0 + 1) * nx * bpp)
    return _array(raw, h, y1 - y0 + 1, nx)


async def _compressed_rows(url: str, data_off: int, h: fits.Header, y0: int, y1: int) -> np.ndarray:
    """Rows y0..y1 of a tile-compressed image (R7 FLAGS: RICE_1, one tile per row).

    The binary table holds one (count, heap offset) descriptor per tile; the compressed bytes live in
    the heap. Read the descriptors, then the heap span, and decode each tile with astropy's codec."""
    if str(h.get("ZCMPTYPE", "")).strip() != "RICE_1" or int(h.get("ZTILE2", 0)) != 1:
        raise LayoutError(
            f"unsupported compression {h.get('ZCMPTYPE')} / tile {h.get('ZTILE1')}x{h.get('ZTILE2')}"
        )
    try:
        from astropy.io.fits.hdu.compressed._codecs import Rice1
    except ImportError as e:  # astropy moved its codec
        raise LayoutError("RICE decoder not available") from e
    nx = int(h["ZNAXIS1"])
    row_len = int(h["NAXIS1"])  # bytes per table row; first column = 1PB descriptor (2 x int32)
    desc = np.frombuffer(await _range(url, data_off + y0 * row_len, (y1 - y0 + 1) * row_len), dtype=">i4")
    desc = desc.reshape(y1 - y0 + 1, row_len // 4)[:, :2]
    heap = data_off + int(h.get("THEAP", int(h["NAXIS1"]) * int(h["NAXIS2"])))
    lo, hi = int(desc[:, 1].min()), int((desc[:, 1] + desc[:, 0]).max())
    blob = await _range(url, heap + lo, hi - lo)
    params = {str(h.get(f"ZNAME{i}", "")).strip(): h.get(f"ZVAL{i}") for i in (1, 2, 3)}
    codec = Rice1(
        blocksize=int(params.get("BLOCKSIZE", 32)), bytepix=int(params.get("BYTEPIX", 4)), tilesize=nx
    )
    rows = []
    for n, off in desc:
        raw = np.frombuffer(blob, dtype=np.uint8, count=int(n), offset=int(off - lo))
        tile = np.asarray(codec.decode(raw)).astype(np.int64)
        if tile.size != nx:
            raise LayoutError(f"tile has {tile.size} values, expected {nx}")
        rows.append(tile)
    a = np.vstack(rows)
    zzero = h.get("BZERO") or h.get("ZZERO") or 0
    return a + int(zzero) if zzero else a


async def _hdu_header(url: str, off: int, extname: str) -> fits.Header:
    h = _header(await _range(url, off, HDR_BYTES))
    if str(h.get("EXTNAME", "")).strip().upper() != extname:
        raise LayoutError(f"expected {extname}, found {h.get('EXTNAME')}")
    return h


async def aperture_at(img: S.SpherexImage, ra: float, dec: float) -> dict:
    """One spectrum point (cached). status: ok | no_photometry | off_detector | error."""
    ns, key = f"{img.release}/aperture", f"{img.obs_id}_D{img.detector}_{S.target_key(ra, dec)}"
    if (hit := cache.get_json(ns, key, None)) is not None:
        return hit
    base = {
        "image_id": img.image_id,
        "release": img.release,
        "detector": img.detector,
        "date_obs": img.date_obs,
        "fits_url": img.fits_url,
    }
    s = await S.target_sample(img, ra, dec)
    if not s.get("on_detector"):
        out = {**base, "status": "off_detector"}
        cache.put_json(ns, key, out)
        return out
    url = img.fits_url
    prim, ih = S._parse_primary_and_image_header(await _range(url, 0, HEAD_BYTES))  # noqa: SLF001
    if str(ih.get("EXTNAME", "")).strip().upper() != "IMAGE" or int(ih.get("NAXIS", 0)) != 2:
        raise LayoutError("first extension is not an uncompressed IMAGE")
    nx, ny = int(ih["NAXIS1"]), int(ih["NAXIS2"])
    img_off = len(prim.tostring()) + len(ih.tostring())
    fl_hdr_off = img_off + _padded(_data_bytes(ih))
    fh = await _hdu_header(url, fl_hdr_off, "FLAGS")
    fl_off = fl_hdr_off + len(fh.tostring())
    var_hdr_off = fl_off + _padded(_data_bytes(fh))
    vh = await _hdu_header(url, var_hdr_off, "VARIANCE")
    var_off = var_hdr_off + len(vh.tostring())

    x, y = float(s["x"]), float(s["y"])
    y0, y1 = max(0, round(y) - HALF), min(ny - 1, round(y) + HALF)
    flag_rows = _compressed_rows if fh.get("ZIMAGE") else _rows
    if int(vh.get("NAXIS1", 0)) != nx or vh.get("ZIMAGE"):
        raise LayoutError("VARIANCE is not an uncompressed image like IMAGE")
    data, flags, var = await asyncio.gather(
        _rows(url, img_off, ih, y0, y1), flag_rows(url, fl_off, fh, y0, y1), _rows(url, var_off, vh, y0, y1)
    )
    x0, x1 = max(0, round(x) - HALF), min(nx - 1, round(x) + HALF)

    def _measure() -> dict | None:
        d, f, v = data[:, x0 : x1 + 1], flags[:, x0 : x1 + 1], var[:, x0 : x1 + 1]
        bad = F.mask_from(f, F.flag_schema(fh), F.PHOTOMETRY_MASK) | ~np.isfinite(d)
        omega = float(ih.get("OMEGA_MEDIAN") or DEFAULT_OMEGA)
        return C.aperture_flux(d, v, bad, x - x0, y - y0, omega)

    phot = await asyncio.to_thread(_measure)
    out = {
        **base,
        "status": "ok" if phot else "no_photometry",
        "wavelength_um": s.get("wavelength_um"),
        "bandwidth_um": s.get("bandwidth_um"),
        "x": x,
        "y": y,
        "pipeline_version": s.get("pipeline_version"),
        "flux_ujy": phot["flux_ujy"] if phot else None,
        "err_ujy": phot["err_ujy"] if phot else None,
        "masked_in_aperture": phot["masked_in_aperture"] if phot else None,
    }
    cache.put_json(ns, key, out)
    return out


async def visit_spectrum(ra: float, dec: float, visit: int, progress) -> dict:
    images = await S.coverage(ra, dec, progress)
    # `visit` is the visit's "index" (1-based) from /sky/observations
    v = next((x for x in S.group_visits(images) if x["index"] == visit), None)
    if v is None:
        return {"points": [], "visit": None, "counts": {"exposures": 0}, "method": METHOD, "unit": "µJy"}
    imgs = sorted(v["images"], key=lambda i: (i.detector, i.t_start_mjd))
    await progress("spectrum_start", {"total": len(imgs), "label": v["label"]})
    done = 0

    async def one(img: S.SpherexImage) -> dict:
        nonlocal done
        try:
            p = await aperture_at(img, ra, dec)
        except (UpstreamError, LayoutError, OSError, ValueError, KeyError) as e:
            log.info("spectrum point failed for %s: %s", img.image_id, e)
            p = {
                "image_id": img.image_id,
                "detector": img.detector,
                "release": img.release,
                "status": "error",
            }
        done += 1
        if done % 5 == 0 or done == len(imgs):
            await progress("spectrum", {"done": done, "total": len(imgs)})
        return p

    points = await asyncio.gather(*(one(i) for i in imgs))
    ok = [p for p in points if p["status"] == "ok"]
    ok.sort(key=lambda p: p["wavelength_um"] or 0)
    return {
        "visit": {"index": v["index"], "label": v["label"], "start": v["start"], "end": v["end"]},
        "points": ok,
        "counts": {
            "exposures": len(points),
            "ok": len(ok),
            "no_photometry": sum(p["status"] == "no_photometry" for p in points),
            "off_detector": sum(p["status"] == "off_detector" for p in points),
            "error": sum(p["status"] == "error" for p in points),
        },
        "method": METHOD,
        "unit": "µJy",
    }
