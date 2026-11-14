"""Newest SPHEREx observation in the archive, read live from IRSA TAP in the background.

`SELECT TOP 1 t_min ... ORDER BY t_min DESC` takes ~2 minutes per collection (measured 2026-11-14),
far too slow for a chat answer. So the server checks in the background every 12 hours (both
collections in parallel) and keeps the last answer in memory, the disk cache and the database
(`app_state`): a deploy wipes the disk, so at start-up the database value is shown at once, with the
time it was checked. Only on a brand-new database is it None until the first check ends ("okunuyor");
nothing is ever hard-coded or guessed.
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import re
import time

from astropy.time import Time

from .. import cache
from ..config_loader import releases
from ..http import http

log = logging.getLogger("skytracker.freshness")
TAP_URL = "https://irsa.ipac.caltech.edu/TAP/sync"
REFRESH_S = 12 * 3600
QUERY_TIMEOUT_S = 300
NS, KEY = "_external/freshness", "latest"

_state: dict | None = None


_COLLECTION = re.compile(r"^[a-z0-9_]{1,40}$")


def _query(collection: str) -> str:
    # The name comes from config/releases.toml, never from a request; checked anyway before quoting
    if not _COLLECTION.match(collection):
        raise ValueError(f"unexpected collection name {collection!r}")
    return (
        "SELECT TOP 1 t_min, obs_id FROM spherex.obscore "  # noqa: S608 - name validated above
        f"WHERE obs_collection = '{collection}' ORDER BY t_min DESC"
    )


async def _newest(collection: str) -> dict | None:
    r = await http.get(
        TAP_URL,
        params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": _query(collection)},
        timeout=QUERY_TIMEOUT_S,
        retries=0,
    )
    lines = r.text.strip().splitlines() if r.status_code == 200 else []
    if len(lines) < 2:
        return None
    mjd, obs_id = lines[1].split(",")[:2]
    return {"mjd": float(mjd), "date_utc": Time(float(mjd), format="mjd").isot[:19] + "Z", "obs_id": obs_id}


async def _one(rel, coll: str) -> tuple[str, dict] | None:
    try:
        hit = await _newest(coll)
    except Exception:  # noqa: BLE001 - archive slow or down: keep the previous answer
        log.info("freshness query for %s failed", coll, exc_info=True)
        return None
    return (rel.id, {**hit, "release": rel.label, "collection": coll}) if hit else None


async def refresh() -> dict | None:
    """Ask TAP for every active release (in parallel); keep the newest. Returns the stored state."""
    global _state
    found = await asyncio.gather(*(_one(r, c) for r in releases().active for c in r.sia_collections))
    per_release = dict(f for f in found if f)
    if not per_release:
        return latest()
    newest = max(per_release.values(), key=lambda h: h["mjd"])
    _state = {
        "newest": newest,
        "per_release": per_release,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "IRSA TAP (spherex.obscore)",
    }
    cache.put_json(NS, KEY, _state)
    await asyncio.to_thread(_save_db, _state)
    return _state


# ---------- persistence: the disk cache is wiped by every deploy, the database is not ----------

DB_KEY = "archive_freshness"


def _save_db(state: dict) -> None:
    try:
        from ..db import session_scope
        from ..db.models import AppState, utcnow

        with session_scope() as db:
            row = db.get(AppState, DB_KEY)
            if row is None:
                db.add(AppState(key=DB_KEY, value=state))
            else:
                row.value = state
                row.updated_at = utcnow()
    except Exception:  # noqa: BLE001 - e.g. table not migrated yet; memory/disk copies still work
        log.info("could not store archive freshness", exc_info=True)


def _load_db() -> dict | None:
    try:
        from ..db import session_scope
        from ..db.models import AppState

        with session_scope() as db:
            row = db.get(AppState, DB_KEY)
            return dict(row.value) if row else None
    except Exception:  # noqa: BLE001
        log.info("could not read archive freshness", exc_info=True)
        return None


def latest() -> dict | None:
    global _state
    if _state is None:
        _state = cache.get_json(NS, KEY, 2 * REFRESH_S)
    return _state


def _age_s(state: dict) -> float:
    try:
        return time.time() - calendar.timegm(time.strptime(state["checked_at"], "%Y-%m-%dT%H:%M:%SZ"))
    except (KeyError, ValueError, TypeError):
        return float("inf")


async def load_saved() -> dict | None:
    """Last stored value (database survives deploys); becomes the current answer at once."""
    global _state
    if _state is None and (saved := await asyncio.to_thread(_load_db)):
        _state = saved
        cache.put_json(NS, KEY, saved)
        return saved
    return None


async def run_forever() -> None:
    """At start-up the last value comes back from the database at once (so the status bar and the
    assistant do not say "okunuyor" after a deploy); the slow TAP check then runs when it is due."""
    if (saved := await load_saved()) is not None:
        await asyncio.sleep(max(0.0, REFRESH_S - _age_s(saved)))
    while True:
        await refresh()
        await asyncio.sleep(REFRESH_S)
