"""Feedback button: validation, storage with context, honeypot, rate limit."""

from sqlalchemy import select

from skytracker.db import session_scope
from skytracker.db.models import Feedback


def _post(client, **kw):
    body = {"category": "idea", "message": "Daha büyük görüntüleyici olsun.", **kw}
    return client.post("/api/v1/feedback", json=body)


def _fresh(client):
    client.cookies.clear()  # new anonymous session -> fresh rate-limit bucket
    client.get("/api/v1/health")


def test_feedback_is_stored_with_context(client):
    _fresh(client)
    r = _post(
        client,
        email=" Kisi@Example.org ",
        page="/?q=M31",
        object_key="m-31",
        release_id="dr1",
        context={"view": "compare", "detector": 2, "nested": {"x": 1}},
    )
    assert r.status_code == 201 and r.json()["ok"] is True
    with session_scope() as db:
        fb = db.execute(select(Feedback).where(Feedback.id == r.json()["id"])).scalar_one()
        assert fb.category == "idea" and fb.status == "new"
        assert fb.email == "kisi@example.org"  # trimmed + lower-cased
        assert (fb.page, fb.object_key, fb.release_id) == ("/?q=M31", "m-31", "dr1")
        assert fb.context["view"] == "compare" and fb.context["detector"] == 2
        assert "nested" not in fb.context  # only flat values are kept
        assert fb.ip_hash and len(fb.ip_hash) == 32


def test_feedback_validation(client):
    _fresh(client)
    assert _post(client, category="spam").status_code == 422
    assert _post(client, message="hi").status_code == 422
    assert _post(client, message="\x00\x01   \x02").status_code == 422  # control chars only
    assert _post(client, email="not-an-email").status_code == 422
    assert _post(client, message="x" * 2001).status_code == 422


def test_feedback_honeypot_stores_nothing(client):
    _fresh(client)
    with session_scope() as db:
        before = len(db.execute(select(Feedback.id)).all())
    r = _post(client, website="http://spam.example")
    assert r.status_code == 201 and "id" not in r.json()
    with session_scope() as db:
        assert len(db.execute(select(Feedback.id)).all()) == before


def test_feedback_rate_limited_per_session(client):
    _fresh(client)
    codes = [_post(client).status_code for _ in range(4)]
    assert codes[:3] == [201, 201, 201] and codes[3] == 429
