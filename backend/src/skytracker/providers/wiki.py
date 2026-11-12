"""Short descriptions from Wikipedia (Turkish first, English fallback) via the SIMBAD id on Wikidata."""

from __future__ import annotations

import re
import urllib.parse

from .. import cache
from ..http import http
from ..settings import get_settings

DAY = 86400


def _ua() -> dict:
    return {"User-Agent": get_settings().wikimedia_user_agent}


async def _qid_for_simbad(main_id: str) -> str | None:
    for candidate in dict.fromkeys([main_id, re.sub(r"\s+", " ", main_id)]):
        r = await http.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "format": "json",
                "srlimit": 1,
                "srsearch": f'haswbstatement:"P3083={candidate}"',
            },
            headers=_ua(),
            timeout=8,
            retries=0,
        )
        if r.status_code == 200 and (hits := r.json().get("query", {}).get("search")):
            return hits[0]["title"]
    return None


async def summary(main_id: str) -> dict | None:
    key = main_id.strip()
    if (hit := cache.get_json("_external/wiki", key, DAY)) is not None:
        return hit.get("result")
    result = None
    qid = await _qid_for_simbad(key)
    if qid:
        e = await http.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetentities",
                "ids": qid,
                "props": "sitelinks",
                "sitefilter": "trwiki|enwiki",
                "format": "json",
            },
            headers=_ua(),
            timeout=8,
            retries=0,
        )
        links = e.json().get("entities", {}).get(qid, {}).get("sitelinks", {}) if e.status_code == 200 else {}
        for lang in ("tr", "en"):
            title = links.get(f"{lang}wiki", {}).get("title")
            if not title:
                continue
            s = await http.get(
                f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
                + urllib.parse.quote(title.replace(" ", "_")),
                headers=_ua(),
                timeout=8,
                retries=0,
            )
            if s.status_code == 200:
                d = s.json()
                result = {
                    "lang": lang,
                    "title": d.get("title"),
                    "extract": d.get("extract"),
                    "url": d.get("content_urls", {}).get("desktop", {}).get("page"),
                    "wikidata": qid,
                }
                break
    cache.put_json("_external/wiki", key, {"result": result})
    return result
