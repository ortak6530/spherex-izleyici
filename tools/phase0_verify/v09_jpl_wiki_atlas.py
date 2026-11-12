"""Phase 0 verification: JPL SBDB/Horizons (solar system), Wikipedia REST, 3I/ATLAS SPHEREx table."""

import json
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "spherex-sky-tracker-phase0/0.1 (verification script)"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.headers.get("Content-Type"), r.read(), time.time() - t0


print("=== JPL SBDB lookup (name -> designation) ===")
for s in ["3I", "Ceres", "C/2025 N1"]:
    url = "https://ssd-api.jpl.nasa.gov/sbdb.api?" + urllib.parse.urlencode({"sstr": s})
    try:
        st, ct, body, dt = get(url)
        d = json.loads(body)
        obj = d.get("object", {})
        print(
            f"[{s}] {st} {dt:.1f}s -> fullname={obj.get('fullname')} kind={obj.get('kind')} "
            f"orbit_class={obj.get('orbit_class', {}).get('name')} | keys={list(d)[:6]}"
        )
    except Exception as e:  # noqa: BLE001
        print(f"[{s}] ERROR {type(e).__name__}: {e}")

print("\n=== JPL Horizons API: 3I/ATLAS geocentric RA/Dec on 2025-08-10 ===")
params = {
    "format": "json",
    "COMMAND": "'DES=C/2025 N1;'",
    "OBJ_DATA": "NO",
    "MAKE_EPHEM": "YES",
    "EPHEM_TYPE": "OBSERVER",
    "CENTER": "'500@399'",
    "START_TIME": "'2025-08-10'",
    "STOP_TIME": "'2025-08-11'",
    "STEP_SIZE": "'1 d'",
    "QUANTITIES": "'1'",
    "ANG_FORMAT": "DEG",
}
url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(params)
try:
    st, ct, body, dt = get(url)
    d = json.loads(body)
    res = d.get("result", "")
    i, j = res.find("$$SOE"), res.find("$$EOE")
    print(st, f"{dt:.1f}s", "version", d.get("signature", {}).get("version"))
    print(res[i : j + 5] if i >= 0 else res[:800])
except Exception as e:  # noqa: BLE001
    print("ERROR", type(e).__name__, e)

print("\n=== Wikipedia REST summary (tr, fallback en) ===")
for lang, title in [
    ("tr", "Andromeda_Galaksisi"),
    ("tr", "Betelgeuse"),
    ("tr", "WISE_0855−0714"),
    ("en", "WISE_0855−0714"),
]:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title)
    try:
        st, ct, body, dt = get(url)
        d = json.loads(body)
        print(
            f"[{lang}:{title}] {st} {dt:.1f}s type={d.get('type')} title={d.get('title')} "
            f"extract={d.get('extract', '')[:110]!r}"
        )
    except Exception as e:  # noqa: BLE001
        print(f"[{lang}:{title}] ERROR {type(e).__name__}: {e}")

print("\n=== IRSA 3I/ATLAS SPHEREx observation table ===")
url = "https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/obscore_3I_Atlas.vot"
try:
    st, ct, body, dt = get(url, timeout=120)
    open("data/obscore_3I_Atlas.vot", "wb").write(body)
    from astropy.table import Table

    t = Table.read("data/obscore_3I_Atlas.vot", format="votable")
    print(st, ct, len(body), "bytes", f"{dt:.1f}s", "rows", len(t))
    print("columns:", t.colnames)
    from astropy.time import Time
    import collections

    months = collections.Counter(x.strftime("%Y-%m-%d") for x in Time(t["t_min"], format="mjd").datetime)
    print("obs per day:", sorted(months.items()))
    print(
        "collections:",
        collections.Counter(str(x) for x in t["obs_collection"]) if "obs_collection" in t.colnames else "-",
    )
    print(
        "first row:",
        {
            k: str(t[0][k])[:90]
            for k in t.colnames
            if k in ("obs_id", "energy_bandpassname", "access_url", "comet_ra", "comet_dec", "t_min")
        },
    )
except Exception as e:  # noqa: BLE001
    print("ERROR", type(e).__name__, e)
