"""Phase 0 verification: how flag bit definitions are stored in R7 vs QR2 FLAGS headers."""
import io
import time
import requests
from astropy.io import fits

URL = ("https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/2026W30_1B/l2b-v27-2026-222/3/"
       "level2_2026W30_1B_0051_1D3_spx_l2b-v27-2026-222.fits")
for wait in (0, 10, 30):
    time.sleep(wait)
    r = requests.get(f"{URL}?center=10.684708,41.26875d&size=0.02", timeout=180,
                     headers={"User-Agent": "spherex-sky-tracker-phase0/0.1 (verification script)"})
    if r.status_code == 200:
        break
    print("status", r.status_code, r.content[:60])
open("data/qr3_cutout_D3.fits", "wb").write(r.content)
h = fits.open(io.BytesIO(r.content))
fh = h["FLAGS"].header
skip = ("A_", "B_", "AP_", "BP_", "PC", "CR", "CD", "CT", "CU", "NAXIS", "WCS", "LONP", "LATP", "MJD", "DATE",
        "PV", "PS", "CNAME")
print("R7 FLAGS header (non-WCS):")
for k in fh:
    if not k.startswith(skip):
        print(f"  {k:<18}= {str(fh[k])[:50]!s:<50} / {fh.comments[k][:60]}")
q = fits.open("data/m31_cutout_D4.fits")
print("\nQR2 ZODIMDL:", q["ZODI"].header.get("ZODIMDL"), "| R7 ZODIMDL:", h["ZODI"].header.get("ZODIMDL"))
print("EPSF columns:", h["EPSF"].columns.names)
print("EPSF header sample:", [(k, h["EPSF"].header[k]) for k in list(h["EPSF"].header)[:0] + [
    k for k in h["EPSF"].header if k.startswith(("OVERSAMP", "NX", "NY", "GRID", "ZONE", "EPSF"))]][:10])
