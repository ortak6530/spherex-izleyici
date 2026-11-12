"""Phase 0 verification: CDS Sesame name resolution and SIMBAD TAP object info."""

import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "spherex-sky-tracker-phase0/0.1 (verification script)"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        return r.status, r.headers.get("Content-Type"), body, time.time() - t0


print("=== Sesame (XML, all resolvers: SIMBAD->NED->VizieR, -oxp, 'SNV') ===")
for name in [
    "M31",
    "Betelgeuse",
    "WISE 0855",
    "WISE J085510.83-071442.5",
    "Orion Nebula",
    "3I/ATLAS",
    "C/2025 N1",
    "Ceres",
    "xyznotanobject123",
]:
    url = "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?" + urllib.parse.quote(name)
    try:
        st, ct, body, dt = get(url)
        root = ET.fromstring(body)
        out = []
        for res in root.iter("Resolver"):
            ra, de, oname, otype = (
                res.findtext("jradeg"),
                res.findtext("jdedeg"),
                res.findtext("oname"),
                res.findtext("otype"),
            )
            if ra:
                out.append(f"{res.get('name')}: {oname} ra={ra} dec={de} otype={otype}")
            else:
                info = (res.findtext("INFO") or "").strip()
                out.append(f"{res.get('name')}: (no position) {info[:60]}")
        print(f"[{name}] {st} {dt:.1f}s ->", " | ".join(out) if out else "(no Resolver elements)")
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] ERROR {type(e).__name__}: {e}")

print("\n=== SIMBAD TAP (sync, basic + flux) ===")
adql = """
SELECT TOP 5 b.main_id, b.otype, b.ra, b.dec, b.sp_type, b.plx_value, b.plx_err, b.rvz_redshift,
       b.rvz_radvel, b.galdim_majaxis, f.filter, f.flux
FROM basic AS b
JOIN ident AS i ON i.oidref = b.oid
LEFT JOIN flux AS f ON f.oidref = b.oid AND f.filter IN ('V','K')
WHERE i.id = 'M 31' OR i.id = '* alf Ori'
"""
url = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync?" + urllib.parse.urlencode(
    {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql}
)
st, ct, body, dt = get(url)
print(st, ct, f"{dt:.1f}s")
print(body.decode("utf-8", "replace"))

# Object type description table (for Turkish labels later)
adql2 = "SELECT TOP 8 otype, label, description FROM otypedef WHERE otype IN ('G','*','BD*','Com','SN*','HII','RGB*','s*r')"
url = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync?" + urllib.parse.urlencode(
    {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql2}
)
try:
    st, ct, body, dt = get(url)
    print("otypedef:", st, f"{dt:.1f}s\n", body.decode("utf-8", "replace"))
except Exception as e:  # noqa: BLE001
    print("otypedef ERROR", e)
