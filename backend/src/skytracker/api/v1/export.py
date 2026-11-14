"""Excel download: POST /export/xlsx starts a job that gathers each object's data; GET /export/<id> serves
the file to the same browser. Guests export one object; signed-in users several (their saved list).

Data comes from the same (cached) sources as the site: the query is resolved again on the server,
observations from SIA2 coverage, comparisons from the `comparison` table (this browser's or the
user's own), moving-object frames from IRSA MOST. Downloads are always logged (admin feed).
"""

from __future__ import annotations

import datetime as dt
import secrets
import time
import urllib.parse

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select

from ... import cache, jobs
from ...config_loader import attributions, releases
from ...db import session_scope
from ...db.models import Comparison
from ...domain.coords import CoordinateError
from ...events import _user_id, log_action
from ...http import UpstreamError
from ...providers import most
from ...providers import spherex as S
from ...security import TokenBucket
from ...services import export_xlsx as X
from ...settings import get_settings
from .objects import DAY, build_info
from .resolve import resolve_target
from .sky import approx_channel

router = APIRouter(prefix="/export", tags=["export"])
_limiter = TokenBucket(rate_per_min=6, burst=3)
MAX_OBJECTS_GUEST = 1
MAX_OBJECTS_USER = 20
MAX_COMPARISONS = 25
FILE_TTL_S = 900
MAX_FILES = 30
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_files: dict[str, dict] = {}


class ExportItem(BaseModel):
    q: str = Field(min_length=1, max_length=100)  # the search query that opens the object
    d: int = Field(default=2, ge=1, le=6)  # detector shown on the site (λ is computed for it)


