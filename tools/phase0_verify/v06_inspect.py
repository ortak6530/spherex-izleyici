"""Phase 0 verification: IMAGE/FLAGS/VARIANCE/ZODI headers, WCS-WAVE lookup, per-pixel wavelength."""

import warnings
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning

warnings.simplefilter("ignore", FITSFixedWarning)
hdul = fits.open("data/m31_cutout_D4.fits")


def dump(name, skip_prefixes=()):
    h = hdul[name].header
    print(f"\n--- {name} header ---")
    for k in h.keys():
        if k in ("COMMENT", "HISTORY", "") or k.startswith(skip_prefixes):
            continue
        print(f"  {k:<10}= {str(h[k])[:60]!s:<60} / {h.comments[k][:70]}")


dump("IMAGE", skip_prefixes=("A_", "B_", "AP_", "BP_"))
dump("FLAGS")
print("\n--- VARIANCE / ZODI: keys not in IMAGE ---")
img_keys = set(hdul["IMAGE"].header.keys())
for name in ("VARIANCE", "ZODI"):
    h = hdul[name].header
    print(name, "BUNIT=", h.get("BUNIT"), "| extra keys:", [k for k in h.keys() if k not in img_keys][:30])
dump("WCS-WAVE")
tab = hdul["WCS-WAVE"].data
print("WCS-WAVE columns:", tab.columns.names, [c.format for c in tab.columns])
for c in tab.columns.names:
    v = np.asarray(tab[c][0])
    print(f"  {c}: shape={v.shape} min={v.min():.5g} max={v.max():.5g} head={v.ravel()[:6]}")

# Per-pixel wavelength through the alternate 'W' WCS (lookup table)
img = hdul["IMAGE"]
wcs_sky = WCS(img.header)
wcs_w = WCS(img.header, fobj=hdul, key="W")
print("\nW-wcs ctype:", wcs_w.wcs.ctype, "cunit:", list(wcs_w.wcs.cunit))
ny, nx = img.data.shape
yy, xx = np.mgrid[0:ny, 0:nx]
lam, bw = wcs_w.pixel_to_world_values(xx, yy)
print(f"wavelength over cutout: {lam.min():.4f}..{lam.max():.4f}  bandwidth: {bw.min():.5f}..{bw.max():.5f}")
print(
    "lambda gradient along x/y (um/px):",
    float(np.median(np.diff(lam, axis=1))),
    float(np.median(np.diff(lam, axis=0))),
)
cy, cx = ny // 2, nx // 2
print("centre pixel sky:", wcs_sky.pixel_to_world_values(cx, cy), "lambda:", lam[cy, cx], "bw:", bw[cy, cx])

# Data stats
d = img.data
fl = hdul["FLAGS"].data
var = hdul["VARIANCE"].data
z = hdul["ZODI"].data
print("\nIMAGE  nan:", int(np.isnan(d).sum()), "median:", float(np.nanmedian(d)), "max:", float(np.nanmax(d)))
print(
    "ZODI   median:",
    float(np.nanmedian(z)),
    "ratio zodi/image median:",
    float(np.nanmedian(z) / np.nanmedian(d)),
)
print("VAR    median:", float(np.nanmedian(var)), "-> sigma:", float(np.sqrt(np.nanmedian(var))))
vals, counts = np.unique(fl, return_counts=True)
print("FLAGS unique values (val:count):", dict(zip(vals.tolist(), counts.tolist())))
bits = {b: int(((fl >> b) & 1).sum()) for b in range(32) if ((fl >> b) & 1).any()}
print("FLAGS set bits (bit:pixels):", bits)
# PSF extension summary
psf = hdul["PSF"]
print(
    "\nPSF ext shape:",
    psf.data.shape,
    "keys sample:",
    [
        (k, psf.header[k])
        for k in list(psf.header.keys())
        if k.startswith(("XCTR", "YCTR", "OVERSAMP", "PSF", "NAXIS"))
    ][:12],
)
