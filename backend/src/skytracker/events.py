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
    notify_admin(
        "event",
        {
            "event_type": ev.type,  # not "type": that key is the WS message type ("admin_event")
            "object_key": ev.object_key,
            "page": ev.page,
            "release_id": ev.release_id,
            "payload": ev.payload,
            "user_id": user_id,
            "ua_family": ua_family,
        },
    )
    return ev


def notify_admin(kind: str, data: dict) -> None:
    """Push to the admin panel's live feed (no-op when no admin is watching). Never raises."""
    try:
        from .realtime import manager

        message = {**data, "type": "admin_event", "kind": kind, "ts": datetime.now(UTC).isoformat()}
        manager.publish_nowait("admin", message)
    except Exception:  # noqa: BLE001 - the live feed is a convenience
        import logging

        logging.getLogger("skytracker.events").debug("admin feed push failed", exc_info=True)


CONSENT_COOKIE = "spx_consent"  # set by the frontend when the visitor accepts the privacy notice


def _user_id(db: Session, request) -> int | None:
    """Signed-in user behind the request (accounts store only the token's SHA-256)."""
    from .db.models import AuthSession
    from .services.accounts import AUTH_COOKIE, token_hash

    token = request.cookies.get(AUTH_COOKIE)
    if not token or len(token) > 100:
        return None
    sess = db.get(AuthSession, token_hash(token))
    return sess.user_id if sess else None


def log_action(
    request,
    type: str,
    *,
    object_key: str | None = None,
    release_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Server-side action log (search, observations, cutout, download…). Respects the consent cookie.

    Downloads are always logged (admin audit) but without IP/UA unless the visitor consented.
    """
    from .db import session_scope
    from .security import client_ip, ip_hash, ua_family

    consented = request.cookies.get(CONSENT_COOKIE) == "all"
    if not consented and type != "download":
        return
    try:
        with session_scope() as db:
            record(
                db,
                type=type,
                session_id=request.state.session_id,
                user_id=_user_id(db, request),
                object_key=object_key,
                release_id=release_id,
                payload=payload,
                page=None,
                ip_hash=ip_hash(client_ip(request)) if consented else None,
                ua_family=ua_family(request.headers.get("user-agent")) if consented else None,
            )
    except Exception:  # noqa: BLE001 - logging must never break a request
        import logging

        logging.getLogger("skytracker.events").exception("could not log action %s", type)


def purge_old(db: Session, retention_days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    res = db.execute(delete(Event).where(Event.ts < cutoff))
    return res.rowcount or 0
