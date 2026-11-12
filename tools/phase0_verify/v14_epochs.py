"""Phase 0 feasibility: wavelength at M31 for every D4 exposure (header range-reads),
pick one exposure per epoch at matching wavelength, download cutouts, compare ZODI and differences."""

import collections
import concurrent.futures as cf
import io
import time
import warnings

import numpy as np
import pyvo
import requests
from astropy.io import fits
from astropy.table import Table
from astropy.time import Time
from astropy.wcs import WCS, FITSFixedWarning

from astropy import log as astropy_log  # noqa: E402

astropy_log.setLevel("ERROR")
warnings.simplefilter("ignore", FITSFixedWarning)
warnings.simplefilter("ignore", UserWarning)


def wave_wcs(hdr, hdul):
    """Spectral lookup WCS without SIP keys (SIP belongs to the celestial WCS only)."""
    h = hdr.copy()
    for k in list(h.keys()):
        if k.split("_")[0] in ("A", "B", "AP", "BP") and "_" in k:
            del h[k]
    hdul[1].header = h
    return WCS(h, fobj=hdul, key="W")


RA, DEC = 10.684708, 41.268750
UA = {"User-Agent": "spherex-sky-tracker-phase0/0.1 (verification script)"}
S = requests.Session()
S.headers.update(UA)

tab = Table.read("data/m31_obscore.ecsv", format="ascii.ecsv")
tab = tab[tab["energy_bandpassname"] == "SPHEREx-D4"]
print("D4 exposures covering M31:", len(tab))


def datalink(url):
    dl = pyvo.dal.adhoc.DatalinkResults.from_result_url(url, session=S)
    this = next(r.access_url for r in dl if r.semantics == "#this")
    swcs = next(r.access_url for r in dl if r.semantics == "#calibration" and "spectral_wcs" in r.access_url)
    return this, swcs


swcs_cache = {}


def wcs_wave_table(swcs_url):
    """Read only the trailing WCS-WAVE BINTABLE of a spectral_wcs calibration file via HTTP Range."""
    if swcs_url in swcs_cache:
        return swcs_cache[swcs_url]
    tail = S.get(swcs_url, headers={"Range": "bytes=-17280"}, timeout=60).content
    i = tail.rfind(b"XTENSION= 'BINTABLE'")
    hdu = fits.BinTableHDU.fromstring(tail[i:])
    swcs_cache[swcs_url] = hdu
    return hdu


def wavelength_at_target(row):
    this, swcs = datalink(str(row["access_url"]))
    raw = S.get(this, headers={"Range": "bytes=0-28799"}, timeout=60).content
    hdr = fits.Header.fromstring(raw[2880:].split(b"END" + b" " * 77)[0] + b"END" + b" " * 77)
    tbl = wcs_wave_table(swcs)
    tbl.header["EXTNAME"] = "WCS-WAVE"
    hdul = fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(header=hdr), tbl])
    x, y = WCS(hdr).world_to_pixel_values(RA, DEC)
    lam, bw = wave_wcs(hdr, hdul).pixel_to_world_values(x, y)
    lam_sip, _ = WCS(hdr, fobj=hdul, key="W").pixel_to_world_values(x, y)
    if abs(lam_sip - lam) > 1e-4:
        print(f"   NOTE {row['obs_id']}: W-WCS with SIP differs by {1e3 * (lam_sip - lam):+.2f} nm")
    return dict(
        obs_id=str(row["obs_id"]),
        coll=str(row["obs_collection"]),
        t=float(row["t_min"]),
        x=float(x),
        y=float(y),
        lam=float(lam),
        bw=float(bw),
        url=this,
        swcs=swcs.rsplit("/", 1)[-1],
        epa=hdr.get("SPS_EPA"),
        version=None,
    )


t0 = time.time()
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    rows = list(ex.map(wavelength_at_target, tab))
print(
    f"computed {len(rows)} target wavelengths in {time.time() - t0:.1f}s; spectral_wcs files used:",
    collections.Counter(r["swcs"] for r in rows),
)

for r in rows:
    r["epoch"] = Time(r["t"], format="mjd").strftime("%Y-%m")
groups = collections.defaultdict(list)
for r in rows:
    key = {
        "2025-07": "E1 2025-07",
        "2025-08": "E1 2025-07",
        "2025-12": "E2 2025-12",
        "2026-01": "E2 2025-12",
        "2026-07": "E3 2026-07",
        "2026-08": "E3 2026-07",
    }[r["epoch"]]
    groups[key].append(r)