class ExportFilters(BaseModel):
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    releases: list[str] | None = Field(default=None, max_length=10)
    lam_min_um: float | None = Field(default=None, ge=0.5, le=5.5)
    lam_max_um: float | None = Field(default=None, ge=0.5, le=5.5)

    @field_validator("releases")
    @classmethod
    def _known(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        known = {r.id for r in releases().release}
        if any(r not in known for r in v):
            raise ValueError("unknown release")
        return v

    def text(self) -> str | None:
        parts = []
        if self.date_from or self.date_to:
            parts.append(f"tarih {self.date_from or '…'} – {self.date_to or '…'}")
        if self.releases:
            parts.append("sürüm " + ", ".join(self.releases))
        if self.lam_min_um is not None or self.lam_max_um is not None:
            parts.append(f"λ {self.lam_min_um or '…'} – {self.lam_max_um or '…'} µm")
        return "; ".join(parts) or None

    def keep(
        self, date_obs: str | None, release: str | None, lam: float | None, use_lam: bool = True
    ) -> bool:
        day = (date_obs or "")[:10]
        if self.date_from and (not day or day < self.date_from.isoformat()):
            return False
        if self.date_to and (not day or day > self.date_to.isoformat()):
            return False
        if self.releases and release not in self.releases:
            return False
        if use_lam and (self.lam_min_um is not None or self.lam_max_um is not None):
            if lam is None:
                return False
            if self.lam_min_um is not None and lam < self.lam_min_um:
                return False
            if self.lam_max_um is not None and lam > self.lam_max_um:
                return False
        return True


class ExportRequest(BaseModel):
    items: list[ExportItem] = Field(min_length=1, max_length=MAX_OBJECTS_USER)
    filters: ExportFilters = Field(default_factory=ExportFilters)


def _prune() -> None:
    now = time.time()
    for k in [k for k, v in _files.items() if now - v["created"] > FILE_TTL_S]:
        _files.pop(k, None)
    while len(_files) > MAX_FILES:
        _files.pop(next(iter(_files)))


# ---------- gathering ----------


async def _observations(t: dict, detector: int, f: ExportFilters, progress) -> tuple[list[list], list[str]]:
    images = await S.coverage(t["ra"], t["dec"], progress)
    if not images:
        return [], ["SPHEREx bu konumu henüz gözlememiş (etkin veri sürümlerinde)."]
    shown = [i for i in images if i.detector == detector]
    samples = await S.index_wavelengths(shown, t["ra"], t["dec"], progress)
    label = {}
    for v in S.group_visits(images):
        for i in v["images"]:
            label[i.image_id] = v["label"]
    rows = []
    for i in sorted(images, key=lambda i: (i.t_start_mjd, i.detector)):
        s = samples.get(i.image_id) if i.detector == detector else S.cached_sample(i, t["ra"], t["dec"])
        s = s or {}
        lam = s.get("wavelength_um")
        if not f.keep(i.date_obs, i.release, lam):
            continue
        rows.append(
            [
                i.date_obs,
                i.t_start_mjd,
                label.get(i.image_id),
                i.release,
                f"D{i.detector}",
                lam,
                s.get("bandwidth_um"),
                approx_channel(lam, i.em_min_um, i.em_max_um) if lam else None,
                f"{i.em_min_um:.3f}–{i.em_max_um:.3f}",
                X.yes_no(s.get("on_detector")),
                i.obs_id,
                s.get("pipeline_version"),
                i.fits_url,
            ]
        )
    return rows, []


def _comparisons(key: str, session_id: str, user_id: int | None) -> tuple[list[dict], list[dict]]:
    owner = Comparison.session_id == session_id
    if user_id is not None:
        owner = or_(owner, Comparison.user_id == user_id)
    with session_scope() as db:
        rows = db.execute(
            select(Comparison)
            .where(Comparison.object_key == key, owner)
            .order_by(Comparison.created_at.desc())
            .limit(MAX_COMPARISONS)
        ).scalars()
        out = []
        for c in rows:
            r = dict(c.result or {})
            r["_created_at"] = c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else None
            r["_kind"] = c.kind
            out.append(r)
    return [r for r in out if r["_kind"] == "time"], [r for r in out if r["_kind"] == "object"]


async def collect(item: ExportItem, f: ExportFilters, session_id: str, user_id: int | None, progress) -> dict:
    out: dict = {"name": item.q, "notes": [], "n_observations": 0}
    try:
        t = await resolve_target(item.q)
    except CoordinateError:
        t = None
    if t is None:
        out["notes"].append("Cisim çözümlenemedi (ad bulunamadı ya da ad çözümleme servisi yanıt vermedi).")
        return out
    out["target"], out["name"] = t, t["name"]
    out["time_comparisons"], out["object_comparisons"] = _comparisons(t["key"], session_id, user_id)

    if t["kind"] == "object" and t.get("main_id"):
        info = cache.get_json("_external/objinfo", t["main_id"], DAY)
        if info is None:
            try:
                info = await build_info(t["main_id"], progress)
            except Exception:  # noqa: BLE001 - the export still works without the info panel
                info = None
        out["info"] = info
        if info and info.get("unavailable"):
            out["notes"].append("Şu an erişilemeyen kaynak: " + ", ".join(info["unavailable"]) + ".")

    if t["kind"] == "solar_system":
        des = t.get("designation")
        if not des:
            out["notes"].append("JPL tanımı yok; hareket kareleri alınamadı.")
            return out
        try:
            m = await most.moving_frames(des, most.MISSION_START, dt.datetime.now(dt.UTC).date().isoformat())
        except most.MostNameError:
            out["notes"].append("IRSA MOST bu tanımı bulamadı.")
            return out
        except UpstreamError:
            out["notes"].append("IRSA MOST şu an yanıt vermiyor; hareket kareleri eklenemedi.")
            return out
        m["frames"] = [fr for fr in m["frames"] if f.keep(fr.get("date_obs"), fr.get("release"), None, False)]
        out["moving"] = m
        out["n_observations"] = len(m["frames"])
        visit = {fid: v["label"] for v in m.get("visits") or [] for fid in v["frame_ids"]}
        out["observations"] = [
            [
                fr.get("date_obs"),
                fr.get("mjd"),
                visit.get(fr.get("image_id")),
                fr.get("release"),
                f"D{fr.get('detector')}",
                None,
                None,
                None,
                "{:.3f}–{:.3f}".format(*most.DETECTOR_RANGE_UM[fr["detector"]])
                if fr.get("detector") in most.DETECTOR_RANGE_UM
                else None,
                "evet",
                fr.get("obs_id"),
                None,
                fr.get("fits_url"),
            ]
            for fr in m["frames"]
        ]
        if f.lam_min_um is not None or f.lam_max_um is not None:
            out["notes"].append("λ süzgeci hareketli cisim karelerine uygulanmadı (λ hesaplanmıyor).")
        return out

    try:
        rows, notes = await _observations(t, item.d, f, progress)
    except UpstreamError:
        rows, notes = [], ["IRSA şu an yanıt vermiyor; gözlemler eklenemedi."]
    out["observations"], out["n_observations"] = rows, len(rows)
    out["notes"] += notes
    return out


def _sources(objects: list[dict]) -> list[dict]:
    """Acknowledgements of the providers this file's data came from (verbatim, attributions.toml)."""
    keys = {"spherex", "irsa"}
    for o in objects:
        info, t = o.get("info") or {}, o.get("target") or {}
        if t.get("kind") == "object" or info.get("simbad"):
            keys.add("cds")
        if info.get("wikipedia"):
            keys.add("wikipedia")
        if t.get("kind") == "solar_system":
            keys.add("jpl")
    keys.add("astropy")
    return [i for i in attributions().get("item", []) if i.get("key") in keys]


# ---------- endpoints ----------


@router.post("/xlsx")
async def start_export(req: ExportRequest, request: Request) -> dict:
    sid = request.state.session_id
    with session_scope() as db:
        uid = _user_id(db, request)
    if uid is None and len(req.items) > MAX_OBJECTS_GUEST:
        raise HTTPException(401, {"code": "LOGIN_REQUIRED_MULTI"})
    if not _limiter.allow(sid):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    f = req.filters

    async def run(progress):
        objects = []
        n = len(req.items)
        for idx, item in enumerate(req.items, start=1):
            await progress("export_object", {"i": idx, "n": n, "name": item.q})
            objects.append(await collect(item, f, sid, uid, progress))
        await progress("export_build", {})
        now = dt.datetime.now(dt.UTC)
        meta = {
            "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "site_url": get_settings().public_base_url,
            "filters_text": f.text(),
        }
        data, counts = X.build_workbook(objects, meta, _sources(objects))
        filename = X.filename_for([o["name"] for o in objects], now.date())
        _prune()
        file_id = secrets.token_urlsafe(16)
        _files[file_id] = {
            "data": data,
            "filename": filename,
            "session_id": sid,
            "created": time.time(),
            "objects": [(o.get("target") or {}).get("key") or o["name"] for o in objects],
            "rows": counts,
        }
        return {"file_id": file_id, "filename": filename, "size_bytes": len(data), "rows": counts}

    return {"job_id": jobs.start("export_xlsx", run)}


@router.get("/{file_id}")
def download(file_id: str, request: Request) -> Response:
    _prune()
    entry = _files.get(file_id)
    # Only the browser that asked for the file can fetch it (the id is also unguessable)
    if entry is None or entry["session_id"] != request.state.session_id:
        raise HTTPException(404, {"code": "EXPORT_EXPIRED"})
    objs = entry["objects"]
    log_action(
        request,
        "download",
        object_key=objs[0] if len(objs) == 1 else None,
        payload={
            "format": "xlsx",
            "objects": len(objs),
            "names": ", ".join(objs),
            "filename": entry["filename"],
            "rows": sum(entry["rows"].values()),
        },
    )
    quoted = urllib.parse.quote(entry["filename"])
    return Response(
        entry["data"],
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": f"attachment; filename=\"{entry['filename']}\"; filename*=UTF-8''{quoted}",
            "Cache-Control": "no-store",
        },
    )
