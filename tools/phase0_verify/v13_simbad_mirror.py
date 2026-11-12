"""Phase 0 verification: SIMBAD TAP on the Harvard mirror; Sesame full XML via redirect."""

import time
import requests

UA = {"User-Agent": "spherex-sky-tracker-phase0/0.1 (verification script)"}
BASE = "https://simbad.cfa.harvard.edu/simbad/sim-tap/sync"


def tap(q):
    t0 = time.time()
    r = requests.get(
        BASE,
        params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": q},
        headers=UA,
        timeout=90,
    )
    return r.status_code, time.time() - t0, r.text


q = """
SELECT b.main_id, b.otype, b.ra, b.dec, b.sp_type, b.plx_value, b.plx_err, b.rvz_redshift, b.rvz_radvel,
       b.galdim_majaxis, f.filter, f.flux
FROM basic AS b JOIN ident AS i ON i.oidref = b.oid
LEFT JOIN flux AS f ON f.oidref = b.oid AND f.filter IN ('V','K')
WHERE i.id IN ('M  31', 'M 31', '* alf Ori', 'WISE J085510.83-071442.5', 'NAME Orion Nebula')
"""
st, dt, txt = tap(q)
print("basic+flux:", st, f"{dt:.1f}s\n", txt[:1400])

st, dt, txt = tap(
    "SELECT TOP 10 i.id, b.main_id, b.otype FROM ident AS i JOIN basic AS b ON i.oidref=b.oid "
    "WHERE i.id LIKE 'WISE%0855%'"
)
print("fuzzy 'WISE%0855%':", st, f"{dt:.1f}s\n", txt[:800])

st, dt, txt = tap(
    "SELECT otype, label, description FROM otypedef "
    "WHERE otype IN ('G','AGN','*','BD*','s*r','HII','SN*','Com','LP*')"
)
print("otypedef:", st, f"{dt:.1f}s\n", txt[:900])

st, dt, txt = tap(
    "SELECT TOP 3 table_name FROM TAP_SCHEMA.tables WHERE table_name IN ('basic','ident','flux','mesDistance','otypedef')"
)
print("schema:", st, txt[:300])

print("\n=== Sesame full XML (SNV, follows redirect) ===")
for name in ["Betelgeuse", "M31"]:
    t0 = time.time()
    r = requests.get("https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?" + name, headers=UA, timeout=90)
    print(f"[{name}] {r.status_code} final_url={r.url} {time.time() - t0:.1f}s")
    print(r.text[:1600])
