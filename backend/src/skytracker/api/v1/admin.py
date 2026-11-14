"""Admin panel (ADMIN_EMAIL only): users, activity, feedback, data releases and cache refresh.

The live activity feed is the WebSocket topic "admin" (realtime.py); these endpoints give the same
data over HTTP, so the panel also works when the socket is down. IP hashes are never shown.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import cache
from ...config_loader import releases
from ...db import get_db
from ...db.models import Event, Feedback, SavedItem, User
from ...events import log_action
from ...services import accounts as A
from .auth import _same_origin, current_user

router = APIRouter(prefix="/admin", tags=["admin"])
FEEDBACK_STATUS = ("new", "read", "done")
ACTIVITY_TYPES = {
    "search": ["search", "search_submitted"],
    "compare": ["compare_time", "compare_objects", "observations", "cutout", "moving_frames", "spectrum"],
    "download": ["download"],
    "account": ["login", "login_code_requested", "saved"],
    "feedback": ["feedback"],
    "assistant": ["assistant_question"],  # no question text is ever stored
}


def require_admin(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise HTTPException(401, {"code": "LOGIN_REQUIRED"})
    if not A.is_admin(user.email):
        raise HTTPException(403, {"code": "ADMIN_ONLY"})
    return user


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


@router.get("/summary")
def summary(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    since = A.now() - timedelta(hours=24)
    by_type = dict(
        db.execute(select(Event.type, func.count()).where(Event.ts >= since).group_by(Event.type)).all()
    )
    return {
        "users": db.execute(select(func.count()).select_from(User)).scalar_one(),
        "events_24h": sum(by_type.values()),
        "events_24h_by_type": by_type,
        "sessions_24h": db.execute(
            select(func.count(func.distinct(Event.session_id))).where(Event.ts >= since)
        ).scalar_one(),
        "feedback_new": db.execute(
            select(func.count()).select_from(Feedback).where(Feedback.status == "new")
        ).scalar_one(),
        "email_mode": A.email_mode(),
        "note": (
            "Olaylar yalnızca gizlilik bildirimini kabul eden ziyaretçiler için kaydedilir "
            "(indirmeler ve geri bildirimler hariç)."
        ),
    }


@router.get("/users")
def users(
    _: User = Depends(require_admin), db: Session = Depends(get_db), limit: int = Query(200, ge=1, le=1000)
) -> dict:
    saved = dict(db.execute(select(SavedItem.user_id, func.count()).group_by(SavedItem.user_id)).all())
    events = dict(
        db.execute(
            select(Event.user_id, func.count()).where(Event.user_id.is_not(None)).group_by(Event.user_id)
        ).all()
    )
    rows = db.execute(select(User).order_by(User.created_at.desc()).limit(limit)).scalars()
    return {
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "is_admin": A.is_admin(u.email),
                "created_at": _iso(u.created_at),
                "last_login_at": _iso(u.last_login_at),
                "saved": saved.get(u.id, 0),
                "events": events.get(u.id, 0),
            }
            for u in rows
        ]
    }


@router.get("/events")
def events(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    group: str | None = Query(None, pattern="^(" + "|".join(ACTIVITY_TYPES) + ")$"),
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    q = select(Event).order_by(Event.id.desc()).limit(limit)
    if group:
        q = q.where(Event.type.in_(ACTIVITY_TYPES[group]))
    if before_id:
        q = q.where(Event.id < before_id)
    emails = dict(db.execute(select(User.id, User.email)).all())
    return {
        "items": [
            {
                "id": e.id,
                "ts": _iso(e.ts),
                "type": e.type,
                "object_key": e.object_key,
                "page": e.page,
                "release_id": e.release_id,
                "payload": e.payload,
                "ua_family": e.ua_family,
                "user": emails.get(e.user_id) if e.user_id else None,
                "session": e.session_id[:6],  # short prefix: tells visits apart without exposing the cookie
            }
            for e in db.execute(q).scalars()
        ],
        "groups": list(ACTIVITY_TYPES),
    }


@router.get("/feedback")
def feedback(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    status: str | None = Query(None, pattern="^(new|read|done)$"),
    limit: int = Query(200, ge=1, le=1000),
) -> dict:
    q = select(Feedback).order_by(Feedback.created_at.desc()).limit(limit)
    if status:
        q = q.where(Feedback.status == status)
    return {
        "items": [
            {
                "id": f.id,
                "created_at": _iso(f.created_at),
                "category": f.category,
                "message": f.message,
                "email": f.email,
                "page": f.page,
                "object_key": f.object_key,
                "release_id": f.release_id,
                "context": f.context,
                "status": f.status,
            }
            for f in db.execute(q).scalars()
        ]
    }


class FeedbackStatus(BaseModel):
    status: str = Field(pattern="^(new|read|done)$")


@router.post("/feedback/{fid}/status")
def set_feedback_status(
    fid: int,
    body: FeedbackStatus,
    request: Request,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    _same_origin(request)
    f = db.get(Feedback, fid)
    if f is None:
        raise HTTPException(404, {"code": "NOT_FOUND"})
    f.status = body.status
    db.commit()
    return {"ok": True, "id": fid, "status": f.status}


@router.get("/releases")
def data_releases(_: User = Depends(require_admin)) -> dict:
    """Release settings come from config/releases.toml (switching is done there, by design)."""
    sizes = cache.stats()
    cfg = releases()
    return {
        "default": cfg.default_release,
        "releases": [
            {
                "id": r.id,
                "label": r.label,
                "status": r.status,
                "announced": r.announced,
                "calib_family": r.calib_family,
                "doi": r.doi or None,
                "sia_collections": r.sia_collections,
                "cache": sizes.get(r.id, {"files": 0, "bytes": 0, "newest": None}),
            }
            for r in cfg.release
        ],
        "cache": sizes,
        "config_file": "config/releases.toml",
    }


class CacheRefresh(BaseModel):
    scope: str = Field(max_length=32)


@router.post("/cache/refresh")
def refresh_cache(body: CacheRefresh, request: Request, _: User = Depends(require_admin)) -> dict:
    """Delete a cache scope; the next visitor (or tools/prewarm.py) fetches fresh data from IRSA etc."""
    _same_origin(request)
    allowed = {"all", "external"} | {r.id for r in releases().release}
    if body.scope not in allowed:
        raise HTTPException(400, {"code": "UNKNOWN_SCOPE", "allowed": sorted(allowed)})
    removed = cache.clear(body.scope)
    log_action(request, "cache_refresh", payload={"scope": body.scope, "files": removed["files"]})
    return {"ok": True, "scope": body.scope, "removed": removed}
