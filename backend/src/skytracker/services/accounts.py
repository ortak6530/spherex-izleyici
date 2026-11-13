"""Accounts: e-mail + server-generated one-time code (DECISIONS.md §2.6, §4e-e).

- 6 digits from `secrets`, stored only as HMAC-SHA256(SECRET_KEY, email|code); valid 10 minutes;
  at most 5 attempts per code; at most 3 codes per e-mail per hour.
- Sent with the EmailJS REST API from the server, using the private key as `accessToken`.
- EMAILJS_* empty: in development the code is written ONLY to the server log; in production sending
  fails with EMAIL_NOT_CONFIGURED. The code is never part of any HTTP response.
- Signed-in browsers hold a random token in an httpOnly cookie; only its SHA-256 is stored.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..db.models import AuthSession, LoginCode, User
from ..http import UpstreamError, http
from ..settings import get_settings

log = logging.getLogger("skytracker.accounts")

EMAILJS_URL = "https://api.emailjs.com/api/v1.0/email/send"
CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
MAX_CODES_PER_HOUR = 3
SESSION_TTL = timedelta(days=30)
AUTH_COOKIE = "spx_auth"
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[A-Za-z]{2,}$")


class AccountError(Exception):
    def __init__(self, code: str, status: int = 400, **params):
        super().__init__(code)
        self.code, self.status, self.params = code, status, params


def now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes even for timezone=True columns
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def normalize_email(email: str) -> str:
    e = (email or "").strip().lower()
    if len(e) > 254 or not EMAIL_RE.match(e):
        raise AccountError("INVALID_EMAIL")
    return e


def mask_email(email: str) -> str:
    """For logs: 'ayse@example.org' -> 'a***@example.org'."""
    user, _, domain = email.partition("@")
    return f"{user[:1]}***@{domain}"


def _secret() -> bytes:
    s = get_settings()
    return (s.secret_key or "dev-only-secret-not-for-production").encode()


def code_hash(email: str, code: str) -> str:
    return hmac.new(_secret(), f"{email}|{code}".encode(), hashlib.sha256).hexdigest()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def is_admin(email: str | None) -> bool:
    admin = (get_settings().admin_email or "").strip().lower()
    return bool(admin) and (email or "").lower() == admin


def email_mode() -> str:
    """'emailjs' when all four EMAILJS_* values are set, 'server_log' in development, else 'disabled'."""
    s = get_settings()
    keys = (s.emailjs_service_id, s.emailjs_template_id, s.emailjs_public_key, s.emailjs_private_key)
    if all(k.strip() for k in keys):
        return "emailjs"
    return "disabled" if s.is_production else "server_log"


async def deliver(email: str, code: str) -> str:
    mode = email_mode()
    if mode == "disabled":
        raise AccountError("EMAIL_NOT_CONFIGURED", 503)
    if mode == "server_log":
        log.warning("DEVELOPMENT ONLY - EmailJS not configured. Code for %s: %s", mask_email(email), code)
        return mode
    s = get_settings()
    body = {
        "service_id": s.emailjs_service_id.strip(),
        "template_id": s.emailjs_template_id.strip(),
        "user_id": s.emailjs_public_key.strip(),
        "accessToken": s.emailjs_private_key.strip(),
        "template_params": {
            "to_email": email,
            "code": code,
            "valid_minutes": int(CODE_TTL.total_seconds() // 60),
            "site_url": s.public_base_url,
        },
    }
    try:
        r = await http.post(EMAILJS_URL, json=body, timeout=15, retries=1)
    except UpstreamError as e:
        log.error("EmailJS unreachable for %s: %s", mask_email(email), e.code)
        raise AccountError("EMAIL_SEND_FAILED", 502) from e
    if r.status_code != 200:
        # EmailJS explains the problem in plain text (e.g. non-browser API access disabled); log only
        log.error("EmailJS %s for %s: %s", r.status_code, mask_email(email), r.text[:200])
        raise AccountError("EMAIL_SEND_FAILED", 502)
    return mode


def codes_last_hour(db: Session, email: str) -> list[datetime]:
    since = now() - timedelta(hours=1)
    rows = db.execute(
        select(LoginCode.created_at).where(LoginCode.email == email, LoginCode.created_at >= since)
    ).scalars()
    return sorted(_aware(t) for t in rows)


async def request_code(db: Session, email: str, session_id: str, ip_hash: str | None) -> dict:
    email = normalize_email(email)
    recent = codes_last_hour(db, email)
    if len(recent) >= MAX_CODES_PER_HOUR:
        retry = int((recent[0] + timedelta(hours=1) - now()).total_seconds()) + 1
        raise AccountError("EMAIL_RATE_LIMITED", 429, retry_after_s=max(retry, 1))
    # Only the newest code is valid
    db.execute(
        update(LoginCode).where(LoginCode.email == email, LoginCode.used_at.is_(None)).values(used_at=now())
    )
    code = new_code()
    row = LoginCode(
        email=email,
        code_hash=code_hash(email, code),
        created_at=now(),
        expires_at=now() + CODE_TTL,
        attempts=0,
        session_id=session_id,
        ip_hash=ip_hash,
    )
    db.add(row)
    db.flush()
    try:
        mode = await deliver(email, code)
    except AccountError:
        db.delete(row)  # our failure must not use up the visitor's hourly sends
        db.commit()
        raise
    db.commit()
    out = {
        "ok": True,
        "expires_in_s": int(CODE_TTL.total_seconds()),
        "sends_left": MAX_CODES_PER_HOUR - len(recent) - 1,
    }
    if mode == "server_log":
        out["delivery"] = "server_log"  # development only: tells the developer where to look
    return out


def verify_code(db: Session, email: str, code: str) -> tuple[User, str]:
    email = normalize_email(email)
    code = (code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        raise AccountError("INVALID_CODE_FORMAT")
    row = db.execute(
        select(LoginCode)
        .where(LoginCode.email == email, LoginCode.used_at.is_(None))
        .order_by(LoginCode.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None or _aware(row.expires_at) <= now():
        raise AccountError("CODE_EXPIRED")
    if row.attempts >= MAX_ATTEMPTS:
        raise AccountError("CODE_LOCKED")
    row.attempts += 1
    if not hmac.compare_digest(row.code_hash, code_hash(email, code)):
        left = MAX_ATTEMPTS - row.attempts
        if left <= 0:
            row.used_at = now()
        db.commit()
        raise AccountError("CODE_LOCKED" if left <= 0 else "INVALID_CODE", attempts_left=max(left, 0))
    row.used_at = now()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email, created_at=now())
        db.add(user)
        db.flush()
    user.last_login_at = now()
    token = secrets.token_urlsafe(32)
    sess = AuthSession(token_hash=token_hash(token), user_id=user.id, created_at=now())
    sess.expires_at = now() + SESSION_TTL
    db.add(sess)
    db.commit()
    return user, token


def user_for_token(db: Session, token: str | None) -> User | None:
    if not token or len(token) > 100:
        return None
    sess = db.get(AuthSession, token_hash(token))
    if sess is None or _aware(sess.expires_at) <= now():
        return None
    if sess.last_seen_at is None or now() - _aware(sess.last_seen_at) > timedelta(minutes=5):
        sess.last_seen_at = now()
        db.commit()
    return db.get(User, sess.user_id)


def logout(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(token)))
        db.commit()


def purge_expired(db: Session) -> None:
    """Old codes and sessions are deleted (called opportunistically)."""
    db.execute(delete(LoginCode).where(LoginCode.created_at < now() - timedelta(days=1)))
    db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
    db.commit()


def user_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(User)).scalar_one()
