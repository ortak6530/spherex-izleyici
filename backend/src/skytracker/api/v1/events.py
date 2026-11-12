"""Client event ingestion (batched, sent with navigator.sendBeacon or fetch)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db
from ...events import CLIENT_EVENT_TYPES, record
from ...security import TokenBucket, client_ip, ip_hash, session_id_from, ua_family

router = APIRouter(tags=["events"])
_limiter = TokenBucket(rate_per_min=120, burst=60)


class ClientEvent(BaseModel):
    type: str = Field(max_length=40)
    page: str | None = Field(default=None, max_length=200)
    object_key: str | None = Field(default=None, max_length=120)
    payload: dict | None = None


class EventBatch(BaseModel):
    events: list[ClientEvent] = Field(max_length=50)


@router.post("/events", status_code=202)
def ingest(batch: EventBatch, request: Request, db: Session = Depends(get_db)) -> dict:
    sid = session_id_from(request)
    if not _limiter.allow(sid, cost=max(1, len(batch.events))):
        raise HTTPException(status_code=429, detail={"code": "RATE_LIMITED"})
    iph = ip_hash(client_ip(request))
    uaf = ua_family(request.headers.get("user-agent"))
    accepted = 0
    for ev in batch.events:
        if ev.type not in CLIENT_EVENT_TYPES:
            continue
        record(
            db,
            type=ev.type,
            session_id=sid,
            page=ev.page,
            object_key=ev.object_key,
            payload=ev.payload,
            ip_hash=iph,
            ua_family=uaf,
        )
        accepted += 1
    db.commit()
    return {"accepted": accepted, "rejected": len(batch.events) - accepted}
