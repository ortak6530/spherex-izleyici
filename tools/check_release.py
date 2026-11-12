"""Check a SPHEREx data release before (or after) enabling it.

Usage (from the repo root):
    backend\\.venv\\Scripts\\python.exe tools\\check_release.py dr1 [--no-compare] [--out report.md]

What it checks (docs/DECISIONS.md section 4b-C):
  1. TAP: rows per obs_collection at a reference position (M31) - is the collection served?
  2. SIA2: rows for each collection listed in config/releases.toml
  3. S3: the release prefix exists; first/last planning period under level2/
  4. Sample frame: extension names, flag header style (MP_ vs MSKN), flag names, ZODIMDL, VERSION,
     compared with the known QR2 (R6) and QR3 (R7) layouts -> differences are reported
  5. Demo comparisons inside this release: M31 (expect no significant change) and Barnard's Star
     (expect a shift close to its proper motion). 3I/ATLAS needs the moving-object (MOST) view.
The script only reads; it never changes configuration or caches outside data/cache.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import re
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

import numpy as np  # noqa: E402
from astropy.io import fits  # noqa: E402

from skytracker.config_loader import releases  # noqa: E402
from skytracker.domain import flags as F  # noqa: E402
from skytracker.http import http  # noqa: E402
from skytracker.providers import spherex as S  # noqa: E402
from skytracker.services.time_compare import compare_time  # noqa: E402

M31 = (10.684708, 41.26875)
# Barnard's Star, SIMBAD J2000 + proper motion; searches use the 2026.0 position
BARNARD = {
    "ra_j2000": 269.4520769586187,
    "dec_j2000": 4.69336496657667,
    "pmra_mas_yr": -801.551,
    "pmdec_mas_yr": 10362.394,
}

KNOWN_LAYOUTS = {
    "R6 (QR2)": {
        "extensions": ["PRIMARY", "IMAGE", "FLAGS", "VARIANCE", "ZODI", "PSF", "WCS-WAVE"],
        "flag_style": "MP",
        "zodi_model": "ModifiedKelsallModelWithHPFT",
    },
    "R7 (QR3)": {
        "extensions": ["PRIMARY", "IMAGE", "FLAGS", "VARIANCE", "ZODI", "EPSF", "WCS-WAVE"],
        "flag_style": "MSK",
        "zodi_model": "KEL98_WAVESCL_V1",
    },
}
R7_FLAGS = {
    "TRANSIENT",
    "OVERFLOW",
    "SUR_ERROR",
    "NONFUNC",
    "DICHROIC",
    "MISSING_DATA",
    "HOT",
    "COLD",
    "FULLSAMPLE",
    "PHANMISS",
    "NONLINEAR",
    "PERSIST",
    "OUTLIER",
    "CROSSTALK",
    "SOURCE",
    "GHOST",
    "GHOST_FPA",
    "GHOST_EXT",
    "STREAK",
    "BLOOM",
    "SNOWBALL",
    "HALO",
}

lines: list[str] = []


def out(s: str = "") -> None:
    print(s)
    lines.append(s)


async def tap_counts(ra: float, dec: float) -> dict[str, int]:
    q = (
        "SELECT obs_collection, COUNT(*) AS n FROM spherex.obscore "
        f"WHERE CONTAINS(POINT('ICRS', {ra}, {dec}), s_region) = 1 GROUP BY obs_collection"
    )
    r = await http.get(
        "https://irsa.ipac.caltech.edu/TAP/sync",
        params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": q},
        timeout=180,
    )
    rows = [ln.split(",") for ln in r.text.strip().splitlines()[1:]]
    return {c: int(n) for c, n in rows if c}


async def s3_summary(prefix: str) -> dict:
    base = "https://nasa-irsa-spherex.s3.amazonaws.com/"
    r = await http.get(base, params={"list-type": "2", "delimiter": "/", "prefix": prefix}, timeout=60)
    dirs = re.findall(r"<Prefix>([^<]*)</Prefix>", r.text)[1:]
    first = await http.get(
        base,
        params={"list-type": "2", "delimiter": "/", "prefix": prefix + "level2/", "max-keys": "1"},
        timeout=60,
    )
    first_pp = re.findall(r"<Prefix>([^<]*)</Prefix>", first.text)[1:2]
    return {"products": [d.removeprefix(prefix).strip("/") for d in dirs], "first_level2": first_pp}


def describe(raw: bytes) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        h = fits.open(io.BytesIO(raw))
        names = [hdu.name for hdu in h]
        fh = h["FLAGS"].header
        style = (
            "MSK"
            if any(k.startswith("MSKN") for k in fh)
            else "MP"
            if any(k.startswith("MP_") for k in fh)
            else "?"
        )
        return {
            "extensions": names,
            "flag_style": style,
            "flags": sorted(F.flag_schema(fh)),
            "zodi_model": str(h["ZODI"].header.get("ZODIMDL", "")).strip(),
            "version": str(h[0].header.get("VERSION", "")).strip(),
            "bunit": str(h["IMAGE"].header.get("BUNIT", "")).strip(),
            "has_msk_masks": any(k.startswith("MSKM") for k in fh),
            "has_msk_descr": any(k.startswith("MSKD") for k in fh),
        }


def closest_pair(images, ra, dec, samples):
    visits = S.group_visits(images)
    if len(visits) < 2:
        return None
    usable = lambda v: [i for i in v["images"] if (samples.get(i.image_id) or {}).get("wavelength_um")]  # noqa: E731
    va, vb = usable(visits[0]), usable(visits[-1])
    best = None
    for a in va:
        la = samples[a.image_id]["wavelength_um"]
        b = min(vb, key=lambda i: abs(samples[i.image_id]["wavelength_um"] - la), default=None)
        if b is None:
            continue
        d = abs(samples[b.image_id]["wavelength_um"] - la)
        if best is None or d < best[2]:
            best = (a, b, d)
    return best


async def demo_compare(
    rel_id: str, name: str, ra: float, dec: float, det: int, pm: dict | None
) -> dict | None:
    images = [i for i in await S.coverage(ra, dec) if i.release == rel_id and i.detector == det]
    if not images:
        return None
    samples = await S.index_wavelengths(images, ra, dec)
    pair = closest_pair(images, ra, dec, samples)
    if not pair:
        return {"skipped": "bu sürümde tek gözlem dönemi var"}

    async def _p(*_a):
        return None

    return await compare_time(pair[0].image_id, pair[1].image_id, ra, dec, 0.1, "sub", True, pm, _p)


async def main(rel_id: str, do_compare: bool) -> int:
    rel = releases().get(rel_id)
    if rel is None:
        out(f"Bilinmeyen sürüm: {rel_id} (config/releases.toml)")
        return 2
    t0 = time.time()
    out(f"## check_release: {rel.label} ({rel_id}) — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    out(
        f"- Ayar: status={rel.status}, announced={rel.announced}, calib_family={rel.calib_family}, "
        f"SIA koleksiyonları={rel.sia_collections}"
    )

    counts = await tap_counts(*M31)
    out(f"- TAP (M31 konumu) koleksiyon satırları: {counts}")
    for c in rel.sia_collections:
        mark = "✓" if counts.get(c) else "✗"
        out(f"  - {mark} `{c}` TAP'ta {'var' if counts.get(c) else 'YOK'} ({counts.get(c, 0)} satır)")

    for c in rel.sia_collections:
        r = await http.get(
            f"{S.SIA_URL}?COLLECTION={c}&POS=circle+{M31[0]}+{M31[1]}+0.0005&RESPONSEFORMAT=VOTable",
            timeout=90,
        )
        out(f"- SIA2 `{c}` (M31): {r.text.count('<TR>')} görüntü")

    s3 = await s3_summary(rel.s3_prefix)
    out(f"- S3 `{rel.s3_prefix}`: ürünler={s3['products']}; ilk level2 dönemi={s3['first_level2']}")

    imgs = [i for i in await S.coverage(*M31) if i.release == rel_id]
    if not imgs:
        out("- ✗ Örnek kare alınamadı (bu sürüm M31'de SIA2'den görüntü döndürmüyor).")
        return 1
    sample = imgs[len(imgs) // 2]
    raw = await S.fetch_cutout_fits(sample, *M31, 0.05)
    d = describe(raw)
    out(f"- Örnek kare: `{sample.obs_id}` D{sample.detector} ({sample.date_obs[:10]}) — {sample.fits_url}")
    out(f"  - VERSION={d['version']}, BUNIT={d['bunit']}, ZODIMDL={d['zodi_model']}")
    out(f"  - Uzantılar: {d['extensions']}")
    out(
        f"  - Bayrak başlığı: {d['flag_style']} (MSKM={d['has_msk_masks']}, MSKD={d['has_msk_descr']}); "
        f"{len(d['flags'])} bayrak"
    )
    for lname, ref in KNOWN_LAYOUTS.items():
        diffs = [k for k in ("extensions", "flag_style", "zodi_model") if d[k] != ref[k]]
        out(f"  - {lname} düzeniyle fark: {', '.join(diffs) if diffs else 'yok ✓'}")
    if d["flag_style"] == "MSK":
        missing, extra = R7_FLAGS - set(d["flags"]), set(d["flags"]) - R7_FLAGS
        out(f"  - R7 bayrak listesiyle fark: eksik={sorted(missing) or '—'}, fazla={sorted(extra) or '—'}")

    if do_compare:
        out("- Demo karşılaştırmaları (yalnızca bu sürümün dönemleri arasında):")
        r = await demo_compare(rel_id, "M31", *M31, 2, None)
        if r is None or "skipped" in (r or {}):
            out(f"  - M31: atlandı ({(r or {}).get('skipped', 'görüntü yok')})")
        else:
            ch = r["photometry"]["change_normalized"] or r["photometry"]["change"]
            if ch:
                ok = abs(ch["percent"]) < 3 * ch["err_percent"]
                out(
                    f"  - M31 (D2, λ {r['a']['wavelength_um']:.3f}/{r['b']['wavelength_um']:.3f} µm): "
                    f"parlaklık farkı {ch['percent']:+.1f} ± {ch['err_percent']:.1f} % → "
                    f"{'beklenenle uyumlu (anlamlı değişim yok) ✓' if ok else 'BEKLENMEYEN değişim ✗'}"
                )
            else:
                out("  - M31: fotometri ölçülemedi (çekirdek doymuş/maskeli) — değerlendirilemedi")
            out(
                f"    normalleştirme çarpanı={r['normalization']['factor']}, uyarılar={[w['code'] for w in r['warnings']]}"
            )
        from skytracker.domain.astrometry import SEARCH_EPOCH, jyear_to_mjd, propagate

        bra, bdec = propagate(
            BARNARD["ra_j2000"],
            BARNARD["dec_j2000"],
            BARNARD["pmra_mas_yr"],
            BARNARD["pmdec_mas_yr"],
            jyear_to_mjd(SEARCH_EPOCH),
        )
        r = await demo_compare(rel_id, "Barnard", bra, bdec, 5, BARNARD)
        if r is None or "skipped" in (r or {}):
            out(f"  - Barnard: atlandı ({(r or {}).get('skipped', 'görüntü yok')})")
        elif r["shift"] and r["expected_shift"]:
            diff_px = abs(r["shift"]["px"] - r["expected_shift"]["px"])
            ok = diff_px < 0.5
            out(
                f"  - Barnard (D5, {r['dt_days']:.0f} gün): ölçülen {r['shift']['arcsec']:.2f}″ "
                f"({r['shift']['px']:.2f} px, {r['shift']['pa_deg']:.0f}°), beklenen {r['expected_shift']['arcsec']:.2f}″ "
                f"({r['expected_shift']['px']:.2f} px) → fark {diff_px:.2f} px "
                f"{'✓ uyumlu' if ok else '✗ uyumsuz'}"
            )
        else:
            out("  - Barnard: kayma ölçülemedi ✗")
        out("  - 3I/ATLAS: hareketli cisim görünümü (MOST) bu araçta henüz test edilmiyor — atlandı")
    out(f"- Süre: {time.time() - t0:.0f} sn")
    await http.aclose()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("release")
    ap.add_argument("--no-compare", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    code = asyncio.run(main(a.release, not a.no_compare))
    if a.out:
        a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.exit(code)
