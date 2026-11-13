"""Accounts: one-time e-mail code (hashed, 10 min, 5 attempts, 3/hour), EmailJS, sessions, saved items."""

import json
import re
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from skytracker.db import session_scope
from skytracker.db.models import Comparison, LoginCode
from skytracker.services import accounts as A
from skytracker.settings import get_settings

EMAIL = "Ayse.Yilmaz@Example.org"


@pytest.fixture
def sent(monkeypatch):
    """Capture codes instead of e-mailing them (the real deliver() is tested separately)."""
    box: list[tuple[str, str]] = []

    async def fake_deliver(email, code):
        box.append((email, code))
        return "server_log"

    monkeypatch.setattr(A, "deliver", fake_deliver)
    return box


@pytest.fixture(autouse=True)
def fresh_session(client):
    client.cookies.clear()
    client.get("/api/v1/health")  # new anonymous session -> fresh rate-limit buckets
    yield


def _email(tag: str) -> str:
    return f"{tag}-{EMAIL}"


def _login(client, sent, email):
    r = client.post("/api/v1/auth/request-code", json={"email": email})
    assert r.status_code == 202, r.text
    code = sent[-1][1]
    r = client.post("/api/v1/auth/verify", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    return r


def test_code_is_never_in_the_response_and_only_its_hmac_is_stored(client, sent):
    email = _email("hash")
    r = client.post("/api/v1/auth/request-code", json={"email": email})
    assert r.status_code == 202
    code = sent[-1][1]
    assert re.fullmatch(r"\d{6}", code)
    assert code not in r.text
    body = r.json()
    assert body["expires_in_s"] == 600 and body["sends_left"] == 2 and body["delivery"] == "server_log"
    with session_scope() as db:
        row = db.execute(select(LoginCode).where(LoginCode.email == email.lower())).scalar_one()
        assert row.code_hash == A.code_hash(email.lower(), code) and code not in row.code_hash
        assert len(row.code_hash) == 64


def test_verify_sets_httponly_cookie_and_me_shows_user(client, sent, monkeypatch):
    email = _email("me")
    monkeypatch.setattr(get_settings(), "admin_email", email.upper())
    r = _login(client, sent, email)
    cookie = r.headers["set-cookie"]
    assert A.AUTH_COOKIE + "=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    me = client.get("/api/v1/auth/me").json()["user"]
    assert me["email"] == email.lower() and me["is_admin"] is True
    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").json()["user"] is None


def test_wrong_codes_lock_after_five_attempts(client, sent):
    email = _email("lock")
    client.post("/api/v1/auth/request-code", json={"email": email})
    good = sent[-1][1]
    bad = "000000" if good != "000000" else "111111"
    lefts = []
    for _ in range(4):
        r = client.post("/api/v1/auth/verify", json={"email": email, "code": bad})
        assert r.status_code == 400 and r.json()["code"] == "INVALID_CODE"
        lefts.append(r.json()["attempts_left"])
    assert lefts == [4, 3, 2, 1]
    r = client.post("/api/v1/auth/verify", json={"email": email, "code": bad})
    assert r.json()["code"] == "CODE_LOCKED"
    r = client.post("/api/v1/auth/verify", json={"email": email, "code": good})
    assert r.status_code == 400  # the code is dead after the 5th wrong guess


def test_at_most_three_codes_per_email_per_hour(client, sent):
    email = _email("rate")
    codes = [client.post("/api/v1/auth/request-code", json={"email": email}).status_code for _ in range(3)]
    assert codes == [202, 202, 202]
    r = client.post("/api/v1/auth/request-code", json={"email": email})
    assert r.status_code == 429 and r.json()["code"] == "EMAIL_RATE_LIMITED"
    assert 0 < r.json()["retry_after_s"] <= 3600


def test_only_the_newest_code_is_valid_and_codes_expire(client, sent):
    email = _email("exp")
    client.post("/api/v1/auth/request-code", json={"email": email})
    first = sent[-1][1]
    client.post("/api/v1/auth/request-code", json={"email": email})
    second = sent[-1][1]
    if first != second:
        r = client.post("/api/v1/auth/verify", json={"email": email, "code": first})
        assert r.status_code == 400
    with session_scope() as db:
        db.execute(
            update(LoginCode)
            .where(LoginCode.email == email.lower(), LoginCode.used_at.is_(None))
            .values(expires_at=A.now() - timedelta(seconds=1))
        )
    r = client.post("/api/v1/auth/verify", json={"email": email, "code": second})
    assert r.json()["code"] == "CODE_EXPIRED"


def test_input_validation(client, sent):
    r = client.post("/api/v1/auth/request-code", json={"email": "not-an-email"})
    assert r.json()["code"] == "INVALID_EMAIL"
    r = client.post("/api/v1/auth/verify", json={"email": _email("v"), "code": "12ab56"})
    assert r.json()["code"] == "INVALID_CODE_FORMAT"


def test_production_without_emailjs_refuses_and_never_logs_the_code(client, monkeypatch, caplog):
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "production")
    for k in ("emailjs_service_id", "emailjs_template_id", "emailjs_public_key", "emailjs_private_key"):
        monkeypatch.setattr(s, k, "")
    assert A.email_mode() == "disabled"
    r = client.post(
        "/api/v1/auth/request-code",
        json={"email": _email("prod")},
        headers={"Origin": s.public_base_url},
    )
    assert r.status_code == 503 and r.json()["code"] == "EMAIL_NOT_CONFIGURED"
    assert not re.search(r"\b\d{6}\b", caplog.text)
    with session_scope() as db:  # the failed send does not use up an hourly slot
        assert db.execute(select(LoginCode).where(LoginCode.email == _email("prod").lower())).first() is None


