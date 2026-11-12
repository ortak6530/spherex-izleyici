"""Phase 0 verification: locate the live SIMBAD TAP endpoint; object info; fuzzy identifier search."""

import time
import warnings
import requests

warnings.simplefilter("ignore")
UA = {"User-Agent": "spherex-sky-tracker-phase0/0.1 (verification script)"}

from astroquery.simbad import Simbad, conf  # noqa: E402

print("astroquery Simbad server config:", conf.server, "| timeout", conf.timeout)
try:
    print("astroquery Simbad tap url:", Simbad.tap.baseurl if hasattr(Simbad, "tap") else "-")
except Exception as e:  # noqa: BLE001
    print("tap attr error", e)

for base in [
    "https://simbad.cds.unistra.fr/simbad/sim-tap",
    "https://simbad.u-strasbg.fr/simbad/sim-tap",
    "https://simbad.cds.unistra.fr/tap",
    "https://simbad.cds.unistra.fr/simbad/sim-tap/capabilities",
]:
    try:
        r = requests.get(
            base if base.endswith("capabilities") else base + "/capabilities", headers=UA, timeout=30
        )
        print(f"{base}: {r.status_code} {r.headers.get('Content-Type')} {len(r.content)}B")
    except Exception as e:  # noqa: BLE001
        print(f"{base}: ERROR {type(e).__name__} {e}")

print("\n=== astroquery Simbad.query_object ===")
s = Simbad()
try:
    s.add_votable_fields("otype", "sp_type", "plx_value", "rvz_redshift", "V", "K", "dim")
except Exception as e:  # noqa: BLE001
    print("add fields error:", e)
for name in ["M31", "Betelgeuse", "WISE J085510.83-071442.5"]:
    t0 = time.time()
    try:
        t = s.query_object(name)
        print(f"[{name}] {time.time() - t0:.1f}s cols={t.colnames}")
        for r in t:
            print("   ", {k: str(r[k]) for k in t.colnames})
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] ERROR {type(e).__name__}: {str(e)[:300]}")

print("\n=== fuzzy identifier search (suggestions for 'WISE 0855') ===")
try:
    t0 = time.time()
    t = s.query_tap(
        "SELECT TOP 10 i.id, b.main_id, b.otype FROM ident AS i JOIN basic AS b ON i.oidref=b.oid "
        "WHERE i.id LIKE 'WISE%0855%'"
    )
    print(f"{time.time() - t0:.1f}s", [(str(r["id"]), str(r["main_id"]), str(r["otype"])) for r in t])
except Exception as e:  # noqa: BLE001
    print("ERROR", type(e).__name__, str(e)[:300])
r = requests.get(
    "https://www.wikidata.org/w/api.php",
    headers=UA,
    timeout=60,
    params={
        "action": "wbsearchentities",
        "search": "WISE 0855",
        "language": "en",
        "format": "json",
        "limit": 5,
    },
)
print(
    "wikidata wbsearchentities:",
    [(h["id"], h.get("label"), h.get("description")) for h in r.json().get("search", [])],
)
