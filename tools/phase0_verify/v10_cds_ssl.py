"""Phase 0 verification: diagnose CDS SSL failure; retry Sesame/SIMBAD with certifi (requests)."""
import ssl
import socket
import time
import urllib.parse
import xml.etree.ElementTree as ET

import certifi
import requests

HOST = "cds.unistra.fr"
UA = {"User-Agent": "spherex-sky-tracker-phase0/0.1 (verification script)"}

# 1) Which chain does the server present, and does the default (Windows store) context accept it?
ctx = ssl.create_default_context(cafile=certifi.where())
with socket.create_connection((HOST, 443), timeout=20) as s:
    with ctx.wrap_socket(s, server_hostname=HOST) as ss:
        cert = ss.getpeercert()
        print("certifi OK. issuer:", dict(x[0] for x in cert["issuer"]), "notAfter:", cert["notAfter"])
print("certifi version:", certifi.__version__, "| requests", requests.__version__)

# 2) Sesame via requests (uses certifi)
print("\n=== Sesame via requests/certifi ===")
for name in ["M31", "Betelgeuse", "WISE 0855", "WISE J085510.83-071442.5", "Orion Nebula", "3I/ATLAS",
             "C/2025 N1", "Ceres", "xyznotanobject123"]:
    url = "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?" + urllib.parse.quote(name)
    t0 = time.time()
    r = requests.get(url, headers=UA, timeout=60)
    dt = time.time() - t0
    root = ET.fromstring(r.content)
    out = []
    for res in root.iter("Resolver"):
        ra, de = res.findtext("jradeg"), res.findtext("jdedeg")
        if ra:
            out.append(f"{res.get('name')}: {res.findtext('oname')} ra={float(ra):.6f} dec={float(de):.6f} "
                       f"otype={res.findtext('otype')}")
        else:
            out.append(f"{res.get('name')}: no position ({(res.findtext('INFO') or '').strip()[:40]})")
    print(f"[{name}] {r.status_code} {dt:.1f}s ->", " | ".join(out) if out else "(no Resolver)")

# 3) SIMBAD TAP via requests
print("\n=== SIMBAD TAP via requests ===")
adql = """
SELECT b.main_id, b.otype, b.ra, b.dec, b.sp_type, b.plx_value, b.plx_err, b.rvz_redshift,
       b.rvz_radvel, b.galdim_majaxis, f.filter, f.flux
FROM basic AS b
JOIN ident AS i ON i.oidref = b.oid
LEFT JOIN flux AS f ON f.oidref = b.oid AND f.filter IN ('V','K')
WHERE i.id IN ('M  31', 'M 31', '* alf Ori', 'WISE J085510.83-071442.5')
"""
t0 = time.time()
r = requests.get("https://simbad.cds.unistra.fr/simbad/sim-tap/sync",
                 params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql},
                 headers=UA, timeout=60)
print(r.status_code, r.headers.get("Content-Type"), f"{time.time()-t0:.1f}s")
print(r.text[:1500])

adql2 = "SELECT otype, label, description FROM otypedef WHERE otype IN ('G','*','BD*','Com','SN*','HII','RG*','s*r')"
r = requests.get("https://simbad.cds.unistra.fr/simbad/sim-tap/sync",
                 params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql2},
                 headers=UA, timeout=60)
print("otypedef:", r.status_code, "\n", r.text[:1200])

# 4) Wikidata: SIMBAD identifier (P3083) -> tr/en Wikipedia titles
print("\n=== Wikidata P3083 (SIMBAD ID) -> sitelinks ===")
for simbad_id in ["M  31", "M 31", "* alf Ori", "WISE J085510.83-071442.5"]:
    r = requests.get("https://www.wikidata.org/w/api.php", headers=UA, timeout=60, params={
        "action": "query", "list": "search", "format": "json",
        "srsearch": f'haswbstatement:"P3083={simbad_id}"'})
    hits = [h["title"] for h in r.json().get("query", {}).get("search", [])]
    links = {}
    if hits:
        e = requests.get("https://www.wikidata.org/w/api.php", headers=UA, timeout=60, params={
            "action": "wbgetentities", "ids": hits[0], "props": "sitelinks", "sitefilter": "trwiki|enwiki",
            "format": "json"}).json()
        links = {k: v["title"] for k, v in e["entities"][hits[0]].get("sitelinks", {}).items()}
    print(f"[{simbad_id!r}] -> {hits[:3]} {links}")

# 5) MAST preview download URL check
print("\n=== MAST preview download ===")
uri = "mast:HST/product/x13o1101t_c0f.jpg"
r = requests.get("https://mast.stsci.edu/api/v0.1/Download/file", params={"uri": uri}, headers=UA, timeout=60)
print(r.status_code, r.headers.get("Content-Type"), len(r.content), "bytes")
