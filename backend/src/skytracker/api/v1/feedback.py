"""Feedback button: stored in the database for the admin panel (never e-mailed or sent elsewhere)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ...db import get_db
from ...db.models import Feedback
from ...events import log_action
from ...security import TokenBucket, client_ip, ip_hash, session_id_from, ua_family

router = APIRouter(tags=["feedback"])
# About six messages an hour per visitor, three in a row at most
_limiter = TokenBucket(rate_per_min=0.1, burst=3)
CATEGORIES = ("bug", "idea", "data", "other")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[A-Za-z]{2,}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class FeedbackIn(BaseModel):
    category: str = Field(pattern="^(" + "|".join(CATEGORIES) + ")$")
    message: str = Field(min_length=5, max_length=2000)
    email: str | None = Field(default=None, max_length=254)
    page: str | None = Field(default=None, max_length=200)
    object_key: str | None = Field(default=None, max_length=120)
    release_id: str | None = Field(default=None, max_length=16)
    context: dict | None = None  # e.g. {"view": "moving", "detector": 5}; small, flat values only
    website: str | None = Field(default=None, max_length=200)  # honeypot: humans leave it empty

    @field_validator("message")
    @classmethod
    def _clean_message(cls, v: str) -> str:
        v = _CONTROL.sub("", v).strip()
        if len(v) < 5:
            raise ValueError("message too short")
        return v

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if not v:
            return None
        if not _EMAIL.match(v):
            raise ValueError("invalid e-mail")
        return v.lower()

    @field_validator("context")
    @classmethod
    def _small_context(cls, v: dict | None) -> dict | None:
        if not v:
            return None
        out = {}
        for k, val in list(v.items())[:12]:
            if isinstance(val, (str, int, float, bool)) or val is None:
                out[str(k)[:40]] = val[:200] if isinstance(val, str) else val
        return out or None


@router.post("/feedback", status_code=201)
def submit(fb: FeedbackIn, request: Request, db: Session = Depends(get_db)) -> dict:
    sid = session_id_from(request)
    if not _limiter.allow(sid):
        raise HTTPException(429, {"code": "RATE_LIMITED"})
    if fb.website:  # a bot filled the hidden field: answer as usual, store nothing
        return {"ok": True}
    row = Feedback(
        session_id=sid,
        category=fb.category,
        message=fb.message,
        email=fb.email,
        page=fb.page,
        object_key=fb.object_key,
        release_id=fb.release_id,
        context={**(fb.context or {}), "ua": ua_family(request.headers.get("user-agent"))},
        status="new",
        ip_hash=ip_hash(client_ip(request)),
    )
    db.add(row)
    db.commit()
    log_action(request, "feedback", object_key=fb.object_key, payload={"category": fb.category})
    return {"ok": True, "id": row.id}
