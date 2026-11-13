"""Autocomplete: Turkish normalisation, local list, SIMBAD LIKE patterns, graceful upstream failure."""

import asyncio
import json
from pathlib import Path

import pytest

from skytracker.api.v1 import suggest as S
from skytracker.http import UpstreamError
from skytracker.providers import names, resolvers, simbad

ROOT = Path(__file__).resolve().parents[2]


def test_normalize_turkish():
    assert names.normalize("Barnard Yıldızı") == "barnard yildizi"
    assert names.normalize("BARNARD YILDIZI") == "barnard yildizi"  # dotless I -> ı -> i
    assert names.normalize("İstanbul ÇĞÖŞÜ") == "istanbul cgosu"
    assert names.normalize("  Barnard's   Star ") == "barnards star"
    assert names.normalize("WISE 0855−0714") == "wise 0855-0714"


def test_names_file_shape():
    data = json.loads((ROOT / "config" / "names_tr.json").read_text("utf-8"))["names"]
    assert len(data) >= 30
    for e in data:
        assert e["name"] and e["query"] and e["kind"], e
    queries = {e["query"] for e in data}
    assert {"Barnard's Star", "M31", "M42", "WISE J085510.83-071442.5", "3I/ATLAS"} <= queries


@pytest.mark.parametrize(
    ("text", "first"),
    [
        ("barnard", "Barnard Yıldızı"),
        ("BARNARD YILDIZI", "Barnard Yıldızı"),
        ("barnard yildizi", "Barnard Yıldızı"),
        ("kutup", "Kutup Yıldızı"),
        ("demirkazik", "Kutup Yıldızı"),
        ("ulker", "Ülker"),
        ("m31", "Andromeda Galaksisi"),
        ("M 31", "Andromeda Galaksisi"),
        ("wise 0855", "WISE 0855−0714"),
        ("atlas", "3I/ATLAS"),
        ("halley", "Halley Kuyruklu Yıldızı"),
    ],
)
def test_local_search(text, first):
    hits = names.search_local(text)
    assert hits and hits[0]["label"] == first
    assert hits[0]["source"] == "local" and hits[0]["query"]


def test_local_search_ignores_one_letter():
    assert names.search_local("b") == []


def test_simbad_like_patterns():
    assert simbad.adql_like_prefix(["Barnard"]) == "'Barnard%'"  # the % survives (old bug: it was stripped)
    pats = simbad.suggest_patterns("m3")
    assert "'M %3%'" in pats  # matches 'M   3', not 'MSX …' or 'MCC 31'
    assert all(";" not in p for p in simbad.suggest_patterns("x'; DROP TABLE basic --"))
    assert all(p.count("'") % 2 == 0 for p in simbad.suggest_patterns("Barnard's"))  # quotes doubled
    assert simbad.suggest_patterns("a") == []


@pytest.mark.parametrize(
    ("name", "query"),
    [
        ("2688 Halley (1982 HG1)", "2688"),
        ("1P/Halley", "1P"),
        ("427P/ATLAS", "427P"),
        ("C/2017 D3 (ATLAS)", "C/2017 D3"),
    ],
)
def test_jpl_query(name, query):
    assert S.jpl_query(name) == query


def test_coordinates_offer_search_here(client):
    j = client.get("/api/v1/suggest", params={"q": "10.68 +41.27"}).json()
    assert j["items"][0]["kind"] == "coordinate" and j["items"][0]["ra"] == pytest.approx(10.68)