for k in sorted(groups):
    lams = sorted(round(g["lam"], 3) for g in groups[k])
    print(
        f"{k}: n={len(lams)} SPS_EPA={sorted(set(g['epa'] for g in groups[k]))} "
        f"collections={collections.Counter(g['coll'] for g in groups[k])}\n   lambda@M31 (um): {lams}"
    )

ref = min(groups["E1 2025-07"], key=lambda g: abs(g["lam"] - 2.44))
picks = {"E1 2025-07": ref}
for k in ("E2 2025-12", "E3 2026-07"):
    picks[k] = min(groups[k], key=lambda g: abs(g["lam"] - ref["lam"]))
print("\nPicked (closest wavelength to reference):")
for k, p in picks.items():
    print(
        f"  {k}: {p['obs_id']} {p['coll']} lambda={p['lam']:.4f} bw={p['bw']:.4f} dlam={p['lam'] - ref['lam']:+.4f} "
        f"det_xy=({p['x']:.0f},{p['y']:.0f})"
    )

# Download cutouts and compare
SIZE = 0.1
cut = {}
for k, p in picks.items():
    r = S.get(f"{p['url']}?center={RA},{DEC}d&size={SIZE}", timeout=180)
    h = fits.open(io.BytesIO(r.content))
    cut[k] = h
    fl = h["FLAGS"].data
    bad_bits = [
        h["FLAGS"].header[k2]
        for k2 in h["FLAGS"].header
        if k2.startswith("MP_")
        and k2
        not in ("MP_SOURCE", "MP_FULLSAMPLE", "MP_OUTLIER", "MP_OVERFLOW", "MP_TRANSIENT", "MP_DICHROIC")
    ]
    mask = np.zeros_like(fl, bool)
    for b in bad_bits:
        mask |= ((fl >> b) & 1).astype(bool)
    img, zod = h["IMAGE"].data, h["ZODI"].data
    src = ((fl >> h["FLAGS"].header["MP_SOURCE"]) & 1).astype(bool)
    bg = np.nanmedian(img[~mask & ~src]) if (~mask & ~src).any() else np.nan
    print(
        f"\n{k}: shape={img.shape} MP_ keys={sorted(k2 for k2 in h['FLAGS'].header if k2.startswith('MP_'))}"
    )
    print(
        f"   masked(bad)={mask.mean():.1%} source-flag={src.mean():.1%} ZODI median={np.nanmedian(zod):.4f} "
        f"IMAGE median={np.nanmedian(img):.3f} non-source bg={bg:.4f} MJy/sr  VERSION={h[0].header.get('VERSION')}"
    )


# Difference E2-E1 and E3-E1 on the native pixel grids is NOT valid (different rotation/position);
# reproject onto E1 grid with nearest-neighbour via WCS for a quick look.
def reproject_nn(src_h, dst_h, layer):
    dw, sw = WCS(dst_h["IMAGE"].header), WCS(src_h["IMAGE"].header)
    ny, nx = dst_h["IMAGE"].data.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    ra, de = dw.pixel_to_world_values(xx, yy)
    sx, sy = sw.world_to_pixel_values(ra, de)
    sx, sy = np.rint(sx).astype(int), np.rint(sy).astype(int)
    sny, snx = src_h[layer].data.shape
    ok = (sx >= 0) & (sy >= 0) & (sx < snx) & (sy < sny)
    out = np.full((ny, nx), np.nan, np.float64)
    out[ok] = src_h[layer].data[sy[ok], sx[ok]]
    return out


e1 = cut["E1 2025-07"]
for k in ("E2 2025-12", "E3 2026-07"):
    a = e1["IMAGE"].data.astype(float)
    b = reproject_nn(cut[k], e1, "IMAGE")
    za, zb = e1["ZODI"].data.astype(float), reproject_nn(cut[k], e1, "ZODI")
    raw = b - a
    zsub = (b - zb) - (a - za)
    core = np.zeros_like(a, bool)
    cy, cx = np.array(a.shape) // 2
    core[cy - 3 : cy + 4, cx - 3 : cx + 4] = True

    def st(d):
        d2 = d[np.isfinite(d) & ~core]
        return f"median={np.median(d2):+.4f} std={np.std(d2):.4f}"

    print(f"\n{k} minus E1 (nearest-neighbour regrid, outside 7x7 core):")
    print(
        f"   raw diff: {st(raw)} | ZODI-subtracted diff: {st(zsub)} | dZODI median={np.nanmedian(zb - za):+.4f}"
    )
    print(f"   core (7x7) ratio later/E1: {np.nanmedian(b[core]) / np.nanmedian(a[core]):.4f}")
