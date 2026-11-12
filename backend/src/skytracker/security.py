"""Anonymous session cookie, privacy-preserving request fingerprints, security headers, rate limiting."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .settings import get_settings

SESSION_COOKIE = "sid"
SESSION_MAX_AGE = 90 * 24 * 3600  # matches the 90-day event retention
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")


def new_session_id() -> str:
    return secrets.token_urlsafe(24)


def session_id_from(request: Request) -> str:
    """Session id assigned by SessionMiddleware (always present on the request state)."""
    return request.state.session_id


def client_ip(request: Request) -> str:
    # uvicorn runs with --proxy-headers on Render, so request.client is the real client address
    return request.client.host if request.client else "0.0.0.0"  # noqa: S104 - placeholder, never bound


def ip_hash(ip: str, when: datetime | None = None) -> str:
    """Salted, daily-rotating HMAC of the IP. Raw IPs are never stored (KVKK)."""
    salt = get_settings().ip_hash_salt or get_settings().secret_key or "dev-only-salt"
    day = (when or datetime.now(UTC)).strftime("%Y-%m-%d")
    return hmac.new(f"{salt}|{day}".encode(), ip.encode(), hashlib.sha256).hexdigest()[:32]


_UA_RULES = [
    ("edge", re.compile(r"Edg/")),
    ("opera", re.compile(r"OPR/|Opera")),
    ("samsung", re.compile(r"SamsungBrowser")),
    ("firefox", re.compile(r"Firefox/")),
    ("chrome", re.compile(r"Chrome/|CriOS/")),
    ("safari", re.compile(r"Safari/")),
    ("bot", re.compile(r"bot|crawl|spider|curl|python|httpx", re.I)),
]


def ua_family(ua: str | None) -> str:
    if not ua:
        return "unknown"
    fam = next((name for name, rx in _UA_RULES if rx.search(ua)), "other")
    mobile = "-mobile" if re.search(r"Mobi|Android|iPhone|iPad", ua) else ""
    return (fam + mobile)[:32]


class SessionMiddleware(BaseHTTPMiddleware):
    """Assigns an anonymous, random session id in an httpOnly cookie."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        sid = request.cookies.get(SESSION_COOKIE)
        is_new = not (sid and _SID_RE.match(sid))
        if is_new:
            sid = new_session_id()
        request.state.session_id = sid
        response = await call_next(request)
        if is_new:
            response.set_cookie(
                SESSION_COOKIE,
                sid,
                max_age=SESSION_MAX_AGE,
                httponly=True,
                secure=get_settings().is_production,
                samesite="lax",
                path="/",
            )
        return response


CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",  # framer-motion writes inline style attributes
        "img-src 'self' data: blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "form-action 'self'",
    ]
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if get_settings().is_production:
            h.setdefault("Content-Security-Policy", CSP)
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class TokenBucket:
    """Small in-process rate limiter (single Render instance, so no shared store is needed)."""

    def __init__(self, rate_per_min: float, burst: int):
        self.rate = rate_per_min / 60.0
        self.burst = burst
        self._state: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, cost: float = 1.0) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._state.get(key, (float(self.burst), now))
            tokens = min(self.burst, tokens + (now - last) * self.rate)
            ok = tokens >= cost
            self._state[key] = (tokens - cost if ok else tokens, now)
            if len(self._state) > 50_000:  # crude memory bound
                self._state.clear()
            return ok
