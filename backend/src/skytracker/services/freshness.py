"""Newest SPHEREx observation in the archive, read live from IRSA TAP in the background.

`SELECT TOP 1 t_min ... ORDER BY t_min DESC` takes ~2 minutes per collection (measured 2026-11-14),
far too slow for a chat answer. So the server checks at start-up and every 12 hours and keeps the
last answer (memory + disk cache). Readers get the stored value with the time it was checked, or
None while the first check is still running: nothing is ever hard-coded or guessed.
"""

from __future__ import annotations

import asyncio
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


async def refresh() -> dict | None:
    """Ask TAP for every active release; keep the newest. Returns the stored state (or None)."""
    global _state
    per_release = {}
    for rel in releases().active:
        for coll in rel.sia_collections:
            try:
                hit = await _newest(coll)
            except Exception:  # noqa: BLE001 - archive slow or down: keep the previous answer
                log.info("freshness query for %s failed", coll, exc_info=True)
                hit = None
            if hit:
                per_release[rel.id] = {**hit, "release": rel.label, "collection": coll}
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
    return _state


def latest() -> dict | None:
    global _state
    if _state is None:
        _state = cache.get_json(NS, KEY, 2 * REFRESH_S)
    return _state


async def run_forever() -> None:
    while True:
        await refresh()
        await asyncio.sleep(REFRESH_S)
