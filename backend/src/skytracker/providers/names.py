"""Local Turkish name list (config/names_tr.json) and Turkish-aware text normalisation for suggestions."""

from __future__ import annotations

import json
import re
from functools import lru_cache

from ..settings import get_settings

_TR_MAP = str.maketrans("çğıöşüâîû", "cgiosuaiu")
_NON_WORD = re.compile(r"[^0-9a-z*+\-/ ]+")


def normalize(text: str) -> str:
    """'Barnard Yıldızı' -> 'barnard yildizi', 'İSTANBUL' -> 'istanbul', "Barnard's" -> 'barnards'.

    Turkish dotted/dotless I are lower-cased by hand first (str.lower() maps 'I' to 'i' and 'İ' to 'i̇').
    """
    t = (text or "").replace("İ", "i").replace("I", "ı").lower().translate(_TR_MAP)
    t = t.replace("'", "").replace("’", "").replace("−", "-")
    t = _NON_WORD.sub(" ", t)
    return " ".join(t.split())


@lru_cache
def _entries() -> list[dict]:
    path = get_settings().config_dir / "names_tr.json"
    data = json.loads(path.read_text("utf-8"))
    out = []
    for e in data["names"]:
        keys = {normalize(k) for k in [e["name"], e["query"], *e.get("aliases", [])]}
        out.append({**e, "_keys": sorted(k for k in keys if k)})
    return out


def _score(q: str, keys: list[str]) -> int | None:
    """0 exact, 1 prefix, 2 word prefix, 3 substring; None = no match. Compact forms ('m31' = 'm 31') too."""
    qc = q.replace(" ", "")
    best = None
    for k in keys:
        kc = k.replace(" ", "")
        if q == k or qc == kc:
            s = 0
        elif k.startswith(q) or kc.startswith(qc):
            s = 1
        elif any(w.startswith(q) for w in k.split()):
            s = 2
        elif len(q) >= 3 and q in k:
            s = 3
        else:
            continue
        best = s if best is None else min(best, s)
    return best


def exact_query(text: str) -> str | None:
    """'Kutup Yıldızı' -> 'Polaris' when the text is exactly a listed name or alias (used by /resolve)."""
    q = normalize(text)
    if len(q) < 2:
        return None
    for e in _entries():
        if _score(q, e["_keys"]) == 0:
            return e["query"]
    return None


def search_local(text: str, limit: int = 8) -> list[dict]:
    q = normalize(text)
    if len(q) < 2:
        return []
    hits = []
    for i, e in enumerate(_entries()):
        s = _score(q, e["_keys"])
        if s is not None:
            hits.append((s, i, e))
    hits.sort(key=lambda h: (h[0], h[1]))
    return [
        {"label": e["name"], "query": e["query"], "detail": e.get("kind"), "source": "local", "exact": s == 0}
        for s, _, e in hits[:limit]
    ]