def test_local_only_is_instant_and_partial(client, monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("no upstream call expected")

    monkeypatch.setattr(resolvers, "sesame", boom)
    j = client.get("/api/v1/suggest", params={"q": "barnard", "local": "1"}).json()
    assert j["partial"] is True and j["items"][0]["label"] == "Barnard Yıldızı"


def test_upstream_failures_fall_back_to_local(client, monkeypatch):
    async def down(*a, **k):
        raise UpstreamError("UPSTREAM_UNAVAILABLE", "cds")

    async def slow(*a, **k):
        await asyncio.sleep(5)

    monkeypatch.setattr(S, "DEADLINE_S", 0.2)
    monkeypatch.setattr(resolvers, "sesame", down)
    monkeypatch.setattr(simbad, "suggest", slow)
    monkeypatch.setattr(resolvers, "jpl_sbdb", down)
    j = client.get("/api/v1/suggest", params={"q": "barnard x"}).json()
    assert set(j["unavailable"]) == {"sesame", "simbad", "jpl"}
    j = client.get("/api/v1/suggest", params={"q": "barnard"}).json()
    assert j["items"][0]["label"] == "Barnard Yıldızı"


def test_merge_dedupes_and_limits(client, monkeypatch):
    async def ses(*a, **k):
        return {"main_id": "NAME Barnard's star", "otype": "BY*"}

    async def sb(*a, **k):
        return [{"label": f"Barnard {i}", "main_id": f"Barnard {i}", "otype": "DNe"} for i in range(20)]

    async def none(*a, **k):
        return None

    monkeypatch.setattr(resolvers, "sesame", ses)
    monkeypatch.setattr(simbad, "suggest", sb)
    monkeypatch.setattr(resolvers, "jpl_sbdb", none)
    monkeypatch.setattr(S.cache, "get_json", lambda *a, **k: None)
    monkeypatch.setattr(S.cache, "put_json", lambda *a, **k: None)
    items = client.get("/api/v1/suggest", params={"q": "barnard"}).json()["items"]
    assert len(items) == 8
    labels = [i["label"] for i in items]
    assert labels[0] == "Barnard Yıldızı"
    assert "Barnard's star" not in labels  # same object as the local entry -> merged away


def _upstreams(monkeypatch, ses=None, sb=(), jpl=None):
    async def _ses(*a, **k):
        return ses

    async def _sb(*a, **k):
        return list(sb)

    async def _jpl(*a, **k):
        return jpl

    monkeypatch.setattr(resolvers, "sesame", _ses)
    monkeypatch.setattr(simbad, "suggest", _sb)
    monkeypatch.setattr(resolvers, "jpl_sbdb", _jpl)
    monkeypatch.setattr(S.cache, "get_json", lambda *a, **k: None)
    monkeypatch.setattr(S.cache, "put_json", lambda *a, **k: None)


def test_exact_match_comes_before_partial_local_matches(client, monkeypatch):
    # "m3": the local list only has partial hits (M31, M33); Sesame resolves M 3 itself
    sb = [{"label": "M  34", "main_id": "NGC  1039", "otype": "OpC"}]
    _upstreams(monkeypatch, ses={"main_id": "M 3", "otype": "GlC"}, sb=sb)
    items = client.get("/api/v1/suggest", params={"q": "m3"}).json()["items"]
    labels = [i["label"] for i in items]
    assert labels[0] == "M 3" and items[0]["exact"] is True
    assert labels.index("Andromeda Galaksisi") > 0 and labels.index("Üçgen Galaksisi") > 0
    assert labels.index("M  34") > labels.index("M 3")


def test_exact_simbad_identifier_is_promoted(client, monkeypatch):
    # "ngc 70": local "Kuzey Amerika Bulutsusu" (alias NGC 7000) is only a prefix match
    sb = [
        {"label": "NGC  6709     3", "main_id": "NGC  6709     3", "otype": "*"},
        {"label": "NGC    70", "main_id": "NGC    70", "otype": "G"},
    ]
    _upstreams(monkeypatch, sb=sb)
    labels = [i["label"] for i in client.get("/api/v1/suggest", params={"q": "ngc 70"}).json()["items"]]
    assert labels[0] == "NGC    70"
    assert labels.index("Kuzey Amerika Bulutsusu") < labels.index("NGC  6709     3")  # rest keeps its order


def test_exact_local_name_stays_first(client, monkeypatch):
    _upstreams(monkeypatch, ses={"main_id": "M  31", "otype": "AGN"})
    items = client.get("/api/v1/suggest", params={"q": "m31"}).json()["items"]
    assert items[0]["label"] == "Andromeda Galaksisi" and items[0]["exact"] is True
    assert [i["label"] for i in items].count("M  31") == 0  # same object, merged into the local entry


def test_exact_turkish_name_maps_to_catalogue_query():
    assert names.exact_query("Kutup Yıldızı") == "Polaris"
    assert names.exact_query("barnard yildizi") == "Barnard's Star"
    assert names.exact_query("Kutup") is None  # only exact names/aliases, never a prefix


def test_resolve_uses_local_turkish_name(client, monkeypatch):
    seen = []

    async def ses(name, *a, **k):
        seen.append(name)
        return None

    async def none(*a, **k):
        return None

    async def no_cands(*a, **k):
        return []

    monkeypatch.setattr(resolvers, "sesame", ses)
    monkeypatch.setattr(resolvers, "jpl_sbdb", none)
    monkeypatch.setattr(resolvers, "suggestions", no_cands)
    client.get("/api/v1/resolve", params={"q": "Kutup Yıldızı"})
    assert seen == ["Polaris"]
