"""ORM models. Phase 1: event log only; later phases add tables via Alembic migrations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Event(Base):
    """One user action. Anonymous session id from the start; user_id once accounts exist."""

    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    page: Mapped[str | None] = mapped_column(String(200), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    release_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ua_family: Mapped[str | None] = mapped_column(String(32), nullable=True)


class User(Base):
    """Account = verified e-mail address. The admin role is not stored: it is ADMIN_EMAIL from .env."""

    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LoginCode(Base):
    """One-time 6-digit code: only an HMAC of it is stored; 10 minutes, at most 5 attempts."""

    __tablename__ = "login_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session_id: Mapped[str] = mapped_column(String(64))
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AuthSession(Base):
    """Signed-in browser. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "auth_session"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SavedItem(Base):
    """A user's object list and saved studies (comparisons)."""

    __tablename__ = "saved_item"
    __table_args__ = (UniqueConstraint("user_id", "kind", "ref", name="uq_saved_item_user_kind_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(16))  # object | comparison
    ref: Mapped[str] = mapped_column(String(120))  # object key or comparison id
    label: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # e.g. the search query to reopen it
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Feedback(Base):
    """Feedback from the site's button; the admin panel lists these. E-mail only if the visitor gives one."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(16), index=True)
    message: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    page: Mapped[str | None] = mapped_column(String(200), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    release_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AppState(Base):
    """Small server values that must survive a deploy (the disk cache does not), e.g. the archive's
    newest observation read from IRSA TAP (services/freshness.py)."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Comparison(Base):
    """A computed comparison (time or object-object). The assistant and Excel export read these values."""

    __tablename__ = "comparison"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(16))  # time | object
    object_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    params: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
