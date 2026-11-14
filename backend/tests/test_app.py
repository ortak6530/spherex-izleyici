from sqlalchemy import select

from skytracker.db import session_scope
from skytracker.db.models import Event


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["db"] == "ok"


def test_session_cookie_is_httponly(client):
    client.cookies.clear()
    r = client.get("/api/v1/health")
    cookie = r.headers.get("set-cookie", "")
    assert "sid=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie


def test_security_headers(client):
    r = client.get("/api/v1/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_releases_endpoint(client):
    body = client.get("/api/v1/meta/releases").json()
    ids = {r["id"]: r for r in body["releases"]}
    assert body["default"] == "dr1"
    assert ids["dr1"]["status"] == "active" and ids["qr3"]["status"] == "active"
    assert ids["qr2"]["status"] == "superseded"  # cached results readable, never searched
    # DR1 was announced in November 2026 (announced = true) -> no "announcement pending" note
    assert ids["dr1"]["announced"] is True and ids["dr1"]["notice"] is None
    assert ids["qr3"]["notice"] is None
    assert body["last_update"] is None  # never invented


def test_attributions_endpoint(client):
    items = client.get("/api/v1/meta/attributions").json()["items"]
    keys = {i["key"] for i in items}
    assert {"spherex", "irsa", "cds", "jpl"} <= keys
    assert not {"hst", "jwst"} & keys  # MAST is not used (Hubble <-> Webb cancelled)


def test_events_ingest_filters_unknown_types_and_hashes_ip(client):
    r = client.post(
        "/api/v1/events",
        json={
            "events": [
                {"type": "page_view", "page": "/"},
                {"type": "drop_table_users", "page": "/"},
                {"type": "ui_action", "payload": {"button": "x", "nested": {"a": 1}}},
            ]
        },
    )
    assert r.status_code == 202
    assert r.json() == {"accepted": 2, "rejected": 1}
    with session_scope() as db:
        rows = db.execute(select(Event).order_by(Event.id.desc()).limit(2)).scalars().all()
        assert all(e.ip_hash and len(e.ip_hash) == 32 for e in rows)
        assert all("testclient" not in (e.ip_hash or "") for e in rows)
        nested = next(e for e in rows if e.type == "ui_action").payload["nested"]
        assert isinstance(nested, str)  # payloads are flattened to scalars


def test_events_batch_limit(client):
    r = client.post("/api/v1/events", json={"events": [{"type": "page_view"}] * 51})
    assert r.status_code == 422
    assert r.json() == {"code": "INVALID_INPUT"}


def test_websocket_ping_and_topics(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
        ws.send_json({"type": "subscribe", "topic": "job:abc123"})
        assert ws.receive_json() == {"type": "subscribed", "topic": "job:abc123"}
        ws.send_json({"type": "subscribe", "topic": "admin"})  # needs admin auth (later phase)
        assert ws.receive_json()["code"] == "FORBIDDEN_TOPIC"
        ws.send_text("not json")
        assert ws.receive_json()["code"] == "BAD_JSON"


def test_unknown_api_path_is_json_404(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
