"""Phase 0 verification: MAST HST/JWST coverage and preview availability."""

import collections
import time
import warnings
import astropy.units as u
from astropy.coordinates import SkyCoord

warnings.simplefilter("ignore")
from astroquery.mast import Observations, MastMissions  # noqa: E402

targets = {
    "M31 nucleus": SkyCoord(10.684708, 41.268750, unit="deg"),
    "Orion Nebula (M42)": SkyCoord(83.8221, -5.3911, unit="deg"),
    "empty-ish field": SkyCoord(
        150.0, -60.5, unit="deg"
    ),  # arbitrary low-latitude field for a 'no data' check
}
R = 2 * u.arcmin

print("=== MAST CAOM (Observations.query_criteria) ===")
for label, c in targets.items():
    for coll in ("HST", "JWST"):
        t0 = time.time()
        try:
            tab = Observations.query_criteria(
                coordinates=c, radius=R, obs_collection=coll, dataproduct_type="image", intentType="science"
            )
        except Exception as e:  # noqa: BLE001
            print(f"[{label}/{coll}] ERROR {type(e).__name__}: {e}")
            continue
        dt = time.time() - t0
        n = len(tab)
        if n == 0:
            print(f"[{label}/{coll}] 0 rows ({dt:.1f}s)")
            continue
        public = tab[tab["dataRights"] == "PUBLIC"] if "dataRights" in tab.colnames else tab
        has_prev = (
            sum(1 for x in public["jpegURL"] if x and str(x) not in ("--", ""))
            if "jpegURL" in tab.colnames
            else -1
        )
        print(f"[{label}/{coll}] rows={n} public={len(public)} with jpegURL={has_prev} ({dt:.1f}s)")
        print(
            "   instruments:", collections.Counter(str(x) for x in public["instrument_name"]).most_common(5)
        )
        print("   filters:", collections.Counter(str(x) for x in public["filters"]).most_common(5))
        ex = [r for r in public if r["jpegURL"] and str(r["jpegURL"]) not in ("--", "")][:1]
        if ex:
            r = ex[0]
            print(
                "   example:",
                r["obs_id"],
                r["instrument_name"],
                r["filters"],
                r["t_min"],
                "jpegURL:",
                r["jpegURL"],
            )
        if label.startswith("M31") and coll == "HST":
            print("   columns:", tab.colnames)

print("\n=== MastMissions (mission-specific search API) ===")
for mission in ("hst", "jwst"):
    try:
        mm = MastMissions(mission=mission)
        t0 = time.time()
        res = mm.query_region(targets["M31 nucleus"], radius=R, limit=5)
        print(f"[{mission}] rows={len(res)} ({time.time() - t0:.1f}s) cols={res.colnames[:14]}")
    except Exception as e:  # noqa: BLE001
        print(f"[{mission}] ERROR {type(e).__name__}: {e}")
