"""Warm the caches for the demo objects by calling the site's own API, exactly as the UI does.

Render's free plan wipes the disk on every restart/deploy, so run this after a deploy and shortly
before a demo. It only reads public data; nothing is written except the server's cache files.

Usage (from the repo root; standard library only):
    backend\\.venv\\Scripts\\python.exe tools\\prewarm.py                                    # local server
    backend\\.venv\\Scripts\\python.exe tools\\prewarm.py --base https://spherex-izleyici.onrender.com
    backend\\.venv\\Scripts\\python.exe tools\\prewarm.py --only barnard luhman16

Per object it warms: name resolution, the info panel (SIMBAD + Wikipedia), same-type suggestions,
the observation list for the chosen detector, and the default time comparison (the pair the UI
picks: first vs last visit, smallest Δλ / bandwidth). Moving objects: the MOST frame list and the
object-centred cutouts of the visit the UI opens first (predicted brightest), detector D5.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# key -> (search text, detector). Detectors follow earlier live tests (docs/PROGRESS.md):
# Barnard D5 (12.5" shift DR1->QR3), WISE 0855 and Luhman 16 D6 (4.74 µm, same channel).
TARGETS: dict[str, tuple[str, int]] = {
    "3i_atlas": ("3I/ATLAS", 5),
    "barnard": ("Barnard's Star", 5),
    "wise0855": ("WISE J085510.83-071442.5", 6),
    "luhman16": ("Luhman 16", 6),
}
SIZE_DEG = 0.1
MAX_MOVING_FRAMES = 40  # same cap as the UI
JOB_TIMEOUT_S = 900


class Api:
    def __init__(self, base: str, timeout: float = 120):
        if urllib.parse.urlparse(base).scheme not in ("http", "https"):
            raise SystemExit("--base must be an http(s) address")
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())  # one anonymous session
        )
        self.opener.addheaders = [("User-Agent", "SPHEREx-Gokyuzu-Izleyici prewarm")]

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode()
        for attempt in range(6):
            url = self.base + "/api/v1" + path  # scheme checked in __init__ (http/https only)
            req = urllib.request.Request(url, data=data, method=method)  # noqa: S310
            if data is not None:
                req.add_header("Content-Type", "application/json")
            try:
                with self.opener.open(req, timeout=self.timeout) as r:
                    return json.loads(r.read() or b"{}")
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 5:  # our own rate limit: wait for the bucket to refill
                    time.sleep(15)
                    continue
                try:
                    code = json.loads(e.read()).get("code")
                except ValueError:
                    code = None
                raise RuntimeError(f"{method} {path} -> HTTP {e.code} {code or ''}".strip()) from None
        raise RuntimeError(f"{method} {path} -> still rate limited")

    def get(self, path: str) -> dict:
        return self.call("GET", path)

    def post(self, path: str, body: dict) -> dict:
        return self.call("POST", path, body)

    def job(self, first: dict) -> dict:
        """Follow {"job_id"} (HTTP polling, like the UI's fallback); a cached answer is returned as is."""
        if set(first) != {"job_id"}:
            return first
        t0 = time.time()
        while time.time() - t0 < JOB_TIMEOUT_S:
            j = self.get(f"/jobs/{first['job_id']}")
            if j["status"] == "done":
                return j["result"]
            if j["status"] == "error":
                raise RuntimeError(f"job {j['kind']} failed: {j['error']}")
            time.sleep(1.5)
        raise RuntimeError("job timed out")


# ---------- the same choices the UI makes (features/Workspace.tsx, features/MovingView.tsx) ----------


def usable(images: list[dict]) -> list[dict]:
    return [i for i in images if i.get("wavelength_um") is not None and i.get("on_detector")]


def channel_ratio(a: dict, b: dict) -> float:
    bw = ((a.get("bandwidth_um") or 0) + (b.get("bandwidth_um") or 0)) / 2
    return abs(a["wavelength_um"] - b["wavelength_um"]) / (bw or 1)


def best_pair(images_a: list[dict], images_b: list[dict]) -> tuple[dict, dict, float] | None:
    """Exposure in visit A whose closest partner in visit B has the smallest Δλ / bandwidth."""
    best = None
    cands_b = usable(images_b)
    for a in usable(images_a):
        b = min(cands_b, key=lambda x: abs(x["wavelength_um"] - a["wavelength_um"]), default=None)
        if b is None or b["image_id"] == a["image_id"]:
            continue
        r = channel_ratio(a, b)
        if best is None or r < best[2]:
            best = (a, b, r)
    return best


def brightest_visit(res: dict) -> dict | None:
    """Visit with the lowest predicted V magnitude (ties: more frames)."""
    frames = {f["image_id"]: f for f in res["frames"]}

    def score(v: dict):
        mags = [frames[i]["vmag"] for i in v["frame_ids"] if frames[i].get("vmag") is not None]
        return (min(mags) if mags else float("inf"), -len(v["frame_ids"]))

    return min(res["visits"], key=score, default=None)


# ---------- warming ----------


def log(msg: str) -> None:
    print(msg, flush=True)


def timed(label: str, fn):
    t0 = time.time()
    out = fn()
    log(f"  {label}: {time.time() - t0:.1f} s")
    return out


def warm_fixed(api: Api, target: dict, detector: int) -> None:
    if target.get("main_id"):
        info_path = f"/objects/info?main_id={q(target['main_id'])}"
        info = timed("bilgi paneli", lambda: api.job(api.get(info_path)))
        if info.get("unavailable"):
            log(f"    erişilemeyen: {', '.join(info['unavailable'])}")
        if target.get("otype"):
            path = f"/objects/similar?main_id={q(target['main_id'])}&otype={q(target['otype'])}"
            timed("aynı tür önerileri", lambda: api.job(api.get(path)))
    body = {"ra": target["ra"], "dec": target["dec"], "detector": detector, "object_key": target["key"]}
    obs = timed(f"gözlemler D{detector}", lambda: api.job(api.post("/sky/observations", body)))
    visits = obs.get("visits") or []
    log(f"    {len(visits)} dönem, {obs.get('total_images', 0)} görüntü")
    if len(visits) < 2:
        log("    karşılaştırma için iki dönem yok, atlandı")
        return
    pair = best_pair(visits[0]["images"], visits[-1]["images"])
    if not pair:
        log("    uygun kanal çifti yok, atlandı")
        return
    a, b, ratio = pair
    log(f"    çift: {a['date_obs'][:10]} -> {b['date_obs'][:10]}, Δλ/bant = {ratio:.2f}")
    cmp_body = {
        "image_a": a["image_id"],
        "image_b": b["image_id"],
        "ra": target["ra"],
        "dec": target["dec"],
        "size_deg": SIZE_DEG,
        "zodi": "sub",
        "normalize": True,
        "main_id": target.get("main_id"),
        "object_key": target["key"],
    }
    try:
        r = timed("zaman karşılaştırması", lambda: api.job(api.post("/compare/time", cmp_body)))
        shift = (r.get("shift") or {}).get("arcsec")
        log(f"    ölçülen kayma: {shift:.2f}″" if shift is not None else "    ölçülen kayma: —")
    except RuntimeError as e:  # e.g. CHANNEL_REJECT: a real answer, not a prewarm failure
        log(f"    karşılaştırma sonucu: {e}")


def warm_moving(api: Api, target: dict, detector: int) -> None:
    des = target.get("designation")
    if not des:
        log("  JPL tanımı yok, atlandı")
        return
    res = timed("MOST kareleri", lambda: api.job(api.get(f"/moving/{q(des)}/frames")))
    visit = brightest_visit(res)
    log(f"    {len(res['frames'])} kare, {len(res['visits'])} dönem")
    if not visit:
        return
    ids = set(visit["frame_ids"])
    frames = [f for f in res["frames"] if f["image_id"] in ids and f["detector"] == detector]
    frames = frames[:MAX_MOVING_FRAMES]
    log(f"    dönem {visit['start']} → {visit['end']}, D{detector}: {len(frames)} kare")

    def one(f: dict) -> bool:
        body = {"image_id": f["image_id"], "ra": f["ra"], "dec": f["dec"]}
        body |= {"size_deg": SIZE_DEG, "zodi": "sub"}
        try:
            api.job(api.post("/moving/cutout", body))
            return True
        except RuntimeError as e:
            log(f"    kare {f['obs_id']}: {e}")
            return False

    def all_frames() -> int:
        with ThreadPoolExecutor(max_workers=3) as ex:  # the UI also loads 3 at a time
            return sum(ex.map(one, frames))

    ok = timed("cisme ortalı kesitler", all_frames)
    log(f"    {ok}/{len(frames)} kesit hazır")


def q(s: str) -> str:
    return urllib.parse.quote(s, safe="")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="site address (default: local server)")
    ap.add_argument("--only", nargs="*", choices=sorted(TARGETS), help="warm only these objects")
    args = ap.parse_args()
    api = Api(args.base)
    try:
        health = api.get("/health")
    except (RuntimeError, urllib.error.URLError) as e:
        log(f"Sunucuya ulaşılamadı ({args.base}): {e}")
        return 2
    log(f"Sunucu: {args.base} · sürüm {health.get('version')} · db {health.get('db')}")
    failures = 0
    t_all = time.time()
    for key in args.only or list(TARGETS):
        text, detector = TARGETS[key]
        log(f"\n== {text}")
        try:
            r = timed("ad çözümleme", lambda text=text: api.get(f"/resolve?q={q(text)}"))
            target = r.get("target")
            if not target:
                raise RuntimeError(f"bulunamadı ({r.get('kind')})")
            log(f"    {target['name']} ({target['kind']})")
            if target["kind"] == "solar_system":
                warm_moving(api, target, detector)
            else:
                warm_fixed(api, target, detector)
        except (RuntimeError, urllib.error.URLError, TimeoutError) as e:
            failures += 1
            log(f"  HATA: {e}")
    log(f"\nBitti: {time.time() - t_all:.0f} s, {failures} hata")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
