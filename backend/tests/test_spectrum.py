"""Spectrum points from HTTP Range reads: synthetic L2 file with the real R7 layout (uncompressed IMAGE
and VARIANCE, RICE_1 tile-compressed FLAGS), read through a fake server that honours Range."""

import asyncio
import io

import numpy as np
from astropy.io import fits

from skytracker.domain import compare as C
from skytracker.domain import flags as F
from skytracker.providers import spherex as S
from skytracker.services import spectrum as SP

N = 64
TX, TY = 30.3, 31.7


def l2_file() -> tuple[bytes, dict]:
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:N, 0:N]
    img = (2.0 + 0.01 * xx + 50 * np.exp(-((xx - TX) ** 2 + (yy - TY) ** 2) / 1.5)).astype(np.float32)
    img += rng.normal(0, 0.05, img.shape).astype(np.float32)
    var = np.full((N, N), 0.0025, np.float32)
    flags = np.zeros((N, N), np.int32)
    flags[32, 31] = 1 << 5  # HOT pixel inside the aperture -> photometry mask
    flags[10, 10] = 1 << 2  # far away, other flag
    prim = fits.PrimaryHDU()
    prim.header["VERSION"] = "7.0.5"
    ih = fits.ImageHDU(img, name="IMAGE")
    ih.header["OMEGA_MEDIAN"] = 38.0
    fh = fits.CompImageHDU(flags, name="FLAGS", compression_type="RICE_1", tile_shape=(1, N))
    fh.header["MSKN0005"] = "HOT"
    fh.header["MSKN0002"] = "SOURCE"
    hdul = fits.HDUList(
        [prim, ih, fh, fits.ImageHDU(var, name="VARIANCE"), fits.ImageHDU(img * 0, name="ZODI")]
    )
    buf = io.BytesIO()
    hdul.writeto(buf)
    return buf.getvalue(), {"img": img.astype(float), "var": var.astype(float), "flags": flags}


class Resp:
    def __init__(self, status, content):
        self.status_code, self.content, self.text, self.headers = status, content, "", {}


def install(monkeypatch, raw: bytes, calls: list):
    async def fake_get(url, headers=None, **_):
        a, b = headers["Range"].removeprefix("bytes=").split("-")
        calls.append(int(b) - int(a) + 1)
        return Resp(206, raw[int(a) : int(b) + 1])

    async def fake_sample(img, ra, dec):
        return {"on_detector": True, "x": TX, "y": TY, "wavelength_um": 2.0, "bandwidth_um": 0.04}

    monkeypatch.setattr(SP.http, "get", fake_get)
    monkeypatch.setattr(SP.S, "target_sample", fake_sample)
    monkeypatch.setattr(SP.cache, "get_json", lambda *a, **k: None)
    monkeypatch.setattr(SP.cache, "put_json", lambda *a, **k: None)


IMG = S.SpherexImage(
    "dr1:o1:D3",
    "dr1",
    "c",
    "o1",
    3,
    60900.0,
    60900.01,
    "2025-08-01T00:00:00Z",
    1.6,
    2.4,
    "https://irsa.ipac.caltech.edu/x.fits",
    None,
)


def test_range_photometry_equals_full_array_photometry(monkeypatch):
    raw, a = l2_file()
    calls = []
    install(monkeypatch, raw, calls)
    p = asyncio.run(SP.aperture_at(IMG, 10.0, 20.0))
    bad = F.mask_from(a["flags"], {"HOT": 5, "SOURCE": 2}, F.PHOTOMETRY_MASK) | ~np.isfinite(a["img"])
    ref = C.aperture_flux(a["img"], a["var"], bad, TX, TY, 38.0)
    assert p["status"] == "ok"
    assert abs(p["flux_ujy"] - ref["flux_ujy"]) < 1e-6 * abs(ref["flux_ujy"])
    assert abs(p["err_ujy"] - ref["err_ujy"]) < 1e-6 * ref["err_ujy"]
    assert p["masked_in_aperture"] == 1  # the HOT pixel came through the compressed FLAGS
    # apart from the fixed-size header reads, only the rows around the target are read
    data_reads = [c for c in calls if c not in (SP.HEAD_BYTES, SP.HDR_BYTES)]
    assert data_reads and max(data_reads) <= (2 * SP.HALF + 1) * N * 4


def test_layout_change_is_reported_not_guessed(monkeypatch):
    raw, _ = l2_file()
    calls = []
    install(monkeypatch, raw.replace(b"EXTNAME = 'VARIANCE'", b"EXTNAME = 'OTHERXXX'"), calls)
    try:
        asyncio.run(SP.aperture_at(IMG, 10.0, 20.0))
    except SP.LayoutError as e:
        assert "VARIANCE" in str(e)
    else:
        raise AssertionError("expected LayoutError")


def test_visit_spectrum_counts_and_sorting(monkeypatch):
    imgs = [
        S.SpherexImage(
            f"dr1:o{i}:D{d}",
            "dr1",
            "c",
            f"o{i}",
            d,
            60900.0 + i * 0.01,
            60900.005 + i * 0.01,
            "2025-08-01T00:00:00Z",
            1.0,
            2.0,
            "https://irsa.ipac.caltech.edu/x.fits",
            None,
        )
        for i, d in enumerate([1, 2, 3])
    ]

    async def fake_cov(ra, dec, progress=None):
        return imgs

    async def fake_point(img, ra, dec):
        if img.detector == 2:
            raise SP.LayoutError("boom")
        return {
            "image_id": img.image_id,
            "detector": img.detector,
            "status": "ok",
            "wavelength_um": 3.0 - img.detector,
            "flux_ujy": 1.0,
            "err_ujy": 0.1,
        }

    async def prog(*_):
        return None

    monkeypatch.setattr(SP.S, "coverage", fake_cov)
    monkeypatch.setattr(SP, "aperture_at", fake_point)
    r = asyncio.run(SP.visit_spectrum(10.0, 20.0, 1, prog))
    assert r["counts"] == {"exposures": 3, "ok": 2, "no_photometry": 0, "off_detector": 0, "error": 1}
    assert [p["wavelength_um"] for p in r["points"]] == [0.0, 2.0]
    assert "açıklık fotometrisi" in r["method"]
    assert asyncio.run(SP.visit_spectrum(10.0, 20.0, 9, prog))["points"] == []


def test_status_endpoint_never_guesses(client, monkeypatch):
    from skytracker.http import http
    from skytracker.services import freshness

    monkeypatch.setattr(freshness, "latest", lambda: None)
    monkeypatch.setattr(
        http, "_health", {"irsa": {"ok": True, "detail": "HTTP 200", "at": "2026-11-14T07:00:00Z"}}
    )
    body = client.get("/api/v1/meta/status").json()
    assert body["default"] == "dr1" and [r["id"] for r in body["releases"]] == ["dr1", "qr3"]
    assert body["archive"] is None  # first check not done -> null, no date invented
    states = {u["id"]: u["state"] for u in body["upstreams"]}
    assert states == {"irsa": "ok", "cds": "unknown", "jpl": "unknown"}
