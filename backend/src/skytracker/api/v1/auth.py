"""Sign-in with an e-mailed one-time code; the signed-in user's object list and saved studies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db import get_db
from ...db.models import Comparison, SavedItem, User
from ...events import clean_payload, log_action
from ...realtime import _origin_allowed
from ...security import TokenBucket, client_ip, ip_hash, session_id_from
from ...services import accounts as A
from ...settings import get_settings

router = APIRouter(tags=["accounts"])
# Per browser session, on top of the per-e-mail limits in services/accounts.py
_code_limiter = TokenBucket(rate_per_min=5 / 60, burst=5)  # e-mails sent
_verify_limiter = TokenBucket(rate_per_min=2, burst=10)  # code guesses across e-mails
MAX_SAVED = 200


def _raise(e: A.AccountError):
    raise HTTPException(e.status, {"code": e.code, **e.params})


def _same_origin(request: Request) -> None:
    # Cookie-authenticated POSTs only from our own pages (SameSite=Lax + JSON already block most CSRF)
    if not _origin_allowed(request.headers.get("origin")):
        raise HTTPException(403, {"code": "FORBIDDEN_ORIGIN"})


def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    return A.user_for_token(db, request.cookies.get(A.AUTH_COOKIE))


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise HTTPException(401, {"code": "LOGIN_REQUIRED"})
    return user


def user_json(u: User) -> dict:
    return {
        "email": u.email,
        "is_admin": A.is_admin(u.email),
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


class CodeRequest(BaseModel):
    email: str = Field(max_length=254)


class VerifyRequest(BaseModel):
    email: str = Field(max_length=254)
    code: str = Field(max_length=12)


@router.get("/auth/me")
def me(user: User | None = Depends(current_user)) -> dict:
    return {"user": user_json(user) if user else None, "email_mode": A.email_mode()}


@router.post("/auth/request-code", status_code=202)
async def request_code(body: CodeRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    _same_origin(request)
    sid = session_id_from(request)
    if not _code_limiter.allow(sid):
        raise HTTPException(429, {"code": "RATE_LIMITED", "retry_after_s": _code_limiter.retry_after(sid)})
    try:
        out = await A.request_code(db, body.email, sid, ip_hash(client_ip(request)))
    except A.AccountError as e:
        # No e-mail went out (typo, per-address limit, e-mail service down): the try is not counted
        _code_limiter.refund(sid)
        _raise(e)
    A.purge_expired(db)
    log_action(request, "login_code_requested")
    return out


@router.post("/auth/verify")
def verify(body: VerifyRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _same_origin(request)
    sid = session_id_from(request)
    if not _verify_limiter.allow(sid):
        raise HTTPException(429, {"code": "RATE_LIMITED", "retry_after_s": _verify_limiter.retry_after(sid)})
    try:
        user, token = A.verify_code(db, body.email, body.code)
    except A.AccountError as e:
        _raise(e)
    response.set_cookie(
        A.AUTH_COOKIE,
        token,
        max_age=int(A.SESSION_TTL.total_seconds()),
        httponly=True,
        secure=get_settings().is_production,
        samesite="lax",
        path="/",
    )
    log_action(request, "login", payload={"new_user": user.created_at == user.last_login_at})
    return {"user": user_json(user)}


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    _same_origin(request)
    A.logout(db, request.cookies.get(A.AUTH_COOKIE))
    response.delete_cookie(A.AUTH_COOKIE, path="/")
    return {"ok": True}


# ---------- object list and saved studies ----------


class SaveRequest(BaseModel):
    kind: str = Field(pattern="^(object|comparison)$")
    ref: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=200)
    data: dict | None = None  # e.g. {"q": "M31", "d": 2} to reopen it


def item_json(i: SavedItem) -> dict:
    return {
        "id": i.id,
        "kind": i.kind,
        "ref": i.ref,
        "label": i.label,
        "data": i.data,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


@router.get("/me/saved")
def list_saved(user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(SavedItem).where(SavedItem.user_id == user.id).order_by(SavedItem.created_at.desc())
    ).scalars()
    return {"items": [item_json(i) for i in rows]}


@router.post("/me/saved", status_code=201)
def save(
    body: SaveRequest, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict:
    _same_origin(request)
    count = select(func.count()).select_from(SavedItem).where(SavedItem.user_id == user.id)
    if db.execute(count).scalar_one() >= MAX_SAVED:
        raise HTTPException(409, {"code": "SAVED_LIMIT", "limit": MAX_SAVED})
    if body.kind == "comparison":
        comp = db.get(Comparison, body.ref)
        # A study can be saved by the browser that computed it (or by its owner)
        if comp is None or (comp.session_id != session_id_from(request) and comp.user_id != user.id):
            raise HTTPException(404, {"code": "UNKNOWN_COMPARISON"})
        comp.user_id = user.id
    data = clean_payload(body.data)
    item = SavedItem(user_id=user.id, kind=body.kind, ref=body.ref, label=body.label, data=data)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(SavedItem).where(
                SavedItem.user_id == user.id, SavedItem.kind == body.kind, SavedItem.ref == body.ref
            )
        ).scalar_one()
        return {"item": item_json(existing), "already": True}
    obj = body.ref if body.kind == "object" else None
    log_action(request, "saved", object_key=obj, payload={"kind": body.kind})
    return {"item": item_json(item)}


@router.delete("/me/saved/{item_id}")
def unsave(
    item_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict:
    _same_origin(request)
    item = db.get(SavedItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(404, {"code": "NOT_FOUND"})
    db.delete(item)
    db.commit()
    return {"ok": True}
