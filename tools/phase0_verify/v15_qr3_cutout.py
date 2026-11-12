"""Phase 0 verification: one QR3 (R7) cutout - extension layout, flag bits, version keywords."""

import io
import time
import requests
from astropy.io import fits

URL = (
    "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/2026W30_1B/l2b-v27-2026-222/3/"
    "level2_2026W30_1B_0051_1D3_spx_l2b-v27-2026-222.fits"
)
for attempt, wait in enumerate((0, 10, 30, 60)):
    time.sleep(wait)
    t0 = time.time()
    r = requests.get(
        f"{URL}?center=10.684708,41.26875d&size=0.05",
        timeout=180,
        headers={"User-Agent": "spherex-sky-tracker-phase0/0.1 (verification script)"},
    )
    print(
        f"attempt {attempt}: {r.status_code} {r.headers.get('Content-Type')} {len(r.content)} bytes "
        f"{time.time() - t0:.1f}s retry-after={r.headers.get('Retry-After')}"
    )
    if r.status_code == 200:
        break
    print("   body:", r.content[:200])
h = fits.open(io.BytesIO(r.content))
h.info()
print("VERSION:", h[0].header.get("VERSION"))
fh = h["FLAGS"].header
print("MP_ bits:", sorted(((fh[k], k) for k in fh if k.startswith("MP_"))))
ih = h["IMAGE"].header
for k in ("BUNIT", "DATE-OBS", "SPS_EPA", "PSF_FWHM", "OMEGA_MEDIAN", "L2DQAFLG"):
    print(f"  {k} = {ih.get(k)}")
print("ZODI header keys:", [(k, h["ZODI"].header[k]) for k in h["ZODI"].header if "ZODI" in k or "SCAL" in k])
hist = [str(c) for c in ih.get("HISTORY", [])]
print("HISTORY zodi/calib lines:", [x for x in hist if "odi" in x or "zodi" in x][:6])
