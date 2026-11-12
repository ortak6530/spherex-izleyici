"""Pure numerical helpers for comparing two SPHEREx cutouts (no network, unit-tested).

Conventions: arrays are FITS order (row 0 = bottom); pixel coordinates are 0-based; surface brightness in
MJy/sr. Every number returned here is computed from the data; nothing is estimated or invented.
"""

from __future__ import annotations

import math

import numpy as np

ARCSEC2_TO_SR = (math.pi / 648000.0) ** 2
SYSTEMATIC_FRACTION = 0.03  # IRSA photometry tool adds 3 % in quadrature (Explanatory Supplement, eq. 19)

# Time-variable foregrounds that are NOT subtracted from SPHEREx images (Supplement sec. 2.3)
ATMOSPHERIC_LINES_UM = {
    "He I 1.083 µm": 1.083,
    "hava parlaması 0.78 µm": 0.78,
    "hava parlaması 0.84 µm": 0.84,
    "hava parlaması 0.93 µm": 0.93,
    "hava parlaması 1.13 µm": 1.13,
    "hava parlaması 1.81 µm": 1.81,
    "hava parlaması 2.63 µm": 2.63,
    "hava parlaması 2.75 µm": 2.75,
    "shuttle glow ~2.9 µm": 2.9,
    "hava parlaması 4.03 µm": 4.03,
    "shuttle glow ~4.5 µm": 4.5,
    "hava parlaması 4.64 µm": 4.64,
}


def bilinear_sample(src: np.ndarray, bad: np.ndarray, x: np.ndarray, y: np.ndarray):
    """Sample src at fractional pixel positions; any bad/NaN neighbour or out-of-range -> NaN."""
    ny, nx = src.shape
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    ok = (x0 >= 0) & (y0 >= 0) & (x0 + 1 < nx) & (y0 + 1 < ny) & np.isfinite(x) & np.isfinite(y)
    out = np.full(x.shape, np.nan, dtype=np.float64)
    if not ok.any():
        return out
    xa, ya, fxa, fya = x0[ok], y0[ok], fx[ok], fy[ok]
    s = src.astype(np.float64)
    corners = [s[ya, xa], s[ya, xa + 1], s[ya + 1, xa], s[ya + 1, xa + 1]]
    badn = bad[ya, xa] | bad[ya, xa + 1] | bad[ya + 1, xa] | bad[ya + 1, xa + 1]
    val = (
        corners[0] * (1 - fxa) * (1 - fya)
        + corners[1] * fxa * (1 - fya)
        + corners[2] * (1 - fxa) * fya
        + corners[3] * fxa * fya
    )
    val[badn | ~np.isfinite(val)] = np.nan
    out[ok] = val
    return out


def robust_background(img: np.ndarray, usable: np.ndarray, min_fraction: float = 0.05):
    """Sigma-clipped median of usable (non-source, non-bad) pixels; None if too few remain."""
    v = img[usable & np.isfinite(img)].astype(np.float64)
    if v.size < max(30, int(min_fraction * img.size)):
        return None, None
    for _ in range(5):
        med = np.median(v)
        mad = 1.4826 * np.median(np.abs(v - med))
        keep = np.abs(v - med) < 3 * max(mad, 1e-12)
        if keep.all():
            break
        v = v[keep]
    return float(np.median(v)), float(1.4826 * np.median(np.abs(v - np.median(v))))


def relative_scale(a: np.ndarray, b: np.ndarray, exclude: np.ndarray) -> float | None:
    """Robust factor k so that k*b matches a over the field (target core excluded)."""
    m = np.isfinite(a) & np.isfinite(b) & ~exclude
    if m.sum() < 20:
        return None
    bb, aa = b[m], a[m]
    bright = bb > np.percentile(bb, 50)
    bright &= np.abs(bb) > 1e-6
    if bright.sum() < 10:
        return None
    k = float(np.median(aa[bright] / bb[bright]))
    return k if math.isfinite(k) and 0.2 < k < 5 else None


def disk_mask(shape, cx: float, cy: float, r: float) -> np.ndarray:
    yy, xx = np.mgrid[0 : shape[0], 0 : shape[1]]
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r


def annulus_mask(shape, cx: float, cy: float, r_in: float, r_out: float) -> np.ndarray:
    yy, xx = np.mgrid[0 : shape[0], 0 : shape[1]]
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    return (d2 >= r_in * r_in) & (d2 <= r_out * r_out)


