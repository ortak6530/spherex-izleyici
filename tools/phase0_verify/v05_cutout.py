"""Phase 0 verification: download one SPHEREx cutout of M31 and inspect MEF extensions."""

import time
import urllib.request
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

RA, DEC = 10.684708, 41.268750
FITS_URL = (
    "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/level2/2025W28_1B/l2b-v20-2025-260/4/"
    "level2_2025W28_1B_0480_4D4_spx_l2b-v20-2025-260.fits"
)
SIZE_DEG = 0.1
url = f"{FITS_URL}?center={RA},{DEC}d&size={SIZE_DEG}"
print("GET", url)
t0 = time.time()
with urllib.request.urlopen(url, timeout=120) as resp:
    raw = resp.read()
    print(
        "status",
        resp.status,
        "content-type",
        resp.headers.get("Content-Type"),
        "bytes",
        len(raw),
        f"time={time.time() - t0:.1f}s",
    )
open("data/m31_cutout_D4.fits", "wb").write(raw)

hdul = fits.open("data/m31_cutout_D4.fits")
hdul.info()

h0 = hdul[0].header
print("\n--- primary header (selected) ---")
for k in list(h0.keys()):
    if k in ("COMMENT", "HISTORY", ""):
        continue
    print(f"  {k:<10}= {str(h0[k])[:70]!s:<70} / {h0.comments[k][:60]}")
