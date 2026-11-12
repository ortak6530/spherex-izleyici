from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ... import __version__
from ...db import get_db

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001 - health must never raise
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "db": "ok" if db_ok else "error",
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
    }