def centroid(img: np.ndarray, bad: np.ndarray, cx: float, cy: float, r: float = 3.0, bg: float = 0.0):
    """Flux-weighted centroid of positive, good pixels inside radius r. None if no signal."""
    m = disk_mask(img.shape, cx, cy, r) & ~bad & np.isfinite(img)
    # np.where (not multiplication): saturated cores are NaN and NaN * 0 would poison the sum
    w = np.where(m, np.clip(img - bg, 0, None), 0.0)
    tot = float(w.sum())
    if tot <= 0:
        return None
    yy, xx = np.mgrid[0 : img.shape[0], 0 : img.shape[1]]
    return float((w * xx).sum() / tot), float((w * yy).sum() / tot)


def aperture_flux(
    img: np.ndarray,
    var: np.ndarray,
    bad: np.ndarray,
    cx: float,
    cy: float,
    omega_arcsec2: float,
    r: float = 2.0,
    r_in: float = 4.0,
    r_out: float = 7.0,
) -> dict | None:
    """Background-subtracted aperture flux in µJy with statistical and 3 % systematic error."""
    ap = disk_mask(img.shape, cx, cy, r)
    good_ap = ap & ~bad & np.isfinite(img)
    if good_ap.sum() < max(3, 0.6 * ap.sum()):
        return None
    ann = annulus_mask(img.shape, cx, cy, r_in, r_out) & ~bad & np.isfinite(img)
    bg = float(np.median(img[ann])) if ann.sum() >= 8 else 0.0
    to_ujy = 1e6 * omega_arcsec2 * ARCSEC2_TO_SR * 1e6  # MJy/sr * sr -> Jy (1e6) -> µJy (1e6)
    # Masked pixels inside the aperture are filled with the mean of the good ones (area correction)
    n_ap, n_good = int(ap.sum()), int(good_ap.sum())
    flux = float((img[good_ap] - bg).sum()) * (n_ap / n_good) * to_ujy
    stat = float(np.sqrt(np.nansum(var[good_ap]))) * (n_ap / n_good) * to_ujy
    err = math.hypot(stat, SYSTEMATIC_FRACTION * flux)
    return {
        "flux_ujy": flux,
        "err_ujy": err,
        "stat_err_ujy": stat,
        "background_mjy_sr": bg,
        "aperture_px": r,
        "masked_in_aperture": n_ap - n_good,
    }


def percent_change(fa: dict | None, fb: dict | None) -> dict | None:
    if not fa or not fb or fa["flux_ujy"] == 0:
        return None
    a, b = fa["flux_ujy"], fb["flux_ujy"]
    pct = (b - a) / a * 100.0
    err = 100.0 * abs(b / a) * math.hypot(fa["err_ujy"] / a, fb["err_ujy"] / b)
    return {"percent": pct, "err_percent": err, "significance": abs(pct) / err if err else None}


def channel_match(lam_a: float, lam_b: float, bw_a: float, bw_b: float) -> dict:
    """Decision S5: |dλ| <= 0.5 bandwidth -> match; <= 1 -> warn; > 1 -> reject."""
    dl = abs(lam_a - lam_b)
    bw = (bw_a + bw_b) / 2.0
    ratio = dl / bw if bw > 0 else float("inf")
    status = "match" if ratio <= 0.5 else "warn" if ratio <= 1.0 else "reject"
    return {"delta_um": lam_b - lam_a, "bandwidth_um": bw, "ratio": ratio, "status": status}


def nearby_lines(lam: float, bw: float) -> list[str]:
    return [name for name, l0 in ATMOSPHERIC_LINES_UM.items() if abs(lam - l0) <= bw]


def difference_stats(diff: np.ndarray, sigma: np.ndarray) -> dict:
    m = np.isfinite(diff)
    if not m.any():
        return {"n": 0}
    i = int(np.nanargmax(np.where(m, np.abs(diff), -np.inf)))
    y, x = divmod(i, diff.shape[1])
    s = sigma[y, x] if np.isfinite(sigma[y, x]) else None
    return {
        "n": int(m.sum()),
        "mean": float(np.nanmean(diff)),
        "std": float(np.nanstd(diff)),
        "max_abs": float(abs(diff[y, x])),
        "max_px": [x, y],
        "max_sigma": None if s is None else float(s),
        "n_over_5sigma": int(np.nansum(np.abs(sigma) > 5)),
    }
