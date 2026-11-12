"""Event log helpers: recording, the allowed event types, retention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .db.models import Event

# Client-sent event types. Server-side actions (search, compare, download…) are logged by the
# endpoints themselves with their own types.
CLIENT_EVENT_TYPES = {
    "page_view",
    "privacy_consent",
    "ui_action",
    "search_submitted",
    "view_changed",
    "client_error",
}

MAX_PAYLOAD_KEYS = 20
MAX_STR = 300


def clean_payload(payload: dict | None) -> dict | None:
    """Keep payloads small and flat: scalar values only, strings truncated."""
    if not payload:
        return None
    out: dict = {}
    for k, v in list(payload.items())[:MAX_PAYLOAD_KEYS]:
        key = str(k)[:40]
        if isinstance(v, bool | int | float) or v is None:
            out[key] = v
        else:
            out[key] = str(v)[:MAX_STR]
    return out


def record(
    db: Session,
    *,
    type: str,
    session_id: str,
    user_id: int | None = None,
    page: str | None = None,
    object_key: str | None = None,
    release_id: str | None = None,
    payload: dict | None = None,
    ip_hash: str | None = None,
    ua_family: str | None = None,
) -> Event:
    ev = Event(
        type=type[:40],
        session_id=session_id,
        user_id=user_id,
        page=(page or None) and page[:200],
        object_key=(object_key or None) and object_key[:120],
        release_id=release_id,
        payload=clean_payload(payload),
        ip_hash=ip_hash,
        ua_family=ua_family,
    )
    db.add(ev)
    return ev


def purge_old(db: Session, retention_days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    res = db.execute(delete(Event).where(Event.ts < cutoff))
    return res.rowcount or 0
