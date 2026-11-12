"""ORM models. Phase 1: event log only; later phases add tables via Alembic migrations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String
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
