"""Phase 0 verification: SIMBAD outage page text and alternative SIMBAD interfaces."""
import re
import requests

UA = {"User-Agent": "spherex-sky-tracker-phase0/0.1 (verification script)"}
r = requests.get("https://simbad.cds.unistra.fr/simbad/sim-tap/sync", headers=UA, timeout=30)
txt = re.sub(r"<style.*?</style>|<script.*?</script>", "", r.text, flags=re.S)
txt = re.sub(r"<[^>]+>", " ", txt)
print("TAP 404 page text:", re.sub(r"\s+", " ", txt).strip()[:600])

tests = {
    "sim-id votable": ("https://simbad.cds.unistra.fr/simbad/sim-id",
                       {"Ident": "M31", "output.format": "votable"}),
    "sim-script": ("https://simbad.cds.unistra.fr/simbad/sim-script",
                   {"script": "format object \"%IDLIST(1) | %OTYPE(S) | %SP(S) | %PLX(V) | %RV(Z)\"\nM31"}),
    "simbad home": ("https://simbad.cds.unistra.fr/simbad/", {}),
    "cds home": ("https://cds.unistra.fr/", {}),
    "vizier tap": ("https://tapvizier.cds.unistra.fr/TAPVizieR/tap/capabilities", {}),
}
for k, (u, p) in tests.items():
    try:
        r = requests.get(u, params=p, headers=UA, timeout=30)
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))[:220]
        print(f"[{k}] {r.status_code} {r.headers.get('Content-Type')} {len(r.content)}B :: {body}")
    except Exception as e:  # noqa: BLE001
        print(f"[{k}] ERROR {type(e).__name__}: {e}")