def test_emailjs_request_shape(monkeypatch):
    import asyncio

    s = get_settings()
    for k, v in {
        "emailjs_service_id": "service_x",
        "emailjs_template_id": "template_y",
        "emailjs_public_key": "pub",
        "emailjs_private_key": "priv",
    }.items():
        monkeypatch.setattr(s, k, v)
    calls = []

    class R:
        status_code = 200
        text = "OK"

    async def fake_post(url, **kw):
        calls.append((url, kw))
        return R()

    monkeypatch.setattr(A.http, "post", fake_post)
    assert asyncio.run(A.deliver("kisi@example.org", "123456")) == "emailjs"
    url, kw = calls[0]
    assert url == "https://api.emailjs.com/api/v1.0/email/send"
    body = kw["json"]
    assert body["service_id"] == "service_x" and body["template_id"] == "template_y"
    assert body["user_id"] == "pub" and body["accessToken"] == "priv"
    assert body["template_params"] == {
        "to_email": "kisi@example.org",
        "code": "123456",
        "valid_minutes": 10,
        "site_url": s.public_base_url,
    }

    R.status_code, R.text = 403, "API calls are disabled for non-browser applications"
    with pytest.raises(A.AccountError) as e:
        asyncio.run(A.deliver("kisi@example.org", "123456"))
    assert e.value.code == "EMAIL_SEND_FAILED" and e.value.status == 502


def test_failed_sends_do_not_use_up_the_browser_limit(client, monkeypatch):
    # Regression (2026-11-14): with EmailJS failing, the 6th try said "too many attempts"
    # instead of the real problem, although no e-mail had been sent.
    async def failing(email, code):
        raise A.AccountError("EMAIL_SEND_FAILED", 502)

    monkeypatch.setattr(A, "deliver", failing)
    codes = [
        client.post("/api/v1/auth/request-code", json={"email": _email(f"fail{i}")}).json()["code"]
        for i in range(7)
    ]
    assert codes == ["EMAIL_SEND_FAILED"] * 7


def test_browser_limit_reports_when_to_retry(client, sent):
    codes = [
        client.post("/api/v1/auth/request-code", json={"email": _email(f"many{i}")}).status_code
        for i in range(5)
    ]
    assert codes == [202] * 5
    r = client.post("/api/v1/auth/request-code", json={"email": _email("many5")})
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"
    assert 600 < r.json()["retry_after_s"] <= 721  # one new try every 12 minutes


def test_saved_items_need_login_and_belong_to_their_owner(client, sent):
    assert client.get("/api/v1/me/saved").status_code == 401
    _login(client, sent, _email("owner"))
    body = {"kind": "object", "ref": "m-31", "label": "M 31", "data": {"q": "M31", "d": 2, "x": {"y": 1}}}
    r = client.post("/api/v1/me/saved", json=body)
    assert r.status_code == 201
    item = r.json()["item"]
    assert item["data"]["q"] == "M31" and item["data"]["x"] == "{'y': 1}"  # flattened, never nested
    assert client.post("/api/v1/me/saved", json=body).json()["already"] is True
    assert [i["ref"] for i in client.get("/api/v1/me/saved").json()["items"]] == ["m-31"]
    r = client.post("/api/v1/me/saved", json={"kind": "comparison", "ref": "nope", "label": "x"})
    assert r.status_code == 404

    client.cookies.clear()
    _login(client, sent, _email("other"))
    assert client.delete(f"/api/v1/me/saved/{item['id']}").status_code == 404
    assert client.get("/api/v1/me/saved").json()["items"] == []


def test_saving_a_comparison_from_this_browser(client, sent):
    _login(client, sent, _email("cmp"))
    sid = client.cookies.get("sid")
    with session_scope() as db:
        db.add(Comparison(id="cafe0001", session_id=sid, kind="time", object_key="m-31", params={}, result={}))  # noqa: E501
    r = client.post("/api/v1/me/saved", json={"kind": "comparison", "ref": "cafe0001", "label": "M 31 zaman"})
    assert r.status_code == 201
    with session_scope() as db:
        assert db.get(Comparison, "cafe0001").user_id is not None


def test_cross_site_posts_are_refused_in_production(client, sent, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    evil = {"Origin": "https://evil.example"}
    r = client.post("/api/v1/auth/request-code", json={"email": _email("csrf")}, headers=evil)
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN_ORIGIN"
    assert json.loads(r.text) == {"code": "FORBIDDEN_ORIGIN"}
