"""Admin panel: ADMIN_EMAIL only, users/events/feedback, releases + cache refresh, live WS feed."""

import pytest

from skytracker import cache
from skytracker.services import accounts as A
from skytracker.settings import get_settings

ADMIN = "yonetici@example.org"


@pytest.fixture
def sent(monkeypatch):
    box = []

    async def fake_deliver(email, code):
        box.append(code)
        return "server_log"

    monkeypatch.setattr(A, "deliver", fake_deliver)
    return box


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_email", ADMIN)


def login(client, sent, email):
    client.cookies.clear()
    client.get("/api/v1/health")
    client.post("/api/v1/auth/request-code", json={"email": email})
    r = client.post("/api/v1/auth/verify", json={"email": email, "code": sent[-1]})
    assert r.status_code == 200


def test_admin_endpoints_need_the_admin_email(client, sent, admin_env):
    client.cookies.clear()
    assert client.get("/api/v1/admin/summary").status_code == 401
    login(client, sent, "biri@example.org")
    r = client.get("/api/v1/admin/summary")
    assert r.status_code == 403 and r.json()["code"] == "ADMIN_ONLY"
    for path in ("/admin/users", "/admin/events", "/admin/feedback", "/admin/releases"):
        assert client.get("/api/v1" + path).status_code == 403
    assert client.post("/api/v1/admin/cache/refresh", json={"scope": "all"}).status_code == 403


def test_admin_sees_users_events_and_feedback(client, sent, admin_env):
    login(client, sent, "kullanici@example.org")
    client.cookies.set("spx_consent", "all")  # analytics consent -> server actions are logged
    client.post("/api/v1/feedback", json={"category": "bug", "message": "Kesit açılmadı, D3."})
    client.post("/api/v1/me/saved", json={"kind": "object", "ref": "m-42", "label": "M 42"})

    login(client, sent, ADMIN)
    s = client.get("/api/v1/admin/summary").json()
    assert s["users"] >= 2 and s["feedback_new"] >= 1 and "note" in s
    users = {u["email"]: u for u in client.get("/api/v1/admin/users").json()["items"]}
    assert users[ADMIN]["is_admin"] is True and users["kullanici@example.org"]["saved"] == 1

    ev = client.get("/api/v1/admin/events", params={"group": "account"}).json()["items"]
    saved = next(e for e in ev if e["type"] == "saved")
    assert saved["user"] == "kullanici@example.org" and saved["object_key"] == "m-42"
    assert "ip_hash" not in saved and len(saved["session"]) == 6

    fb = client.get("/api/v1/admin/feedback", params={"status": "new"}).json()["items"]
    mine = next(f for f in fb if f["message"] == "Kesit açılmadı, D3.")
    r = client.post(f"/api/v1/admin/feedback/{mine['id']}/status", json={"status": "done"})
    assert r.json()["status"] == "done"
    assert client.post(f"/api/v1/admin/feedback/{mine['id']}/status", json={"status": "x"}).status_code == 422


def test_releases_and_cache_refresh(client, sent, admin_env, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "cache_dir", str(tmp_path))
    cache.put_json("dr1/coverage", "k", {"a": 1})
    cache.put_json("_external/sesame", "m31", {"result": None})
    cache.put_json("_index/images", "x", {"image_id": "x"})
    login(client, sent, ADMIN)
    rel = client.get("/api/v1/admin/releases").json()
    by_id = {r["id"]: r for r in rel["releases"]}
    assert rel["default"] == "dr1" and by_id["dr1"]["cache"]["files"] == 1
    assert by_id["qr2"]["status"] == "superseded"
    assert client.post("/api/v1/admin/cache/refresh", json={"scope": "../etc"}).status_code == 400
    assert client.post("/api/v1/admin/cache/refresh", json={"scope": "_index"}).status_code == 400
    r = client.post("/api/v1/admin/cache/refresh", json={"scope": "external"}).json()
    assert r["removed"]["files"] == 1 and cache.get_json("_external/sesame", "m31", None) is None
    assert cache.get_json("dr1/coverage", "k", None) == {"a": 1}  # other scopes untouched
    client.post("/api/v1/admin/cache/refresh", json={"scope": "dr1"})
    assert cache.get_json("dr1/coverage", "k", None) is None
    assert cache.get_json("_index/images", "x", None) is not None  # only 'all' removes the index


def test_admin_ws_feed_only_for_admins_and_receives_events(client, sent, admin_env):
    login(client, sent, "meraklı@example.org")
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "subscribe", "topic": "admin"})
        assert ws.receive_json()["code"] == "FORBIDDEN_TOPIC"

    login(client, sent, ADMIN)
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "subscribe", "topic": "admin"})
        assert ws.receive_json() == {"type": "subscribed", "topic": "admin"}
        client.post("/api/v1/feedback", json={"category": "idea", "message": "Canlı akış denemesi"})
        msg = ws.receive_json()
        assert msg["type"] == "admin_event" and msg["kind"] == "feedback" and msg["category"] == "idea"
        # an ordinary logged action keeps the WS message type and carries its own type separately
        client.post("/api/v1/events", json={"events": [{"type": "search_submitted", "page": "/"}]})
        msg = ws.receive_json()
        assert msg["type"] == "admin_event" and msg["kind"] == "event"
        assert msg["event_type"] == "search_submitted" and msg["page"] == "/"
